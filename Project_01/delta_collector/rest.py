"""Fetch and validate closed BTCUSD OHLCV candles using public Delta REST API."""
from __future__ import annotations

import logging
import random
import time
from datetime import datetime
from typing import Callable, Iterator

import pandas as pd
import requests

from .config import (
    COLUMNS, INTERVAL_SECONDS, MAX_CANDLES_PER_REQUEST, REST_URL, aligned_open,
)

LOGGER = logging.getLogger(__name__)


def empty_candles() -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp_utc": pd.Series(dtype="datetime64[ns, UTC]"),
        **{field: pd.Series(dtype="float64") for field in COLUMNS[1:]},
    })


def normalize_rest(rows: list[dict], timeframe: str, start_ts: int, end_exclusive: int) -> pd.DataFrame:
    """Validate, deduplicate, and normalize API output. All timestamps are UTC."""
    if not rows:
        return empty_candles()
    required = {"time", "open", "high", "low", "close", "volume"}
    df = pd.DataFrame(rows)
    if not required.issubset(df.columns):
        raise ValueError(f"Missing OHLCV fields: {sorted(required - set(df.columns))}")
    for field in required:
        df[field] = pd.to_numeric(df[field], errors="raise")
    if df[list(required)].isnull().any().any():
        raise ValueError("Null candle fields returned by Delta")
    # Official historical candle timestamps are in seconds (WS uses microseconds).
    if (df["time"] % 1 != 0).any():
        raise ValueError("REST timestamps must be whole Unix seconds")
    if (df["time"].abs() >= 10**11).any():
        raise ValueError("REST candle timestamps must be Unix seconds, not microseconds")
    df["time"] = df["time"].astype("int64")
    df = df.loc[(df["time"] >= start_ts) & (df["time"] < end_exclusive)]
    df = df.drop_duplicates(subset="time", keep="last").sort_values("time").copy()
    if df.empty:
        return empty_candles()
    step = INTERVAL_SECONDS[timeframe]
    if (df["time"] % step != 0).any():
        raise ValueError("REST candle open times are not on UTC candle boundaries")
    if ((df["high"] < df[["open", "close", "low"]].max(axis=1)).any()
            or (df["low"] > df[["open", "close", "high"]].min(axis=1)).any()
            or (df["volume"] < 0).any()):
        raise ValueError("Invalid OHLCV candle: high/low/volume inconsistent")
    df["timestamp_utc"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df[COLUMNS].reset_index(drop=True)


def candle_pages(start: datetime, end: datetime, timeframe: str) -> Iterator[tuple[int, int, int]]:
    """Yield (start_inclusive, end_inclusive, end_exclusive) pages, <= 2000 candles.

    Caller passes [start,end) and the current still-forming candle is excluded.
    """
    if timeframe not in INTERVAL_SECONDS:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start and end must be timezone-aware")
    if end <= start:
        raise ValueError("end must be later than start")
    step = INTERVAL_SECONDS[timeframe]
    a = (int(start.timestamp()) + step - 1) // step * step
    b = aligned_open(int(end.timestamp()), step)
    for lo in range(a, b, MAX_CANDLES_PER_REQUEST * step):
        hi_exclusive = min(lo + MAX_CANDLES_PER_REQUEST * step, b)
        yield lo, hi_exclusive - step, hi_exclusive


class DeltaRestClient:
    """Read-only HTTP client. Do not add private order/auth endpoints here."""

    def __init__(self, *, timeout: tuple[int, int] = (5, 30), max_attempts: int = 6,
                 request_pause: float = 0.25, session: requests.Session | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.request_pause = request_pause
        self.session = session or requests.Session()
        self._owns_session = session is None
        self.sleep = sleep

    def close(self):
        if self._owns_session:
            self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def get_page(self, symbol: str, timeframe: str, start_ts: int, end_ts: int) -> list[dict]:
        params = {"symbol": symbol, "resolution": timeframe, "start": start_ts, "end": end_ts}
        for attempt in range(self.max_attempts):
            try:
                response = self.session.get(
                    REST_URL, params=params,
                    headers={"Accept": "application/json", "User-Agent": "delta-btc-market-data-study/2.0"},
                    timeout=self.timeout,
                )
            except (requests.ConnectionError, requests.Timeout) as exc:
                if attempt + 1 == self.max_attempts:
                    raise RuntimeError("Delta REST connection failed after retries") from exc
                delay = min(30.0, 2 ** attempt) + random.uniform(0, 0.25)
                LOGGER.warning("REST connection issue; retrying in %.1fs", delay)
                self.sleep(delay)
                continue
            if response.status_code == 429:
                if attempt + 1 == self.max_attempts:
                    response.raise_for_status()
                try:
                    reset_millis = float(response.headers.get("X-RATE-LIMIT-RESET", ""))
                    delay = max(1.0, (reset_millis / 1000.0) + 1.0)
                except (TypeError, ValueError):
                    delay = min(30.0, 2 ** attempt)
                # Delta specifies the reset header in milliseconds. Respect it.
                LOGGER.warning("REST 429; waiting %.1fs for rate-limit reset", delay)
                self.sleep(delay)
                continue
            if 500 <= response.status_code <= 599:
                if attempt + 1 == self.max_attempts:
                    response.raise_for_status()
                delay = min(30.0, 2 ** attempt)
                LOGGER.warning("REST HTTP %s; retrying in %.1fs", response.status_code, delay)
                self.sleep(delay)
                continue
            response.raise_for_status()
            try:
                payload = response.json()
            except ValueError as exc:
                raise RuntimeError("Delta REST returned invalid JSON") from exc
            if (not isinstance(payload, dict) or payload.get("success") is not True
                    or not isinstance(payload.get("result"), list)):
                raise RuntimeError(f"Unexpected Delta response: {str(payload)[:250]}")
            if self.request_pause > 0:
                self.sleep(self.request_pause)
            return payload["result"]
        raise RuntimeError("Exhausted retries")

    def iter_pages(self, symbol: str, timeframe: str, start: datetime, end: datetime):
        for page_start, page_end, page_end_exclusive in candle_pages(start, end, timeframe):
            raw = self.get_page(symbol, timeframe, page_start, page_end)
            yield normalize_rest(raw, timeframe, page_start, page_end_exclusive)

    def fetch_candles(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        pages = list(self.iter_pages(symbol, timeframe, start, end))
        if not pages:
            return empty_candles()
        return pd.concat(pages, ignore_index=True).drop_duplicates("timestamp_utc").sort_values("timestamp_utc").reset_index(drop=True)
