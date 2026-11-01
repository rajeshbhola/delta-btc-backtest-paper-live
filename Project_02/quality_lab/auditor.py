"""Find missing candle slots efficiently, storing ranges rather than huge lists."""
from __future__ import annotations

from datetime import datetime, timezone
from .config import TIMEFRAMES, ceil_align, closed_end, iso_utc, parse_utc


def build_audit(cleaned: list[dict], timeframe: str, start: datetime, end: datetime, *, now: datetime) -> dict:
    """Audit half-open [start, end), excluding unfinished candles and off-grid edges."""
    step = TIMEFRAMES[timeframe]
    start_dt = ceil_align(start, timeframe)
    end_dt = min(ceil_align(end, timeframe), closed_end(now, timeframe))
    if end_dt < start_dt:
        end_dt = start_dt
    first = int(start_dt.timestamp())
    upper = int(end_dt.timestamp())
    expected = max(0, (upper - first) // step)
    actual_times = sorted({int(parse_utc(r["timestamp_utc"]).timestamp()) for r in cleaned
                           if first <= int(parse_utc(r["timestamp_utc"]).timestamp()) < upper})
    missing_ranges = []
    missing_samples = []
    cursor = first
    missing = 0
    def gap(lo: int, hi_exclusive: int):
        nonlocal missing
        count = (hi_exclusive - lo) // step
        if count <= 0:
            return
        missing += count
        if len(missing_ranges) < 1000:
            missing_ranges.append({"start_utc": iso_utc(datetime.fromtimestamp(lo, timezone.utc)),
                "end_utc": iso_utc(datetime.fromtimestamp(hi_exclusive - step, timezone.utc)),
                "count": count})
        if len(missing_samples) < 20:
            for ts in range(lo, min(hi_exclusive, lo + (20 - len(missing_samples)) * step), step):
                missing_samples.append(iso_utc(datetime.fromtimestamp(ts, timezone.utc)))
    for ts in actual_times:
        if ts > cursor:
            gap(cursor, ts)
        cursor = ts + step
    if cursor < upper:
        gap(cursor, upper)
    return {
        "window_start_utc": iso_utc(start_dt), "window_end_exclusive_utc": iso_utc(end_dt),
        "expected": expected, "present": len(actual_times), "missing": missing,
        "coverage_pct": round(len(actual_times) / expected * 100, 3) if expected else 100.0,
        "gap_count_stored": len(missing_ranges), "gap_ranges_truncated": len(missing_ranges) >= 1000,
        "missing_ranges": missing_ranges, "missing_samples_utc": missing_samples,
    }
