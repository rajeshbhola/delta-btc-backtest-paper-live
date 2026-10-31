"""Optional one-time migration from Project 1 v2 Parquet archives to JSON.

Does not delete source Parquet. Install `pyarrow` separately if migration needed.
"""
import argparse
from pathlib import Path

import pandas as pd

from delta_collector.config import DEFAULT_TIMEFRAMES
from delta_collector.storage import CandleStore


def migrate(source: Path, destination: Path, symbol: str, timeframes=DEFAULT_TIMEFRAMES) -> dict:
    store = CandleStore(destination)
    counts = {}
    for tf in timeframes:
        total = 0
        for path in sorted((source / symbol / tf).glob("????-??.parquet")):
            frame = pd.read_parquet(path)
            total += store.write(symbol, tf, frame)
        counts[tf] = total
    return counts


def main():
    parser = argparse.ArgumentParser(description="Convert old Parquet candle files to JSON")
    parser.add_argument("--source", type=Path, default=Path("data/candles_parquet"))
    parser.add_argument("--dest", type=Path, default=Path("data/candles"))
    parser.add_argument("--symbol", default="BTCUSD")
    args = parser.parse_args()
    if args.source.resolve() == args.dest.resolve():
        parser.error("--source and --dest must differ to protect your files")
    if not args.source.exists():
        parser.error(f"No source directory: {args.source}")
    print("Migrated candle counts:", migrate(args.source, args.dest, args.symbol))
    print("Original Parquet files remain unchanged.")


if __name__ == "__main__":
    main()
