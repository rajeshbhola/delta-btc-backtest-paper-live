"""Project 4 CLI. OFFLINE ONLY: never places exchange orders."""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from signal_lab.config import SignalConfig, TIMEFRAMES
from signal_lab.pipeline import generate


def parse_as_of(text: str) -> datetime:
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise argparse.ArgumentTypeError("Use ISO UTC like 2026-11-01T00:00:00Z") from error
    if value.tzinfo is None:
        raise argparse.ArgumentTypeError("As-of time must specify a timezone")
    return value.astimezone(timezone.utc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Project 4: BTCUSD EMA+RSI signals (offline only)")
    commands = parser.add_subparsers(dest="command", required=True)
    signals = commands.add_parser("generate", help="Generate timestamped BUY/SELL/HOLD labels")
    signals.add_argument("--source", default="demo_input", help="Project 3 output directory")
    signals.add_argument("--output", default="output", help="Separate signal output directory")
    signals.add_argument("--timeframes", nargs="+", default=list(TIMEFRAMES), choices=list(TIMEFRAMES))
    signals.add_argument("--rsi-buy-min", type=float, default=50)
    signals.add_argument("--rsi-buy-max", type=float, default=75)
    signals.add_argument("--rsi-sell-min", type=float, default=25)
    signals.add_argument("--rsi-sell-max", type=float, default=50)
    signals.add_argument("--as-of-utc", type=parse_as_of, default=None,
                         help="Only completed candles as of this ISO UTC time (optional)")
    summary = commands.add_parser("summary", help="Summarize previously created signals")
    summary.add_argument("--output", default="output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "generate":
        params = SignalConfig(args.rsi_buy_min, args.rsi_buy_max,
                              args.rsi_sell_min, args.rsi_sell_max)
        reports = generate(args.source, args.output, timeframes=args.timeframes,
                           config=params, as_of=args.as_of_utc)
        if not reports:
            print("No indicator files processed. Check your --source folder")
            return 1
        print("Done. Source indicator files were not modified.")
        return 0
    reports = sorted((Path(args.output) / "reports").glob("BTCUSD_*_signals.json"))
    if not reports:
        print("No reports found. Run: python main.py generate --source demo_input")
        return 1
    for file in reports:
        row = json.loads(file.read_text(encoding="utf-8"))
        counts = row["signals"]
        print(f"{row['timeframe']:>3}: BUY={counts['BUY']:>5} SELL={counts['SELL']:>5} "
              f"HOLD={counts['HOLD']:>8} gaps={row['missing_candle_slots']} origin={row['data_origin']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
