"""Deterministic artificial market regime candles for practice. NOT REAL BTC."""
from __future__ import annotations
import json
import random
from pathlib import Path
from datetime import datetime,timedelta,timezone
from .data import INTERVAL_SECONDS


def make_demo(root: str|Path, bars: int = 1500, seed: int = 42) -> None:
    root = Path(root)
    if bars < 10: raise ValueError("Need at least 10 demo candles")
    for idx,(tf,seconds) in enumerate(INTERVAL_SECONDS.items()):
        rng = random.Random(seed + idx)
        start = datetime(2026,2,1,tzinfo=timezone.utc)
        price = 100000.0
        months = {}
        for i in range(bars):
            # Multi-regime artificial trend and volatility. No future actual prices.
            regimes = [0.00050,-0.00047,0.00022,-0.00030,0.00005]
            drift = regimes[(i//300)%len(regimes)]
            shock = rng.gauss(0, 0.0018)
            opening = price
            closing = max(1, opening*(1+drift+shock))
            high = max(opening,closing)*(1+rng.random()*0.0006)
            low = min(opening,closing)*(1-rng.random()*0.0006)
            dt = start + timedelta(seconds=i*seconds)
            record = {"timestamp_utc":dt.strftime("%Y-%m-%dT%H:%M:%SZ"),"open":round(opening,5),"high":round(high,5),"low":round(low,5),"close":round(closing,5),"volume":round(10+rng.random()*90,4)}
            months.setdefault(dt.strftime("%Y-%m"),[]).append(record)
            price = closing
        folder = root/"clean"/"BTCUSD"/tf
        folder.mkdir(parents=True,exist_ok=True)
        for month,records in months.items():
            (folder/(month+".json")).write_text(json.dumps(records,indent=2),encoding="utf-8")
    (root/"SYNTHETIC_DEMO_NOTICE.json").write_text(json.dumps({"synthetic":True,"warning":"Artificial generated OHLCV only. NOT Delta real BTCUSD data.","bars_per_timeframe":bars},indent=2),encoding="utf-8")
