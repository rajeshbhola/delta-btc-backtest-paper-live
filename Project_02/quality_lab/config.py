"""Project settings. Only public BTCUSD candle data is used."""
from datetime import datetime, timezone

SYMBOL = "BTCUSD"
TIMEFRAMES = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400}
FIELDS = ("timestamp_utc", "open", "high", "low", "close", "volume")
REST_URL = "https://api.india.delta.exchange/v2/history/candles"
MAX_API_CANDLES = 2000


def parse_utc(value: str) -> datetime:
    """Require an explicit UTC offset (Z or +00:00); do not guess local time."""
    value = value.strip()
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Dates must include a timezone. Example: 2026-10-01T00:00:00Z")
    return dt.astimezone(timezone.utc)


def iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        raise ValueError("Datetime must be timezone-aware")
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def closed_end(now: datetime, timeframe: str) -> datetime:
    """Open time of current candle; only earlier candle opens are fully closed."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    step = TIMEFRAMES[timeframe]
    seconds = int(now.timestamp())
    return datetime.fromtimestamp(seconds // step * step, timezone.utc)


def ceil_align(dt: datetime, timeframe: str) -> datetime:
    step = TIMEFRAMES[timeframe]
    ts = dt.timestamp()
    import math
    return datetime.fromtimestamp(math.ceil(ts / step) * step, timezone.utc)
