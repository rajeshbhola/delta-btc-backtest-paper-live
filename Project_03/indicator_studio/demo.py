"""Create deterministic and clearly synthetic candle datasets for every timeframe."""
from __future__ import annotations
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from .config import SYMBOL, TIMEFRAMES
from .json_files import write_json


def create_demo(root: str | Path = "demo_data", *, rows: int = 500, overwrite: bool = False) -> dict[str, int]:
    if not (100 <= rows <= 10000):
        raise ValueError("Choose between 100 and 10,000 synthetic candles per timeframe")
    base = Path(root) / "clean" / SYMBOL
    end_utc = int(datetime(2026, 10, 30, 0, 0, tzinfo=timezone.utc).timestamp())
    write_json(Path(root) / "SYNTHETIC_DATA_NOTICE.json", {"warning": "SYNTHETIC DEMONSTRATION CANDLES. NOT REAL DELTA MARKET DATA."})
    counts = {}
    for i, (tf, seconds) in enumerate(TIMEFRAMES.items()):
        rng = random.Random(1500 + i)
        start = end_utc - (rows + 3) * seconds
        price = 100000.0 + i * 1000
        candles = []
        for j in range(rows):
            if j == 230:
                continue  # ONE intentional gap, so dashboard can illustrate warm-up reset
            stamp = start + j * seconds
            movement = 20 * math.sin(j / 11) + rng.uniform(-45, 45)
            op = price
            close = max(1000.0, op + movement)
            high = max(op, close) + rng.uniform(2, 35)
            low = min(op, close) - rng.uniform(2, 35)
            candles.append({
                "timestamp_utc": datetime.fromtimestamp(stamp, timezone.utc).isoformat().replace("+00:00", "Z"),
                "open": round(op, 2), "high": round(high, 2), "low": round(low, 2),
                "close": round(close, 2), "volume": round(rng.uniform(1, 80), 4),
            })
            price = close
        # Two months for the 4h example, sometimes more depending on dates.
        by_month: dict[str, list[dict]] = {}
        for c in candles:
            by_month.setdefault(c["timestamp_utc"][:7], []).append(c)
        for month, group in by_month.items():
            dest = base / tf / f"{month}.json"
            if dest.exists() and not overwrite:
                raise FileExistsError(f"{dest} exists; use --force to replace demo data")
            write_json(dest, group)
        if overwrite:
            for file in (base / tf).glob("*.json"):
                if file.stem not in by_month:
                    file.unlink()
        counts[tf] = len(candles)
    return counts
