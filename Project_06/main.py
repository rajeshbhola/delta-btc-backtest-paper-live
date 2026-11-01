"""Project 6 command-line interface. No broker or trading connectivity."""
from __future__ import annotations
import argparse
from datetime import datetime
from pathlib import Path
from backtest_lab.config import TIMEFRAMES
from backtest_lab.pipeline import run_project, read_saved


def build_parser():
    parser = argparse.ArgumentParser(description="Offline BTCUSD vectorized backtesting")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Backtest candle + Project 4 signal JSON")
    run.add_argument("--candles", default="demo_data", help="Folder containing clean/, candles/ or indicators/BTCUSD")
    run.add_argument("--signals", default="demo_data", help="Folder containing signals/BTCUSD")
    run.add_argument("--output", default="results")
    run.add_argument("--timeframes", nargs="+", choices=list(TIMEFRAMES), default=["5m"])
    run.add_argument("--capital", type=float, default=10000)
    run.add_argument("--mode", choices=["long_only", "long_short"], default="long_only")
    run.add_argument("--fee-bps", type=float, default=0.0, help="Flat illustrative fee bps per side; not actual Delta charges")
    run.add_argument("--days", type=int)
    run.add_argument("--as-of-utc", help="UTC ISO time to exclude incomplete candles, e.g. 2026-11-01T00:00:00+00:00")
    summary = sub.add_parser("summary")
    summary.add_argument("--output", default="results")
    summary.add_argument("--timeframe", choices=list(TIMEFRAMES), default="5m")
    return parser


def main():
    args = build_parser().parse_args()
    if args.command == "run":
        as_of = datetime.fromisoformat(args.as_of_utc.replace("Z", "+00:00")) if args.as_of_utc else None
        run_project(args.candles, args.signals, args.output, timeframes=args.timeframes,
                    starting_capital=args.capital, mode=args.mode, fee_bps=args.fee_bps, days=args.days, as_of=as_of)
    elif args.command == "summary":
        report, curve, trades = read_saved(args.output, args.timeframe)
        for key in ("timeframe", "mode", "candles", "trade_count", "starting_capital_usd", "ending_capital_usd", "net_return_pct", "win_rate_pct", "max_drawdown_pct"):
            print(f"{key:25} {report[key]}")


if __name__ == "__main__":
    main()
