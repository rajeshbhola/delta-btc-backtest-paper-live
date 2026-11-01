"""Beginner-readable OHLCV validation. Never fill a gap with fake candles."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import math

from .config import FIELDS, TIMEFRAMES, closed_end, iso_utc, parse_utc


def validate_candle(row: dict, timeframe: str, *, now: datetime) -> tuple[dict | None, str | None]:
    """Return (normalized candle, None) or (None, reason)."""
    if not all(key in row for key in FIELDS):
        return None, "missing_fields"
    try:
        dt = parse_utc(str(row["timestamp_utc"]))
    except (ValueError, TypeError, OverflowError):
        return None, "invalid_timestamp"
    seconds = dt.timestamp()
    if seconds != int(seconds) or int(seconds) % TIMEFRAMES[timeframe] != 0:
        return None, "off_grid_timestamp"
    if dt >= closed_end(now, timeframe):
        return None, "unclosed_or_future_candle"
    try:
        values = {key: float(row[key]) for key in FIELDS[1:]}
    except (TypeError, ValueError, OverflowError):
        return None, "invalid_number"
    if not all(math.isfinite(x) for x in values.values()):
        return None, "non_finite_number"
    o, h, l, c, v = (values[k] for k in FIELDS[1:])
    if min(o, h, l, c) <= 0 or h < max(o, l, c) or l > min(o, h, c):
        return None, "invalid_ohlc"
    if v < 0:
        return None, "negative_volume"
    return {"timestamp_utc": iso_utc(dt), **values}, None


def clean_rows(raw: list[dict], timeframe: str, *, now: datetime, patches: list[dict] | None = None) -> tuple[list[dict], dict]:
    """Sort, validate, remove bad records, deduplicate, then apply valid API patches.

    Duplicates keep the LAST valid record. For equal timestamps, valid repair
    rows override raw rows. Raw files are never edited by this function.
    """
    failures: Counter = Counter()
    kept: dict[str, dict] = {}
    duplicates = 0
    out_of_order = 0
    previous_seconds = None
    patch_count = 0
    samples = []
    for source_name, rows in (("raw", raw), ("repair", patches or [])):
        for pos, row in enumerate(rows):
            record, problem = validate_candle(row, timeframe, now=now)
            if problem:
                failures[problem] += 1
                if len(samples) < 15:
                    samples.append({"source": source_name, "index": pos, "reason": problem, "timestamp_utc": str(row.get("timestamp_utc"))[:80]})
                continue
            seconds = int(parse_utc(record["timestamp_utc"]).timestamp())
            if source_name == "raw":
                if previous_seconds is not None and seconds < previous_seconds:
                    out_of_order += 1
                previous_seconds = seconds
            if record["timestamp_utc"] in kept:
                duplicates += 1
            if source_name == "repair":
                patch_count += 1
            kept[record["timestamp_utc"]] = record
    cleaned = sorted(kept.values(), key=lambda x: x["timestamp_utc"])
    jumps = []
    prev = None
    for record in cleaned:
        if prev:
            move = abs(record["close"] / prev["close"] - 1)
            if move > 0.10 and len(jumps) < 15:
                jumps.append({"timestamp_utc": record["timestamp_utc"], "move_pct": round(move * 100, 3)})
        prev = record
    stats = {
        "raw_rows": len(raw), "repair_rows": len(patches or []),
        "clean_rows": len(cleaned), "duplicate_rows": duplicates,
        "out_of_order_raw_rows": out_of_order, "accepted_repair_rows": patch_count,
        "rejected_rows": sum(failures.values()), "rejections_by_reason": dict(sorted(failures.items())),
        "bad_row_examples": samples, "large_price_move_warnings": jumps,
    }
    return cleaned, stats
