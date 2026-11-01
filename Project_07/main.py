"""Project 7 CLI: one-trade calculator + trade-file cost sensitivity."""
from __future__ import annotations
import argparse
from pathlib import Path
from cost_lab.model import Costs, Trade, calculate
from cost_lab.portfolio import load_trades, run_portfolio
from cost_lab.demo import make_demo_trades
from cost_lab.files import save_json
import json


def build_parser():
    parser = argparse.ArgumentParser(description="Standalone BTCUSD futures transaction cost simulator (offline, no API keys)")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Generate synthetic demo trades and results")
    demo.add_argument("--output", default="demo_generated")
    single = sub.add_parser("single", help="Simulate one completed BTCUSD futures trade")
    single.add_argument("--side", choices=["LONG", "SHORT"], default="LONG")
    single.add_argument("--entry", type=float, default=100000)
    single.add_argument("--exit", type=float, default=101000)
    single.add_argument("--contracts", type=int, default=10)
    single.add_argument("--funding-events", type=int, default=0)
    single.add_argument("--output", default="results/single_trade.json")
    batch = sub.add_parser("batch", help="Analyze synthetic trades or Project 6 trade logs")
    batch.add_argument("--trades", default="demo_data/trades.json", help="Project 6 results folder or JSON trade file")
    batch.add_argument("--timeframe", choices=["1m", "5m", "15m", "1h", "4h"], default="5m")
    batch.add_argument("--capital", type=float, default=10000)
    batch.add_argument("--sizing", choices=["fixed", "one_x"], default="fixed")
    batch.add_argument("--contracts", type=int, default=10)
    batch.add_argument("--output", default="results/batch_results.json")
    for command in [single, batch]:
        command.add_argument("--entry-order", choices=["maker", "taker"], default="taker")
        command.add_argument("--exit-order", choices=["maker", "taker"], default="taker")
        command.add_argument("--maker-bps", type=float, default=2.0)
        command.add_argument("--taker-bps", type=float, default=5.0)
        command.add_argument("--gst-pct", type=float, default=18.0)
        command.add_argument("--spread-bps", type=float, default=2.0)
        command.add_argument("--slippage-bps", type=float, default=1.0)
        command.add_argument("--funding-rate-pct", type=float, default=0.01)
        command.add_argument("--usd-inr", type=float, default=85.0)
        command.add_argument("--leverage", type=float, default=2.0)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command == "demo":
        rows = make_demo_trades()
        save_json(Path(args.output) / "trades.json", rows)
        portfolio = run_portfolio(rows)
        dest = save_json(Path(args.output) / "batch_results.json", portfolio)
        print(f"Synthetic trades saved under {args.output}; {len(rows)} trades, net PnL ${portfolio['summary']['net_pnl_usd']:+,.2f}")
        print(f"See {dest}")
        return
    cfg = Costs(maker_fee_bps=args.maker_bps, taker_fee_bps=args.taker_bps,
                gst_pct=args.gst_pct, spread_bps=args.spread_bps, slippage_bps=args.slippage_bps,
                funding_rate_pct=args.funding_rate_pct, fx_usd_inr=args.usd_inr, leverage=args.leverage)
    if args.command == "single":
        trade = Trade(side=args.side, entry_price=args.entry, exit_price=args.exit,
                      contracts=args.contracts, funding_events=args.funding_events,
                      entry_order=args.entry_order, exit_order=args.exit_order)
        result = calculate(trade, cfg)
        saved = save_json(args.output, result)
        print(f"Reference gross: ${result['gross_reference_pnl_usd']:+,.2f}")
        print(f"Commission+GST: ${result['commission_usd'] + result['gst_usd']:,.2f}")
        print(f"Spread+Slippage: ${result['spread_cost_usd'] + result['slippage_cost_usd']:,.2f}")
        print(f"Funding paid (+) or received (-): ${result['funding_paid_usd']:+,.2f}")
        print(f"Net PnL: ${result['net_pnl_usd']:+,.2f} (indicative INR {result['net_pnl_inr_estimate']:+,.2f})")
    else:
        rows = load_trades(args.trades, timeframe=args.timeframe)
        result = run_portfolio(rows, cfg, capital=args.capital, sizing=args.sizing,
                               contracts=args.contracts, entry_order=args.entry_order, exit_order=args.exit_order)
        saved = save_json(args.output, result)
        print(f"Trades: {len(result['trades'])} | Gross ${result['summary']['gross_pnl_usd']:+,.2f} | Net ${result['summary']['net_pnl_usd']:+,.2f}")
        print("Project 6 compatibility is trade-price cost sensitivity, NOT identical to its rebalanced equity engine.")
    print(f"Saved {saved}")


if __name__ == "__main__":
    main()
