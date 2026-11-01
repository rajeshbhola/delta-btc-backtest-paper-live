"""Load monthly Project 1/2/3 OHLCV JSON into a normalized DataFrame."""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd

INTERVAL_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400}


def find_candle_dir(root: str | Path, timeframe: str) -> Path:
    if timeframe not in INTERVAL_SECONDS:
        raise ValueError(f"Unknown timeframe: {timeframe}")
    root = Path(root)
    options = [
        root / "clean" / "BTCUSD" / timeframe,
        root / "indicators" / "BTCUSD" / timeframe,
        root / "candles" / "BTCUSD" / timeframe,
        root / "BTCUSD" / timeframe,
        root / timeframe,
    ]
    for path in options:
        if path.is_dir() and list(path.glob("????-??.json")):
            return path
    raise FileNotFoundError(f"Monthly BTCUSD {timeframe} JSON not found under {root}. Checked: {options}")


def load_candles(root: str | Path, timeframe: str, max_candles: int = 0) -> pd.DataFrame:
    """Load candle data. Raises on gaps/duplicates instead of manufacturing bars.

    max_candles=0 processes all available bars; positive values retain latest bars.
    """
    directory = find_candle_dir(root, timeframe)
    files = sorted(directory.glob("????-??.json"))
    if max_candles > 0:
        # Read newest month first to minimize I/O when user selects a recent slice.
        selected, count = [], 0
        for file in reversed(files):
            selected.append(file)
            data = json.loads(file.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                raise ValueError(f"Expected list of candles: {file}")
            count += len(data)
            if count >= max_candles:
                break
        files = sorted(selected)
    records = []
    for file in files:
        payload = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"Expected list of candles in {file}")
        records.extend(payload)
    if not records:
        raise ValueError("No historical candles found")
    df = pd.DataFrame(records)
    required = {"timestamp_utc", "open", "high", "low", "close", "volume"}
    if not required.issubset(df.columns):
        raise ValueError(f"Missing OHLCV fields: {sorted(required - set(df.columns))}")
    df = df[list(required)]
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce")
    for field in ("open", "high", "low", "close", "volume"):
        df[field] = pd.to_numeric(df[field], errors="coerce")
    df = df.sort_values("timestamp_utc", kind="stable").reset_index(drop=True)
    if max_candles > 0:
        df = df.tail(max_candles).reset_index(drop=True)
    if df["timestamp_utc"].isna().any() or df[["open", "high", "low", "close", "volume"]].isna().any().any():
        raise ValueError("Invalid or missing timestamp/OHLCV value. Clean Project 2 data first.")
    if df["timestamp_utc"].duplicated().any():
        raise ValueError("Duplicate candles detected; use Project 2 to clean them")
    if (df[["open", "high", "low", "close"]] <= 0).any().any() or (df["volume"] < 0).any():
        raise ValueError("Non-positive prices or negative volume detected")
    if ((df["high"] < df[["open", "close", "low"]].max(axis=1)) | (df["low"] > df[["open", "close", "high"]].min(axis=1))).any():
        raise ValueError("Invalid OHLC relationship detected")
    expected = INTERVAL_SECONDS[timeframe]
    deltas = df["timestamp_utc"].diff().dropna().dt.total_seconds().to_numpy()
    if not np.all(deltas == expected):
        mismatches = int(np.count_nonzero(deltas != expected))
        raise ValueError(f"Found {mismatches} missing/irregular candle interval(s). Repair gaps using Project 2.")
    return df
