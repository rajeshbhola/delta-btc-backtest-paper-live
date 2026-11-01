"""Clearly synthetic, mixed-direction standalone trades."""
from datetime import datetime, timedelta, timezone
import math


def make_demo_trades() -> list[dict]:
    start = datetime(2026, 10, 1, 0, 30, tzinfo=timezone.utc)
    prices = [100000, 100400, 99700, 99200, 99900, 100900, 101300, 100600,
              100100, 101100, 101750, 101050, 100500, 100850, 101600]
    out = []
    cursor = start
    for i in range(len(prices) - 1):
        entry = cursor
        duration = [1, 4, 10, 16][i%4]
        cursor = entry + timedelta(hours=duration + 2)
        side = "LONG" if i % 3 != 1 else "SHORT"
        out.append({"side": side, "entry_price": prices[i],
                    "exit_price": prices[i+1],
                    "entry_time_utc": entry.isoformat().replace("+00:00", "Z"),
                    "exit_time_utc": (entry + timedelta(hours=duration)).isoformat().replace("+00:00", "Z")})
    return out
