"""Read Project 3 indicator JSON and write monthly Project 4 signal JSON."""
from __future__ import annotations
import json
import math
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from .config import SYMBOL, TIMEFRAMES

MONTH_FILE = re.compile(r"\d{4}-(?:0[1-9]|1[0-2])\.json$")


def find_indicator_base(source: str | Path) -> Path:
    source = Path(source).expanduser().resolve()
    candidates = (
        source / "indicators" / SYMBOL,
        source / "data" / "indicators" / SYMBOL,
        source / SYMBOL,
    )
    for root in candidates:
        if root.is_dir() and any((root / tf).is_dir() for tf in TIMEFRAMES):
            return root
    raise FileNotFoundError(
        f"Indicator JSON not found under {source}. Expected "
        "indicators/BTCUSD/<timeframe>/YYYY-MM.json from Project 3."
    )


def monthly_files(base: Path, timeframe: str) -> list[Path]:
    if timeframe not in TIMEFRAMES:
        raise ValueError(f"Unsupported timeframe {timeframe!r}")
    return sorted(f for f in (base / timeframe).glob("*.json") if MONTH_FILE.fullmatch(f.name))


def read_rows(path: Path) -> list[dict]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        raise ValueError(f"Expected an array of objects in {path}")
    return rows


def parse_candle(row: dict, timeframe: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(row["timestamp_utc"].replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError("Naive timestamps not allowed")
        timestamp = timestamp.astimezone(timezone.utc)
        if timestamp.microsecond or int(timestamp.timestamp()) % TIMEFRAMES[timeframe]:
            raise ValueError("Timestamp not aligned to timeframe boundary")
        prices = [float(row[key]) for key in ("open", "high", "low", "close", "volume")]
        op, hi, lo, close, vol = prices
        if not all(math.isfinite(v) for v in prices):
            raise ValueError("Non-finite OHLCV")
        if min(op, hi, lo, close) <= 0 or vol < 0 or hi < max(op, lo, close) or lo > min(op, hi, close):
            raise ValueError("Invalid OHLCV")
        for field in ("ema_9", "ema_21", "rsi_14"):
            number = row.get(field)
            if number is not None:
                number = float(number)
                if not math.isfinite(number) or (field.startswith("ema") and number <= 0):
                    raise ValueError(f"Invalid {field}")
                if field == "rsi_14" and not 0 <= number <= 100:
                    raise ValueError("RSI must be 0..100")
        return timestamp
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        raise ValueError(f"Invalid indicator candle {row!r}: {exc}") from exc


def save_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=".tmp-", suffix=".json", delete=False
        ) as fp:
            temp = Path(fp.name)
            json.dump(payload, fp, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            fp.write("\n")
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(temp, path)
    finally:
        if temp and temp.exists():
            temp.unlink()


def latest_rows(output: str | Path, timeframe: str, limit: int = 1000) -> list[dict]:
    if limit < 1:
        raise ValueError("limit must be >= 1")
    base = Path(output).expanduser() / "signals" / SYMBOL
    result: list[dict] = []
    for filename in reversed(monthly_files(base, timeframe)):
        result[:0] = read_rows(filename)[-limit:]
        if len(result) >= limit:
            break
    return result[-limit:]
