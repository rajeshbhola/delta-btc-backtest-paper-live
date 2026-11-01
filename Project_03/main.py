"""Project 3 command-line interface. No exchange keys, WebSocket, or orders."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from indicator_studio.config import TIMEFRAMES
from indicator_studio.demo import create_demo
from indicator_studio.pipeline import analyze


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Project 3: BTCUSD technical indicators with JSON + Streamlit")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Generate synthetic demonstration candles")
    demo.add_argument("--output", default="demo_data")
    demo.add_argument("--rows", type=int, default=500)
    demo.add_argument("--force", action="store_true")
    calc = commands.add_parser("analyze", help="Calculate indicators from Project 2 cleaned JSON")
    calc.add_argument("--source", default="demo_data", help="Project 2 root / clean folder or Project 1 candles root")
    calc.add_argument("--output", default="data", help="Own Project 3 output root")
    calc.add_argument("--timeframes", nargs="+", choices=list(TIMEFRAMES), default=list(TIMEFRAMES))
    report = commands.add_parser("summary", help="Print previously generated reports")
    report.add_argument("--output", default="data")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = create_parser().parse_args(argv)
    if args.command == "demo":
        counts = create_demo(args.output, rows=args.rows, overwrite=args.force)
        for tf, count in counts.items():
            print(f"{tf}: generated {count} SYNTHETIC candles")
    elif args.command == "analyze":
        reports = analyze(args.source, args.output, timeframes=args.timeframes)
        if not reports:
            print("No files processed. Check your --source path.")
            return 1
    else:
        reports = Path(args.output) / "reports"
        files = sorted(reports.glob("BTCUSD_*_indicators.json")) if reports.exists() else []
        if not files:
            print("No reports yet. Run: python main.py analyze --source demo_data")
            return 1
        for file in files:
            r = json.loads(file.read_text(encoding="utf-8"))
            print(f"{r['timeframe']:>3} | rows: {r['rows']:>8,} | missing slots: {r['missing_candle_slots']:>6,} | last: {r['last_candle']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
