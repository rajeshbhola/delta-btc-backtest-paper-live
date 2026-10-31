"""Monthly JSON candle storage with atomic replacement and gap auditing.

One JSON array of ISO-8601 UTC candle objects per market / interval / month.
No pandas/pyarrow storage engines are required. Single writer per dataset.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from .config import COLUMNS, INTERVAL_SECONDS, aligned_open
from .rest import empty_candles

_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])\.json$")


def _utc_iso(value) -> str:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        raise ValueError("Candle timestamp must include timezone")
    return timestamp.tz_convert("UTC").isoformat().replace("+00:00", "Z")


def atomic_write_json(path: Path, obj: object):
    """Write a complete UTF-8 JSON file, then swap it into place atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.stem}.", suffix=".tmp",
                                         delete=False, newline="\n") as fp:
            temp_path = fp.name
            json.dump(obj, fp, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            fp.write("\n")
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def _frame_from_json(path: Path) -> pd.DataFrame:
    with path.open("r", encoding="utf-8") as fp:
        records = json.load(fp)
    if not isinstance(records, list):
        raise ValueError(f"Expected array of candle objects in {path}")
    if not records:
        return empty_candles()
    df = pd.DataFrame.from_records(records)
    if not set(COLUMNS).issubset(df.columns):
        raise ValueError(f"Invalid candle fields in {path}")
    df = df[COLUMNS]
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, errors="raise")
    for name in COLUMNS[1:]:
        df[name] = pd.to_numeric(df[name], errors="raise").astype("float64")
    return df


def _records(df: pd.DataFrame) -> list[dict]:
    # Explicit, stable JSON schema for external consumers and later projects.
    return [{"timestamp_utc": _utc_iso(row.timestamp_utc),
             "open": float(row.open), "high": float(row.high),
             "low": float(row.low), "close": float(row.close),
             "volume": float(row.volume)}
            for row in df.itertuples(index=False)]


class CandleStore:
    """Single-writer, month-partitioned JSON store for completed OHLCV candles."""

    def __init__(self, root: Path | str = "data/candles"):
        self.root = Path(root)

    def directory(self, symbol: str, timeframe: str) -> Path:
        if not symbol.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Invalid symbol for storage")
        if timeframe not in INTERVAL_SECONDS:
            raise ValueError("Unknown timeframe")
        return self.root / symbol / timeframe

    def _files(self, symbol: str, timeframe: str) -> list[Path]:
        return sorted(p for p in self.directory(symbol, timeframe).glob("????-??.json")
                      if _MONTH.fullmatch(p.name))

    def latest_time(self, symbol: str, timeframe: str) -> datetime | None:
        for path in reversed(self._files(symbol, timeframe)):
            df = _frame_from_json(path)
            if not df.empty:
                return pd.Timestamp(df["timestamp_utc"].max()).to_pydatetime()
        return None

    def write(self, symbol: str, timeframe: str, candles: pd.DataFrame) -> int:
        if candles.empty:
            return 0
        df = candles[COLUMNS].copy()
        df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
        for col in COLUMNS[1:]:
            df[col] = pd.to_numeric(df[col], errors="raise")
        if df[COLUMNS].isna().any().any():
            raise ValueError("JSON candles cannot contain null or NaN fields")
        if df[COLUMNS[1:]].isin([float("inf"), float("-inf")]).any().any():
            raise ValueError("Non-finite candle number")
        if ((df["high"] < df[["open", "close", "low"]].max(axis=1)).any()
                or (df["low"] > df[["open", "close", "high"]].min(axis=1)).any()
                or (df["volume"] < 0).any()):
            raise ValueError("Inconsistent OHLCV data")
        df = df.drop_duplicates("timestamp_utc", keep="last").sort_values("timestamp_utc")
        df["month"] = df["timestamp_utc"].dt.strftime("%Y-%m")
        folder = self.directory(symbol, timeframe)
        folder.mkdir(parents=True, exist_ok=True)
        saved = 0
        for month, group in df.groupby("month", sort=True):
            dest = folder / f"{month}.json"
            group = group.drop(columns="month")
            if dest.exists():
                group = pd.concat([_frame_from_json(dest), group], ignore_index=True)
            group = group.drop_duplicates("timestamp_utc", keep="last").sort_values("timestamp_utc")
            atomic_write_json(dest, _records(group))
            saved += len(group)
        return saved

    def load(self, symbol: str, timeframe: str, start: datetime | None = None,
             end: datetime | None = None) -> pd.DataFrame:
        chunks = []
        for path in self._files(symbol, timeframe):
            month = datetime.strptime(path.stem, "%Y-%m").replace(tzinfo=timezone.utc)
            next_month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
            if start is not None and next_month <= start:
                continue
            if end is not None and month >= end:
                continue
            chunks.append(_frame_from_json(path))
        if not chunks:
            return empty_candles()
        df = pd.concat(chunks, ignore_index=True)
        if start is not None:
            df = df[df["timestamp_utc"] >= start]
        if end is not None:
            df = df[df["timestamp_utc"] < end]
        return df.drop_duplicates("timestamp_utc", keep="last").sort_values("timestamp_utc").reset_index(drop=True)

    def tail(self, symbol: str, timeframe: str, n: int = 500) -> pd.DataFrame:
        """Read only recent monthly files until at least n bars are found."""
        if n < 1:
            raise ValueError("n must be positive")
        chunks = []
        count = 0
        for path in reversed(self._files(symbol, timeframe)):
            df = _frame_from_json(path)
            if not df.empty:
                chunks.append(df)
                count += len(df)
            if count >= n:
                break
        if not chunks:
            return empty_candles()
        result = pd.concat(chunks, ignore_index=True)
        return (result.drop_duplicates("timestamp_utc", keep="last")
                .sort_values("timestamp_utc").tail(n).reset_index(drop=True))

    def audit(self, symbol: str, timeframe: str, start: datetime, end: datetime,
              report_dir: Path | str | None = None) -> dict:
        """Report all missing UTC candle slots; never forward-fill or synthesize bars."""
        step = INTERVAL_SECONDS[timeframe]
        a = (int(start.timestamp()) + step - 1) // step * step
        b = aligned_open(int(end.timestamp()), step)
        expected = (pd.date_range(start=pd.Timestamp(a, unit="s", tz="UTC"),
                                  end=pd.Timestamp(b - step, unit="s", tz="UTC"),
                                  freq=f"{step}s") if a < b else pd.DatetimeIndex([], tz="UTC"))
        df = self.load(symbol, timeframe, start, end)
        actual = pd.DatetimeIndex(df["timestamp_utc"])
        missing = expected.difference(actual)
        summary = {"symbol": symbol, "timeframe": timeframe, "expected": len(expected),
                   "actual": len(actual), "missing": len(missing),
                   "first_missing": missing[0].isoformat() if len(missing) else None,
                   "last_missing": missing[-1].isoformat() if len(missing) else None}
        if report_dir is not None:
            folder = Path(report_dir)
            folder.mkdir(parents=True, exist_ok=True)
            atomic_write_json(folder / f"{symbol}_{timeframe}_missing.json", {
                "summary": summary,
                "missing_timestamps_utc": [_utc_iso(x) for x in missing],
            })
        return summary
