"""Generate all five timeframes of SELF-CONTAINED, SYNTHETIC candles/indicators/signals."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from .config import TIMEFRAMES, SYMBOL


def save_monthly(df: pd.DataFrame, destination: Path) -> None:
    for month, group in df.groupby(df.timestamp_utc.dt.strftime("%Y-%m"), sort=True):
        folder = destination
        folder.mkdir(parents=True, exist_ok=True)
        records = json.loads(group.to_json(orient="records", date_format="iso", date_unit="ms"))
        # pandas emits UTC dates with +00:00 or Z: normalize to seconds for other projects
        for record in records:
            record["timestamp_utc"] = pd.Timestamp(record["timestamp_utc"]).strftime("%Y-%m-%dT%H:%M:%SZ")
            if "decision_time_utc" in record and record["decision_time_utc"]:
                record["decision_time_utc"] = pd.Timestamp(record["decision_time_utc"]).strftime("%Y-%m-%dT%H:%M:%SZ")
        with (folder / f"{month}.json").open("w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, allow_nan=False)


def generate_demo(root: Path, n: int = 720) -> dict:
    if n < 80:
        raise ValueError("At least 80 candles required for warm-up")
    root = Path(root)
    count_by_tf = {}
    for j, (tf, seconds) in enumerate(TIMEFRAMES.items()):
        rng = np.random.default_rng(42 + j)
        idx = np.arange(n, dtype=float)
        # Synthetic back-and-forth market, entirely fictitious—not exchange observations.
        close = 100000 + 950*np.sin(idx*0.087) + 230*np.sin(idx*0.018) + idx*.11 + rng.normal(0, 95, n)
        opn = np.r_[close[0]-25, close[:-1]]
        high = np.maximum(opn,close) + rng.uniform(10, 88, n)
        low = np.minimum(opn,close) - rng.uniform(10, 88, n)
        vol = rng.uniform(10,150,n)
        last = pd.Timestamp("2026-10-30T12:00:00Z")
        times = pd.date_range(end=last, periods=n, freq=pd.Timedelta(seconds=seconds))
        df = pd.DataFrame({"timestamp_utc": times, "open": opn, "high":high, "low":low, "close":close, "volume":vol})
        c = df.close
        for period in (9, 21, 50):
            df[f"ema_{period}"] = c.ewm(span=period, adjust=False, min_periods=period).mean()
        for period in (20, 50):
            df[f"sma_{period}"] = c.rolling(period, min_periods=period).mean()
        ch = c.diff()
        up = ch.clip(lower=0).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
        down = (-ch.clip(upper=0)).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
        df["rsi_14"] = 100 - 100/(1+up/down.replace(0,np.nan))
        ema12 = c.ewm(span=12, adjust=False, min_periods=12).mean()
        ema26 = c.ewm(span=26, adjust=False, min_periods=26).mean()
        df["macd"] = ema12-ema26
        df["macd_signal"] = df.macd.ewm(span=9, adjust=False, min_periods=9).mean()
        df["macd_histogram"] = df.macd - df.macd_signal
        df["bb_middle"] = df.sma_20
        std = c.rolling(20,min_periods=20).std(ddof=0)
        df["bb_upper"] = df.bb_middle + 2*std
        df["bb_lower"] = df.bb_middle - 2*std
        prior = c.shift(1)
        true_range = pd.concat([(df.high-df.low),(df.high-prior).abs(),(df.low-prior).abs()],axis=1).max(axis=1)
        df["atr_14"] = true_range.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
        crosses_up = (df.ema_9.shift(1) <= df.ema_21.shift(1)) & (df.ema_9 > df.ema_21)
        crosses_down = (df.ema_9.shift(1) >= df.ema_21.shift(1)) & (df.ema_9 < df.ema_21)
        buying = crosses_up & df.rsi_14.between(50,75)
        selling = crosses_down & df.rsi_14.between(25,50)
        signals = df[["timestamp_utc", "close", "ema_9", "ema_21", "rsi_14"]].copy()
        signals["decision_time_utc"] = signals.timestamp_utc + pd.Timedelta(seconds=seconds)
        signals["signal"] = np.select([buying,selling],["BUY","SELL"],default="HOLD")
        signals["reason"] = np.select([buying,selling],["BULLISH_EMA_CROSSOVER_RSI_CONFIRMED","BEARISH_EMA_CROSSOVER_RSI_CONFIRMED"],default="NO_VALID_CROSSOVER")
        signals["gap_before"] = False
        candle_dest = root/"candles"/SYMBOL/tf
        indicator_dest = root/"indicators"/SYMBOL/tf
        signal_dest = root/"signals"/SYMBOL/tf
        save_monthly(df[["timestamp_utc","open","high","low","close","volume"]],candle_dest)
        save_monthly(df,indicator_dest)
        save_monthly(signals,signal_dest)
        count_by_tf[tf] = {"candles": n, "BUY": int(buying.sum()), "SELL": int(selling.sum())}
    (root / "SYNTHETIC_DATA_NOTICE.txt").write_text(
        "SYNTHETIC BTCUSD DEMONSTRATION DATA. NOT REAL DELTA EXCHANGE PRICES. DO NOT TRADE FROM THIS DATA.\n",
        encoding="utf-8")
    return count_by_tf
