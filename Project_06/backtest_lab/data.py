"""Load monthly JSON from Projects 1-5 (or bundled standalone demo)."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json
import re
import numpy as np
import pandas as pd
from .config import TIMEFRAMES, SYMBOL

MONTH = re.compile(r"\d{4}-(0[1-9]|1[0-2])\.json$")


def find_base(source: str | Path, kind: str) -> Path:
    source = Path(source).expanduser().resolve()
    if kind == "candles":
        candidates = [source / s / SYMBOL for s in ("clean", "candles", "indicators", "raw" )] + [source / SYMBOL]
        labels = "clean, candles, indicators or raw"
    elif kind == "signals":
        candidates = [source / "signals" / SYMBOL, source / SYMBOL]
        labels = "signals"
    else:
        raise ValueError(kind)
    for base in candidates:
        if base.is_dir() and any((base / tf).is_dir() for tf in TIMEFRAMES):
            return base
    raise FileNotFoundError(f"Cannot locate {kind} under {source}: expected {labels}/BTCUSD/<timeframe>/YYYY-MM.json")


def load_json_months(source: str | Path, kind: str, timeframe: str) -> pd.DataFrame:
    if timeframe not in TIMEFRAMES:
        raise ValueError("Invalid timeframe")
    base = find_base(source, kind)
    files = [p for p in sorted((base / timeframe).glob("*.json")) if MONTH.fullmatch(p.name)]
    if not files:
        raise FileNotFoundError(f"No {timeframe} monthly JSON found in {base}")
    data = []
    for file in files:
        rows = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError(f"Expected JSON array in {file}")
        if any(not isinstance(r, dict) for r in rows):
            raise ValueError(f"Expected records in {file}")
        for record in rows:
            if "timestamp_utc" not in record:
                raise ValueError(f"Record missing timestamp_utc in {file}")
            if not str(record["timestamp_utc"]).startswith(file.stem):
                raise ValueError(f"Wrong UTC month for candle in {file}: {record['timestamp_utc']}")
        data.extend(rows)
    if not data:
        return pd.DataFrame(columns=["timestamp_utc"])
    df = pd.DataFrame(data)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, errors="raise")
    if df["timestamp_utc"].isna().any() or df["timestamp_utc"].duplicated().any():
        raise ValueError(f"Duplicate/missing timestamp_utc in {kind}; use Project 2 to clean data")
    return df.sort_values("timestamp_utc").reset_index(drop=True)


def prepare(candles: pd.DataFrame, signals: pd.DataFrame, timeframe: str, *, as_of: datetime | None = None, days: int | None = None) -> tuple[pd.DataFrame, dict]:
    """Use only completed historical candles. Signals must belong to an exact candle."""
    if timeframe not in TIMEFRAMES:
        raise ValueError("Invalid timeframe")
    if candles.empty:
        raise ValueError("No candles")
    seconds = TIMEFRAMES[timeframe]
    if as_of is None:
        as_of = datetime.now(timezone.utc)
    as_of = pd.Timestamp(as_of)
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    as_of = as_of.tz_convert("UTC")
    df = candles.copy()
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, errors="raise")
    if df["timestamp_utc"].isna().any() or df["timestamp_utc"].duplicated().any():
        raise ValueError("Missing or duplicate candle timestamps")
    df = df.sort_values("timestamp_utc").reset_index(drop=True)
    for field in ("open", "high", "low", "close"):
        if field not in df.columns:
            raise ValueError(f"Candle missing {field}")
        df[field] = pd.to_numeric(df[field], errors="coerce")
    values = df[["open", "high", "low", "close"]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("Invalid candle price; clean using Project 2")
    if ((df["high"] < df[["open", "close", "low"]].max(axis=1)) |
        (df["low"] > df[["open", "close", "high"]].min(axis=1))).any():
        raise ValueError("OHLC data inconsistent; clean using Project 2")
    if "volume" in df.columns and (pd.to_numeric(df["volume"], errors="coerce") < 0).any():
        raise ValueError("Negative volume; clean using Project 2")
    # The bar timestamp is its *opening*; it is safe only after close.
    df = df[df["timestamp_utc"] + pd.Timedelta(seconds=seconds) <= as_of].copy()
    if days is not None:
        if days <= 0:
            raise ValueError("days must be positive")
        # Rolling window relative to last *available* complete historical bar.
        if not df.empty:
            cutoff = df["timestamp_utc"].max() - pd.Timedelta(days=days)
            df = df[df["timestamp_utc"] >= cutoff].copy()
    if df.empty:
        raise ValueError("No completed candles in selected window")
    df = df.reset_index(drop=True)
    df["bar_close_utc"] = df["timestamp_utc"] + pd.Timedelta(seconds=seconds)
    expected = pd.Timedelta(seconds=seconds)
    df["gap_before"] = df["timestamp_utc"].diff().gt(expected).fillna(False)
    differences = df["timestamp_utc"].diff().dropna()
    if (differences < expected).any() or ((differences.dt.total_seconds() % seconds) != 0).any():
        raise ValueError("Misaligned timestamps: expected exact timeframe grid")
    if (df["timestamp_utc"].astype("int64") // 1_000_000_000 % seconds != 0).any():
        raise ValueError("Candle timestamp is not aligned to timeframe")

    if signals.empty:
        signals = pd.DataFrame(columns=["timestamp_utc", "signal"])
    else:
        signals = signals.copy()
        signals["timestamp_utc"] = pd.to_datetime(signals["timestamp_utc"], utc=True, errors="raise")
        if signals["timestamp_utc"].duplicated().any() or signals["timestamp_utc"].isna().any():
            raise ValueError("Missing or duplicate signal timestamps")
        if "signal" not in signals.columns:
            raise ValueError("Missing signal column")
        if not signals["signal"].isin(["BUY", "SELL", "HOLD"]).all():
            raise ValueError("Invalid signal; expected BUY/SELL/HOLD")
        if "decision_time_utc" not in signals.columns:
            raise ValueError("Project 4 signal records require decision_time_utc")
        decision = pd.to_datetime(signals["decision_time_utc"], utc=True, errors="raise")
        if (decision != signals["timestamp_utc"] + expected).any():
            raise ValueError("Signal decision_time_utc must equal candle close time")
    # Keep signals in selected period; left join is deliberate: missing signals => HOLD.
    selected_signals = signals[signals["timestamp_utc"].isin(df["timestamp_utc"])].copy()
    if "close" in selected_signals.columns:
        joined = selected_signals[["timestamp_utc", "close"]].merge(df[["timestamp_utc", "close"]], on="timestamp_utc", suffixes=("_signal", "_candle"))
        mismatch = ~np.isclose(joined["close_signal"], joined["close_candle"], rtol=0, atol=0.011)
        if mismatch.any():
            raise ValueError("Signal close price does not match candle close; data sources are inconsistent")
    df = df.merge(selected_signals[["timestamp_utc", "signal"]], on="timestamp_utc", how="left", validate="one_to_one")
    missing_signal_rows = int(df["signal"].isna().sum())
    df["signal"] = df["signal"].fillna("HOLD")
    # Signals from before a gap cannot open a position after the gap.
    info = {"rows": len(df), "missing_signal_rows": missing_signal_rows,
            "gaps": int(df["gap_before"].sum()),
            "first": df["timestamp_utc"].iloc[0].isoformat(),
            "last": df["timestamp_utc"].iloc[-1].isoformat(),
            "as_of": as_of.isoformat()}
    return df, info
