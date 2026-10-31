"""Create unmistakably synthetic candles to preview the UI without API access.

Writes ONLY to demo_data/, never data/. These numbers must not be used for trading.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from delta_collector.config import INTERVAL_SECONDS, DEFAULT_TIMEFRAMES
from delta_collector.storage import CandleStore
from delta_collector.status import CollectorStatus


def build_demo(root: Path | str = "demo_data", periods: int = 250):
    if periods < 2:
        raise ValueError("periods must be >= 2")
    root = Path(root)
    store = CandleStore(root / "candles")
    rng = np.random.default_rng(4321)
    now = datetime.now(timezone.utc)
    progress = {}
    for tf in DEFAULT_TIMEFRAMES:
        step = INTERVAL_SECONDS[tf]
        last_complete_open = (int(now.timestamp()) // step - 1) * step
        begin = last_complete_open - (periods - 1) * step
        stamps = pd.to_datetime([begin + i * step for i in range(periods)], unit="s", utc=True)
        change = rng.normal(0, 85, size=periods).cumsum()
        close = 100000 + change
        opens = np.r_[close[0], close[:-1]]
        high = np.maximum(opens, close) + rng.uniform(1, 100, size=periods)
        low = np.minimum(opens, close) - rng.uniform(1, 100, size=periods)
        frame = pd.DataFrame({"timestamp_utc": stamps, "open": opens, "high": high,
                              "low": low, "close": close, "volume": rng.uniform(1, 100, size=periods)})
        store.write("BTCUSD", tf, frame)
        progress[tf] = {"state": "DEMO ONLY", "actual": periods, "expected": periods,
                        "missing": 0, "progress_pct": 100}
    status = CollectorStatus(root / "status.json")
    status.update(symbol="BTCUSD", mode="SYNTHETIC DEMO - NOT EXCHANGE DATA",
                  state="demo", timeframes=progress, websocket={"state": "Not connected"})
    return root


if __name__ == "__main__":
    location = build_demo()
    print(f"Synthetic demonstration candles written to {location / 'candles'}")
    print("In dashboard sidebar, set Candle data folder to: demo_data/candles")
    print("DEMO DATA IS SYNTHETIC AND MUST NOT BE USED FOR TRADING/BACKTESTING.")
