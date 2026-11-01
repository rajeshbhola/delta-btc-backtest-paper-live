"""Generate easy-to-inspect fake candles with deliberate defects for learning."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import random
from .config import TIMEFRAMES, closed_end, iso_utc
from .json_store import JsonStore


def create_demo(store: JsonStore, *, days: int = 2, force: bool = False,
                now: datetime | None = None) -> dict[str, int]:
    if days < 1 or days > 7:
        raise ValueError("Demo --days must be 1 to 7")
    now = now or datetime.now(timezone.utc)
    result = {}
    for i, (tf, seconds) in enumerate(TIMEFRAMES.items()):
        if store.files("raw", tf) and not force:
            raise FileExistsError(f"Raw {tf} files already exist. Use a different --data-dir, or --force to replace demo data.")
        rng = random.Random(500 + i)
        end = closed_end(now, tf)
        start = end - timedelta(days=days)
        price = 100000.0
        rows = []
        for ts in range(int(start.timestamp()), int(end.timestamp()), seconds):
            op = price
            close = op + rng.uniform(-60, 60)
            high = max(op, close) + rng.uniform(2, 35)
            low = min(op, close) - rng.uniform(2, 35)
            rows.append({"timestamp_utc": iso_utc(datetime.fromtimestamp(ts, timezone.utc)),
                         "open": round(op, 2), "high": round(high, 2),
                         "low": round(low, 2), "close": round(close, 2),
                         "volume": round(rng.uniform(1, 100), 3)})
            price = close
        # Intentional defects: a missing candle, an invalid price, a duplicate,
        # and out-of-order records. The cleaner must never synthesize candles.
        if len(rows) >= 7:
            rows.pop(3)
            rows[4]["high"] = 1.0  # impossible high: must be rejected
            rows.append(dict(rows[5]))
            rows[0], rows[1] = rows[1], rows[0]
        store.replace_months("raw", tf, rows, clear_old=True)
        # Demo is self-contained: discard previous repair patches on force.
        if force:
            for path in store.files("repairs", tf):
                path.unlink()
        result[tf] = len(rows)
    return result
