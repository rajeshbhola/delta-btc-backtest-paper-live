"""CLI entry point for a standalone, offline-only event-driven backtesting lab."""
import argparse
from pathlib import Path
from event_lab.data import INTERVALS, load_candles, load_signals, dump_json
from event_lab.engine import Settings, execute


def main():
    p = argparse.ArgumentParser(description="BTCUSD Event-Driven Backtesting Lab (no broker orders)")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("run", help="Run a historical event simulation")
    a.add_argument("--candles", default="demo_data", help="Root containing candles/BTCUSD/<timeframe> JSON or Project 2/3 output")
    a.add_argument("--signals", default="demo_data", help="Root containing signals/BTCUSD/<timeframe> JSON (Project 4 compatible)")
    a.add_argument("--output", default="results")
    a.add_argument("--timeframes", nargs="+", choices=list(INTERVALS), default=["5m"])
    a.add_argument("--capital", type=float, default=10000.0)
    a.add_argument("--contracts", type=int, default=5)
    a.add_argument("--contract-btc", type=float, default=0.001)
    a.add_argument("--fee-bps", type=float, default=5.0)
    a.add_argument("--gst-pct", type=float, default=18.0)
    a.add_argument("--spread-bps", type=float, default=1.0)
    a.add_argument("--slippage-bps", type=float, default=1.0)
    a.add_argument("--max-fill-contracts", type=int, default=5)
    a.add_argument("--max-leverage", type=float, default=2.0)
    a.add_argument("--mode", choices=["long_only", "long_short"], default="long_short")
    a.add_argument("--max-candles", type=int, default=3000, help="0 means full dataset; use carefully for 1m 1-year")
    g = sub.add_parser("demo", help="Regenerate bundled synthetic candles and signals")
    g.add_argument("--output", default="demo_data")
    s = sub.add_parser("summary", help="Print saved summary from a previous run")
    s.add_argument("--output", default="results")
    s.add_argument("--timeframe", choices=list(INTERVALS), default="5m")
    args = p.parse_args()
    if args.command == "demo":
        from event_lab.demo import generate
        generate(args.output)
        print(f"Synthetic demo data saved under {args.output}")
    elif args.command == "run":
        for tf in args.timeframes:
            cfg = Settings(timeframe=tf, capital_usd=args.capital, contracts_per_order=args.contracts,
                           contract_btc=args.contract_btc, fee_bps=args.fee_bps, gst_pct=args.gst_pct,
                           spread_bps=args.spread_bps, slippage_bps=args.slippage_bps,
                           max_fill_contracts=args.max_fill_contracts, max_leverage=args.max_leverage, mode=args.mode)
            candles = load_candles(args.candles, tf, args.max_candles)
            signals = load_signals(args.signals, tf, candles)
            result = execute(candles, signals, cfg)
            folder = Path(args.output) / "BTCUSD" / tf
            for key, value in result.items():
                dump_json(folder / f"{key}.json", value)
            summ = result["summary"]
            print(f"{tf}: {len(candles)} candles | {summ['fill_count']} fills | "
                  f"{summ['return_pct']:.3f}% return | {summ['max_drawdown_pct']:.3f}% max DD "
                  f"| equity ${summ['ending_equity_usd']:.2f} -> {folder}")
    else:
        import json
        path = Path(args.output) / "BTCUSD" / args.timeframe / "summary.json"
        print(json.dumps(json.loads(path.read_text(encoding="utf-8")), indent=2))

if __name__ == "__main__":
    main()
