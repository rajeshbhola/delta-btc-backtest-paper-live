"""Shared market data settings. No API credentials or trading code."""

from datetime import datetime, timezone

REST_URL = "https://api.india.delta.exchange/v2/history/candles"
WS_URL = "wss://public-socket.india.delta.exchange"
INTERVAL_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400}
DEFAULT_TIMEFRAMES = tuple(INTERVAL_SECONDS)
MAX_CANDLES_PER_REQUEST = 2000
COLUMNS = ["timestamp_utc", "open", "high", "low", "close", "volume"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def aligned_open(unix_seconds: int, interval_seconds: int) -> int:
    """UTC candle boundary at or before the timestamp."""
    return unix_seconds // interval_seconds * interval_seconds


def closed_end(now: datetime, timeframe: str) -> datetime:
    if now.tzinfo is None:
        raise ValueError("now must have a timezone")
    seconds = INTERVAL_SECONDS[timeframe]
    return datetime.fromtimestamp(aligned_open(int(now.timestamp()), seconds), timezone.utc)
