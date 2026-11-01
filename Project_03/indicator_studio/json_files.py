"""Read Project 2 clean candle files; write Project 3 results as monthly JSON."""
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


def find_candle_base(source: str | Path) -> Path:
    """Accept Project 2 root, clean/, or Project 1 candles/ as input."""
    source = Path(source).expanduser().resolve()
    options = (
        source / "clean" / SYMBOL,
        source / "data" / "clean" / SYMBOL,
        source / SYMBOL,
        source / "candles" / SYMBOL,
        source / "data" / "candles" / SYMBOL,
    )
    for base in options:
        if base.is_dir() and any((base / tf).is_dir() for tf in TIMEFRAMES):
            return base
    raise FileNotFoundError(
        f"No candles found beneath {source}. Expected clean/BTCUSD/<timeframe>/YYYY-MM.json "
        "(Project 2) or candles/BTCUSD/<timeframe>/YYYY-MM.json (Project 1)."
    )


def monthly_files(base: Path, timeframe: str) -> list[Path]:
    if timeframe not in TIMEFRAMES:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    return sorted(x for x in (base / timeframe).glob("*.json") if MONTH_FILE.fullmatch(x.name))


def read_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as file:
        rows = json.load(file)
    if not isinstance(rows, list) or any(not isinstance(x, dict) for x in rows):
        raise ValueError(f"Expected JSON array of candle objects in {path}")
    return rows


def utc_timestamp(row: dict, timeframe: str) -> datetime:
    try:
        s = str(row["timestamp_utc"])
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("timestamp must include UTC offset")
        dt = dt.astimezone(timezone.utc)
        if int(dt.timestamp()) % TIMEFRAMES[timeframe] != 0 or dt.microsecond != 0:
            raise ValueError("timestamp not aligned to timeframe")
        values = [float(row[f]) for f in ("open", "high", "low", "close", "volume")]
        o, h, l, c, v = values
        if not all(math.isfinite(n) for n in values):
            raise ValueError("non-finite OHLCV")
        if min(o, h, l, c) <= 0 or v < 0 or h < max(o, l, c) or l > min(o, h, c):
            raise ValueError("invalid OHLCV prices or volume")
        return dt
    except (KeyError, TypeError, ValueError, OverflowError) as e:
        raise ValueError(f"Invalid candle {row!r}: {e}") from e


def write_json(path: Path, obj: object) -> None:
    """Atomic JSON write: dashboard does not see an incomplete file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                     prefix=".new-", suffix=".json", delete=False) as f:
            tmp = f.name
            json.dump(obj, f, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def read_latest(output_root: str | Path, timeframe: str, limit: int = 500) -> list[dict]:
    """Dashboard reads only the last N rows, not the whole one-year dataset."""
    base = Path(output_root) / "indicators" / SYMBOL
    recent = []
    for path in reversed(monthly_files(base, timeframe)):
        recent[:0] = read_rows(path)[-limit:]
        if len(recent) >= limit:
            return recent[-limit:]
    return recent[-limit:]
