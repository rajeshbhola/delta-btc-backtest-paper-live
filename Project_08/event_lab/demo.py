"""Deterministic synthetic market data. Not actual Bitcoin prices or strategy performance."""
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from .data import INTERVALS, dump_json, iso


def generate(output="demo_data"):
    root = Path(output)
    for tf, step in INTERVALS.items():
        start = datetime(2026, 9, 25, tzinfo=timezone.utc)
        last = 101000.0
        candle_files, signal_files = {}, {}
        for i in range(720):
            at = start+timedelta(seconds=i*step)
            # An intentional gap in 5-minute data to demonstrate pending-order cancellation.
            if tf == "5m" and i == 310:
                continue
            movement = 25*math.sin(i/11) + 11*math.sin(i/3) + (0.8 if i%120 < 60 else -0.8)
            price = max(1000, last+movement)
            row = {"timestamp_utc": iso(at), "open": round(last, 5),
                   "high": round(max(last, price)+12.5, 5), "low": round(min(last, price)-12.5, 5),
                   "close": round(price, 5), "volume": round(18+5*(1+math.sin(i/7)), 5)}
            month = at.strftime("%Y-%m")
            candle_files.setdefault(month, []).append(row)
            signal = "HOLD"
            if i % 80 == 15:
                signal = "BUY"
            elif i % 80 == 55:
                signal = "SELL"
            signal_files.setdefault(month, []).append({"timestamp_utc": iso(at),
                   "decision_time_utc": iso(at+timedelta(seconds=step)),
                   "signal": signal,
                   "reason": "DEMO_ONLY_PRESET_SIGNAL" if signal != "HOLD" else "NO_CROSSOVER",
                   "gap_before": tf == "5m" and i == 311})
            last = price
        for month, rows in candle_files.items():
            dump_json(root/"candles"/"BTCUSD"/tf/f"{month}.json", rows)
        for month, rows in signal_files.items():
            dump_json(root/"signals"/"BTCUSD"/tf/f"{month}.json", rows)
    dump_json(root/"DEMO_NOTICE.json", {"synthetic": True, "note": "NOT real BTC market data. Demonstration signals are deliberately preset."})

if __name__ == "__main__":
    generate()
