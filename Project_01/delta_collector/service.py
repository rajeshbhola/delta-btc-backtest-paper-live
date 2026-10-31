"""Resumable year-long REST backfill and incremental updates."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import INTERVAL_SECONDS, closed_end, utc_now
from .rest import DeltaRestClient
from .storage import CandleStore
from .status import CollectorStatus

LOG = logging.getLogger(__name__)


class CandleService:
    def __init__(self, rest: DeltaRestClient, store: CandleStore, symbol: str = "BTCUSD",
                 status: CollectorStatus | None = None):
        self.rest, self.store, self.symbol, self.status = rest, store, symbol, status

    def sync(self, timeframe: str, start: datetime, end: datetime, *, resume: bool = True) -> int:
        """Persist every REST page immediately; restart continues from latest saved candle."""
        if timeframe not in INTERVAL_SECONDS:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("start/end must be timezone-aware")
        end = min(end, closed_end(utc_now(), timeframe))
        if end <= start:
            return 0
        step = INTERVAL_SECONDS[timeframe]
        if resume:
            latest = self.store.latest_time(self.symbol, timeframe)
            if latest is not None:
                # Overlap the last three closed candles for minor exchange revisions.
                start = max(start, latest - timedelta(seconds=2 * step))
        if end <= start:
            return 0
        total_received = 0
        if self.status:
            self.status.update(current_timeframe=timeframe)
            self.status.timeframe(timeframe, state="fetching", received=0, pages=0,
                                  window_start_utc=start.isoformat(), window_end_utc=end.isoformat())
        for page_no, df in enumerate(self.rest.iter_pages(self.symbol, timeframe, start, end), 1):
            if not df.empty:
                self.store.write(self.symbol, timeframe, df)
            total_received += len(df)
            if self.status:
                latest = self.store.latest_time(self.symbol, timeframe)
                progress = (max(0, min(100, 100 * (latest.timestamp() - start.timestamp()) /
                                                (end.timestamp() - start.timestamp())))
                            if latest else 0)
                self.status.timeframe(timeframe, state="fetching", received=total_received,
                                      pages=page_no, progress_pct=round(progress, 1),
                                      last_saved_utc=latest.isoformat() if latest else None)
            if page_no % 10 == 0 or page_no == 1:
                LOG.info("REST %s page %s: %s rows, %s rows fetched so far",
                         timeframe, page_no, len(df), total_received)
        LOG.info("REST %s sync complete: %s candles received", timeframe, total_received)
        if self.status:
            self.status.timeframe(timeframe, state="synced", received=total_received,
                                  progress_pct=100)
        return total_received

    def sync_recent(self, timeframe: str, *, lookback_days_if_empty: int = 1) -> int:
        end = closed_end(utc_now(), timeframe)
        last = self.store.latest_time(self.symbol, timeframe)
        start = (last - timedelta(seconds=2 * INTERVAL_SECONDS[timeframe]) if last
                 else end - timedelta(days=lookback_days_if_empty))
        return self.sync(timeframe, start, end, resume=False)

    def backfill(self, timeframes: tuple[str, ...], days: int = 365, *, end: datetime | None = None):
        if days <= 0:
            raise ValueError("days must be positive")
        now = end or utc_now()
        for tf in timeframes:
            final_end = closed_end(now, tf)
            start = final_end - timedelta(days=days)
            LOG.info("Backfill BTC %s [%s, %s), days=%s", tf, start.isoformat(), final_end.isoformat(), days)
            self.sync(tf, start, final_end, resume=True)
            report = self.store.audit(self.symbol, tf, start, final_end)
            LOG.info("AUDIT %s: %s/%s saved, %s missing", tf,
                     report["actual"], report["expected"], report["missing"])
            if self.status:
                self.status.timeframe(tf, state="complete", expected=report["expected"],
                                      actual=report["actual"], missing=report["missing"],
                                      progress_pct=100)
