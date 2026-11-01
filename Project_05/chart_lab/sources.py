"""Locate and load monthly JSON files from Projects 1–4, with bounded memory use."""
from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from .config import SYMBOL, TIMEFRAMES, INDICATORS

MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}\.json$")


def parse_utc(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp_utc must be an ISO-8601 string")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp_utc must include a timezone offset or Z")
    return dt.astimezone(timezone.utc)


def locate_root(source: str | Path | None, kind: str) -> Path | None:
    """Accept a project output root or an explicit BTCUSD directory."""
    if not source:
        return None
    root = Path(source).expanduser()
    aliases = {
        "candles": ["candles", "clean", "raw", "indicators"],
        "indicators": ["indicators"],
        "signals": ["signals"],
    }
    if kind not in aliases:
        raise ValueError(f"Invalid data kind: {kind}")
    choices = [root / kind / SYMBOL]
    choices += [root / folder / SYMBOL for folder in aliases[kind]]
    choices += [root / SYMBOL, root]
    for candidate in choices:
        if candidate.is_dir() and any((candidate / t).is_dir() for t in TIMEFRAMES):
            return candidate
    return None


def month_files(root: Path | None, timeframe: str) -> list[Path]:
    if timeframe not in TIMEFRAMES:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    if root is None:
        return []
    directory = root / timeframe
    if not directory.is_dir():
        return []
    return sorted((p for p in directory.iterdir() if p.is_file() and MONTH_PATTERN.fullmatch(p.name)))


def latest_timestamp(root: Path | None, timeframe: str) -> datetime | None:
    """Read only most recent nonempty month, not the complete year."""
    for path in reversed(month_files(root, timeframe)):
        try:
            with path.open(encoding="utf-8") as fh:
                entries = json.load(fh)
            if not isinstance(entries, list):
                continue
            dates = [parse_utc(x["timestamp_utc"]) for x in entries if isinstance(x, dict) and "timestamp_utc" in x]
            if dates:
                return max(dates)
        except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError):
            continue
    return None


def load_range(
    root: Path | None,
    timeframe: str,
    start: datetime,
    end: datetime,
    limit: int = 1500,
) -> tuple[pd.DataFrame, dict]:
    """Load last `limit` records inside [start, end); read newest monthly files first."""
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("UTC-aware start and end are required")
    if end <= start:
        raise ValueError("end must be after start")
    if not 1 <= limit <= 10000:
        raise ValueError("limit must be between 1 and 10000")
    entries: list[dict] = []
    files_read = 0
    invalid = 0
    for path in reversed(month_files(root, timeframe)):
        first_day = datetime.strptime(path.stem, "%Y-%m").replace(tzinfo=timezone.utc)
        next_month = (pd.Timestamp(first_day) + pd.offsets.MonthBegin(1)).to_pydatetime()
        if next_month <= start or first_day >= end:
            continue
        with path.open(encoding="utf-8") as fh:
            monthly = json.load(fh)
        if not isinstance(monthly, list):
            raise ValueError(f"Expected JSON array in {path}")
        files_read += 1
        accepted = []
        for record in monthly:
            if not isinstance(record, dict):
                invalid += 1
                continue
            try:
                timestamp = parse_utc(record["timestamp_utc"])
                if start <= timestamp < end:
                    accepted.append((timestamp, record))
            except (KeyError, TypeError, ValueError):
                invalid += 1
        accepted.sort(key=lambda pair: pair[0], reverse=True)
        entries.extend(item for _, item in accepted[:max(0, limit - len(entries))])
        if len(entries) >= limit:
            break
    if not entries:
        return pd.DataFrame(), {"files_read": files_read, "invalid_timestamps": invalid, "rows": 0, "cap": limit}
    data = pd.DataFrame(entries)
    data["timestamp_utc"] = pd.to_datetime(data["timestamp_utc"], utc=True, errors="coerce")
    data = data.dropna(subset=["timestamp_utc"]).sort_values("timestamp_utc")
    data = data.drop_duplicates(subset=["timestamp_utc"], keep="last").reset_index(drop=True)
    for field in ["open", "high", "low", "close", "volume", *INDICATORS]:
        if field in data:
            data[field] = pd.to_numeric(data[field], errors="coerce")
    return data, {"files_read": files_read, "invalid_timestamps": invalid, "rows": len(data), "cap": limit}


def combine_candles_and_indicators(candles: pd.DataFrame, indicators: pd.DataFrame) -> pd.DataFrame:
    """Candles are canonical; indicators are joined strictly on candle opening time."""
    if candles.empty:
        return indicators.copy()
    if indicators.empty:
        return candles.copy()
    cols = ["timestamp_utc"] + [key for key in INDICATORS if key in indicators]
    merged = candles.drop(columns=[col for col in INDICATORS if col in candles], errors="ignore").merge(
        indicators[cols], on="timestamp_utc", how="left", validate="one_to_one"
    )
    return merged


def candle_price_conflicts(candles: pd.DataFrame, indicators: pd.DataFrame, relative_tolerance: float=0.000001) -> int:
    if candles.empty or indicators.empty or "close" not in candles or "close" not in indicators:
        return 0
    paired = candles[["timestamp_utc", "close"]].merge(
        indicators[["timestamp_utc", "close"]], on="timestamp_utc", suffixes=("_c", "_i")
    ).dropna()
    if paired.empty:
        return 0
    diff = (paired.close_c-paired.close_i).abs()
    return int((diff > paired.close_c.abs().clip(lower=1)*relative_tolerance).sum())
