"""Simple command-line chart export and dataset inspection."""
from __future__ import annotations
import argparse
from datetime import timedelta
from pathlib import Path
import pandas as pd
from chart_lab.config import TIMEFRAMES
from chart_lab.sources import locate_root, latest_timestamp, load_range, combine_candles_and_indicators
from chart_lab.analytics import audit_window, signal_summary
from chart_lab.figures import make_price_figure
from chart_lab.demo import generate_demo


def read_sources(args):
    candle_root = locate_root(args.candles, "candles")
    indicator_root = locate_root(args.indicators, "indicators")
    signal_root = locate_root(args.signals, "signals")
    end_bar = latest_timestamp(candle_root, args.timeframe) or latest_timestamp(indicator_root, args.timeframe)
    if not end_bar:
        raise SystemExit("No candles found. Check --candles/--indicators path and --timeframe.")
    end = end_bar + timedelta(seconds=TIMEFRAMES[args.timeframe])
    start = end - timedelta(days=args.days)
    candles, _ = load_range(candle_root, args.timeframe, start, end, args.limit)
    indicators, _ = load_range(indicator_root, args.timeframe, start, end, args.limit)
    signals, _ = load_range(signal_root, args.timeframe, start, end, args.limit)
    return combine_candles_and_indicators(candles, indicators), signals


def main():
    parser = argparse.ArgumentParser(description="Read-only BTC chart explorer")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Generate bundled-style synthetic demo data")
    demo.add_argument("--output", default="my_demo")
    for cmd in ("inspect", "export"):
        item = sub.add_parser(cmd)
        item.add_argument("--candles", default=None, help="Root containing candles/BTCUSD or clean/BTCUSD")
        item.add_argument("--indicators", default=None, help="Root containing indicators/BTCUSD")
        item.add_argument("--signals", default=None, help="Root containing signals/BTCUSD")
        item.add_argument("--timeframe", choices=TIMEFRAMES, default="5m")
        item.add_argument("--days", type=int, default=7)
        item.add_argument("--limit", type=int, default=1500)
        if cmd == "export":
            item.add_argument("--output", default="exports/BTCUSD_chart.html")
    args = parser.parse_args()
    if args.command == "demo":
        result = generate_demo(Path(args.output))
        print("Generated SYNTHETIC demo JSON:", result)
        return
    if args.days < 1:
        parser.error("--days must be >= 1")
    if args.candles is None and args.indicators is None and args.signals is None:
        args.candles = args.indicators = args.signals = "demo_data"
    candles, signals = read_sources(args)
    print(f"Timeframe: {args.timeframe} | candle rows: {len(candles)} | signal rows: {len(signals)}")
    print("Quality:", audit_window(candles, args.timeframe))
    print("Signals:", signal_summary(signals))
    if args.command == "export":
        dest = Path(args.output)
        dest.parent.mkdir(parents=True, exist_ok=True)
        figure = make_price_figure(candles, signals, ["ema_9", "ema_21"], volume=True)
        figure.write_html(str(dest), include_plotlyjs=True)
        print("Standalone HTML chart saved to", dest.resolve())

if __name__ == "__main__":
    main()
