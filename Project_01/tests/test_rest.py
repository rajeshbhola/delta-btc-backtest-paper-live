from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from delta_collector.rest import DeltaRestClient, candle_pages, normalize_rest


BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def row(ts, *, high=110):
    return {"time": ts, "open": 100, "high": high, "low": 90, "close": 105, "volume": 11}


def test_five_timeframes_and_page_size():
    for tf, step in {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400}.items():
        pages = list(candle_pages(BASE, BASE + timedelta(seconds=2001*step), tf))
        assert len(pages) == 2
        assert pages[0][1] - pages[0][0] == 1999*step
        assert pages[0][2] == pages[1][0]
        assert pages[-1][2] == int((BASE + timedelta(seconds=2001*step)).timestamp())


def test_candle_page_boundary_is_end_exclusive():
    ranges = list(candle_pages(BASE, BASE + timedelta(minutes=61), "1m"))
    assert ranges == [(int(BASE.timestamp()), int(BASE.timestamp()) + 3600, int(BASE.timestamp()) + 3660)]


def test_normalize_sorts_deduplicates_and_bounds():
    ts = int(BASE.timestamp())
    df = normalize_rest([row(ts+120), row(ts), row(ts+60), row(ts+60)], "1m", ts, ts+180)
    assert len(df) == 3
    assert list(df.columns) == ["timestamp_utc", "open", "high", "low", "close", "volume"]
    assert df["timestamp_utc"].is_monotonic_increasing
    assert df["timestamp_utc"].iloc[0] == pd.Timestamp(BASE)


def test_reject_invalid_ohlc():
    ts = int(BASE.timestamp())
    with pytest.raises(ValueError, match="Invalid OHLCV"):
        normalize_rest([row(ts, high=95)], "1m", ts, ts+60)


def test_reject_rest_timestamp_in_microseconds():
    ts = int(BASE.timestamp())
    with pytest.raises(ValueError, match="REST candle"):
        normalize_rest([row(ts*1_000_000)], "1m", ts*1_000_000, ts*1_000_000+60)


def test_no_network_iter_pages():
    seen = []
    class FakeRest(DeltaRestClient):
        def get_page(self, symbol, tf, lo, hi):
            seen.append((lo, hi))
            return [row(ts) for ts in range(lo, hi + 1, 60)][::-1]

    start = BASE
    end = BASE + timedelta(minutes=2001)
    with FakeRest(request_pause=0) as client:
        df = client.fetch_candles("BTCUSD", "1m", start, end)
    assert len(seen) == 2
    assert len(df) == 2001
    assert df["timestamp_utc"].is_unique


def test_rate_limit_reset_milliseconds():
    class FakeResponse:
        def __init__(self, code, payload=None, headers=None):
            self.status_code = code
            self.headers = headers or {}
            self.payload = payload
        def raise_for_status(self):
            if self.status_code >= 400:
                raise AssertionError("Unexpected HTTP error")
        def json(self):
            return self.payload
    class FakeSession:
        def __init__(self): self.count = 0
        def get(self, *_args, **_kwargs):
            self.count += 1
            if self.count == 1:
                return FakeResponse(429, headers={"X-RATE-LIMIT-RESET": "2000"})
            return FakeResponse(200, payload={"success": True, "result": []})
    waits = []
    session = FakeSession()
    with DeltaRestClient(session=session, request_pause=0, sleep=waits.append) as client:
        assert client.get_page("BTCUSD", "1m", 10, 70) == []
    assert session.count == 2
    assert waits == [3]
