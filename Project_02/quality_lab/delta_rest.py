"""Optional Delta India public REST downloader and targeted gap repair.

Only historical candle GET requests. Never uses trading credentials.
"""
from __future__ import annotations

from datetime import datetime, timezone
import random
import time
from typing import Iterator

import requests

from .config import TIMEFRAMES, MAX_API_CANDLES, REST_URL, iso_utc, parse_utc, closed_end


def pages(start: datetime, end: datetime, timeframe: str) -> Iterator[tuple[int, int]]:
    """Inclusive (start,end) Unix seconds, up to 2000 candle slots per page.

    The input window is half-open [start,end). The current unfinished candle
    must not be included.
    """
    step = TIMEFRAMES[timeframe]
    a = (int(start.timestamp()) + step - 1) // step * step
    b = int(end.timestamp()) // step * step
    for lo in range(a, b, step * MAX_API_CANDLES):
        yield lo, min(lo + step * (MAX_API_CANDLES - 1), b - step)


class DeltaPublicClient:
    def __init__(self, *, session: requests.Session | None = None, attempts: int = 5,
                 pause: float = .25, sleep=time.sleep):
        self.session = session or requests.Session()
        self._owns_session = session is None
        self.attempts = attempts
        self.pause = pause
        self.sleep = sleep

    def close(self):
        if self._owns_session:
            self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def get(self, timeframe: str, start_ts: int, end_ts: int) -> list[dict]:
        """Return normalized records with Unix timestamps converted to UTC strings."""
        from .config import SYMBOL
        for attempt in range(self.attempts):
            try:
                r = self.session.get(
                    REST_URL,
                    params={"symbol": SYMBOL, "resolution": timeframe, "start": start_ts, "end": end_ts},
                    headers={"Accept": "application/json", "User-Agent": "BTC-Quality-Lab-Educational/1.0"},
                    timeout=(5, 30),
                )
            except (requests.Timeout, requests.ConnectionError):
                if attempt + 1 >= self.attempts:
                    raise
                self.sleep(min(20, 2 ** attempt))
                continue
            if r.status_code == 429 or 500 <= r.status_code <= 599:
                if attempt + 1 >= self.attempts:
                    r.raise_for_status()
                delay = min(30., float(2 ** attempt))
                # Only use a bounded rate-limit reset if server provides valid data.
                if r.status_code == 429:
                    try:
                        reset_ms = float(r.headers.get("X-RATE-LIMIT-RESET", ""))
                        delay = max(1.0, min(300.0, reset_ms / 1000.0 + 1.0))
                    except (TypeError, ValueError):
                        pass
                self.sleep(delay)
                continue
            r.raise_for_status()
            payload = r.json()
            if not isinstance(payload, dict) or payload.get("success") is not True or not isinstance(payload.get("result"), list):
                raise ValueError(f"Unexpected Delta response: {str(payload)[:200]}")
            normalized = []
            step = TIMEFRAMES[timeframe]
            for row in payload["result"]:
                if not all(k in row for k in ("time", "open", "high", "low", "close", "volume")):
                    raise ValueError("Delta response omitted an OHLCV field")
                ts = int(row["time"])
                if ts != float(row["time"]) or ts >= 100_000_000_000 or ts % step:
                    raise ValueError("Unexpected API timestamp format or candle boundary")
                if not start_ts <= ts <= end_ts:
                    continue
                normalized.append({"timestamp_utc": iso_utc(datetime.fromtimestamp(ts, timezone.utc)),
                                   **{key: row[key] for key in ("open", "high", "low", "close", "volume")}})
            if self.pause:
                self.sleep(self.pause)
            return normalized
        raise RuntimeError("Delta fetch failed after retries")


def recent_raw_timestamp(rows: list[dict], timeframe: str, now: datetime) -> datetime | None:
    """Ignore malformed timestamps when determining where to resume."""
    candidates = []
    for row in rows:
        try:
            dt = parse_utc(str(row["timestamp_utc"]))
            if dt < closed_end(now, timeframe) and dt.timestamp() % TIMEFRAMES[timeframe] == 0:
                candidates.append(dt)
        except (ValueError, KeyError, TypeError, OverflowError):
            continue
    return max(candidates, default=None)
