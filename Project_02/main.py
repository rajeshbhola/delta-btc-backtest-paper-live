"""Project 2 CLI. Run `python main.py --help` for the commands."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

from quality_lab.config import TIMEFRAMES, SYMBOL, closed_end, iso_utc, parse_utc
from quality_lab.delta_rest import DeltaPublicClient, pages, recent_raw_timestamp
from quality_lab.demo import create_demo
from quality_lab.json_store import JsonStore, import_project1
from quality_lab.pipeline import process


def _timeframes(args) -> list[str]:
    names = args.timeframes if args.timeframes else list(TIMEFRAMES)
    invalid = sorted(set(names) - set(TIMEFRAMES))
    if invalid:
        raise ValueError(f"Unsupported timeframes: {invalid}. Choose from {', '.join(TIMEFRAMES)}")
    return list(dict.fromkeys(names))


def _print_quality(report: dict) -> None:
    tf = report["timeframe"]
    q = report["quality"]
    c = report["coverage"]
    print(f"{tf:4} raw={q['raw_rows']:>7} clean={q['clean_rows']:>7} "
          f"invalid={q['rejected_rows']:>5} dup={q['duplicate_rows']:>5} "
          f"missing={c['missing']:>7} coverage={c['coverage_pct']:>7.2f}%")


def command_download(args, store: JsonStore):
    if not 1 <= args.days <= 3650:
        raise ValueError("--days must be 1..3650")
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=args.days)
    with DeltaPublicClient(pause=args.pause) as client:
        for tf in _timeframes(args):
            end = closed_end(now, tf)
            from_dt = start
            if not args.from_start:
                latest = recent_raw_timestamp(store.read("raw", tf), tf, now)
                if latest:
                    from_dt = max(start, latest + timedelta(seconds=TIMEFRAMES[tf]))
            batches = 0
            saved = 0
            print(f"Downloading {SYMBOL} {tf}: {iso_utc(from_dt)} -> {iso_utc(end)}")
            for first, last in pages(from_dt, end, tf):
                rows = client.get(tf, first, last)
                saved += store.merge_by_timestamp("raw", tf, rows)
                batches += 1
                if batches % 25 == 0:
                    print(f"  {tf}: completed {batches} pages, received {saved} candles")
            print(f"  {tf}: pages={batches}, candles_received={saved}. Now run 'process'.")


def command_repair(args, store: JsonStore):
    if not 1 <= args.max_candles <= 20000:
        raise ValueError("--max-candles must be 1..20000")
    if not 1 <= args.max_gaps <= 100:
        raise ValueError("--max-gaps must be 1..100")
    for tf in _timeframes(args):
        report = store.read_report(tf)
        if not report:
            print(f"{tf}: no quality report. Run 'process' first.")
            continue
        ranges = report["coverage"]["missing_ranges"]
        if not ranges:
            print(f"{tf}: no gaps to repair.")
            continue
        budget = args.max_candles
        fetched = 0
        attempts = 0
        now = datetime.now(timezone.utc)
        with DeltaPublicClient(pause=args.pause) as client:
            for gap in ranges[:args.max_gaps]:
                if budget <= 0:
                    break
                lo = parse_utc(gap["start_utc"])
                last = parse_utc(gap["end_utc"])
                step = TIMEFRAMES[tf]
                end = min(last + timedelta(seconds=step), closed_end(now, tf), lo + timedelta(seconds=step * budget))
                for a, b in pages(lo, end, tf):
                    received = client.get(tf, a, b)
                    fetched += store.merge_by_timestamp("repairs", tf, received)
                    attempts += 1
                    budget -= (b - a) // step + 1
            print(f"{tf}: requested {attempts} missing-data pages; received {fetched} candles. Re-run 'process' to refresh reports.")


def make_parser():
    parser = argparse.ArgumentParser(description="Independent BTCUSD JSON data cleaning and auditing project")
    parser.add_argument("--data-dir", default="data", help="Project 2 JSON data directory (default: data)")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Generate fake data with deliberate errors, no internet")
    demo.add_argument("--days", type=int, default=2)
    demo.add_argument("--force", action="store_true", help="Replace existing raw/demo data")
    imp = sub.add_parser("import", help="Copy monthly JSON candles from Project 1")
    imp.add_argument("--source", required=True, help="Path to Project 1's data/candles folder, data folder, or project root")
    imp.add_argument("--overwrite", action="store_true", help="Replace existing raw monthly files")
    down = sub.add_parser("download", help="Standalone REST fetch, no Project 1 required")
    down.add_argument("--days", type=int, default=7)
    down.add_argument("--timeframes", nargs="+", choices=list(TIMEFRAMES))
    down.add_argument("--from-start", action="store_true", help="Re-download entire window rather than resume after latest raw candle")
    down.add_argument("--pause", type=float, default=.25, help="Seconds between public REST requests")
    proc = sub.add_parser("process", help="Clean raw data and create quality reports")
    proc.add_argument("--days", type=int, default=7)
    proc.add_argument("--timeframes", nargs="+", choices=list(TIMEFRAMES))
    repair = sub.add_parser("repair", help="Try to fill report gaps from Delta public REST (without fake data)")
    repair.add_argument("--timeframes", nargs="+", choices=list(TIMEFRAMES))
    repair.add_argument("--max-gaps", type=int, default=5)
    repair.add_argument("--max-candles", type=int, default=2000)
    repair.add_argument("--pause", type=float, default=.25)
    return parser


def main(argv=None):
    parser = make_parser()
    args = parser.parse_args(argv)
    store = JsonStore(args.data_dir)
    try:
        if args.command == "demo":
            counts = create_demo(store, days=args.days, force=args.force)
            print("Generated SYNTHETIC raw candles (with deliberate mistakes):", counts)
            print(f"Next: python main.py process --days {args.days}")
        elif args.command == "import":
            print("Imported monthly JSON files:", import_project1(args.source, store, overwrite=args.overwrite))
            print("Next: python main.py process --days 365")
        elif args.command == "download":
            if args.pause < 0:
                raise ValueError("--pause cannot be negative")
            command_download(args, store)
        elif args.command == "process":
            for tf in _timeframes(args):
                _print_quality(process(store, tf, days=args.days))
            print(f"Clean JSON: {store.root / 'clean' / SYMBOL}; quality reports: {store.root / 'reports'}")
        elif args.command == "repair":
            if args.pause < 0:
                raise ValueError("--pause cannot be negative")
            command_repair(args, store)
    except (ValueError, FileNotFoundError, FileExistsError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
