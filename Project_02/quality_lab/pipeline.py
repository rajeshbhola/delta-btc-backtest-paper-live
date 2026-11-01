"""One-step clean + audit + JSON export for a selected timeframe."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from .config import SYMBOL, TIMEFRAMES, iso_utc, closed_end
from .json_store import JsonStore, atomic_json
from .cleaner import clean_rows
from .auditor import build_audit


def process(store: JsonStore, timeframe: str, *, days: int = 365, now: datetime | None = None) -> dict:
    if timeframe not in TIMEFRAMES:
        raise ValueError("Unknown timeframe")
    if not 1 <= days <= 3650:
        raise ValueError("--days must be between 1 and 3650")
    now = now or datetime.now(timezone.utc)
    raw = store.read("raw", timeframe)
    patches = store.read("repairs", timeframe)
    cleaned, stats = clean_rows(raw, timeframe, now=now, patches=patches)
    store.replace_months("clean", timeframe, cleaned, clear_old=True)
    audit_end = closed_end(now, timeframe)
    audit = build_audit(cleaned, timeframe, audit_end - timedelta(days=days), audit_end, now=now)
    report = {"project": "Project 2 - BTC Data Quality Lab", "symbol": SYMBOL,
              "timeframe": timeframe, "processed_at_utc": iso_utc(now),
              "quality": stats, "coverage": audit,
              "warning": "Missing candles are NEVER filled with synthetic OHLCV. Large price moves are only flagged."}
    atomic_json(store.report_path(timeframe), report)
    return report
