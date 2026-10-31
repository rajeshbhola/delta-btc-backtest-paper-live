import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from delta_collector.storage import CandleStore
from delta_collector.status import CollectorStatus, read_status

START = datetime(2026, 1, 31, 23, 58, tzinfo=timezone.utc)


def candles(start, closes):
    return pd.DataFrame({
        "timestamp_utc": pd.date_range(start, periods=len(closes), freq="60s", tz="UTC"),
        "open": [100.] * len(closes), "high": [500.] * len(closes),
        "low": [1.] * len(closes), "close": closes, "volume": [20.] * len(closes),
    })


def test_monthly_json_files_dedup_and_resume(tmp_path):
    store = CandleStore(tmp_path)
    store.write("BTCUSD", "1m", candles(START, [101, 102, 103, 104]))
    files = sorted(tmp_path.rglob("*.json"))
    assert [p.name for p in files] == ["2026-01.json", "2026-02.json"]
    records = json.loads(files[0].read_text())
    assert records[0] == {"timestamp_utc": "2026-01-31T23:58:00Z",
                          "open": 100.0, "high": 500.0, "low": 1.0,
                          "close": 101.0, "volume": 20.0}
    store.write("BTCUSD", "1m", candles(START + timedelta(minutes=2), [222, 333]))
    result = store.load("BTCUSD", "1m")
    assert result["close"].tolist() == [101, 102, 222, 333]
    assert store.latest_time("BTCUSD", "1m") == START + timedelta(minutes=3)
    assert len(list(tmp_path.rglob(".*.tmp"))) == 0
    assert store.tail("BTCUSD", "1m", 2)["close"].tolist() == [222, 333]


def test_load_filters_month_ranges(tmp_path):
    store = CandleStore(tmp_path)
    store.write("BTCUSD", "1m", candles(START, [101, 102, 103, 104]))
    df = store.load("BTCUSD", "1m", start=START + timedelta(minutes=1),
                    end=START + timedelta(minutes=3))
    assert df["close"].tolist() == [102, 103]


def test_audit_writes_json_gaps(tmp_path):
    store = CandleStore(tmp_path / "candles")
    store.write("BTCUSD", "1m", candles(START, [101, 102, 103, 104]).drop(index=[1]))
    report = store.audit("BTCUSD", "1m", START, START + timedelta(minutes=4),
                         report_dir=tmp_path / "reports")
    assert (report["expected"], report["actual"], report["missing"]) == (4, 3, 1)
    obj = json.loads((tmp_path / "reports" / "BTCUSD_1m_missing.json").read_text())
    assert obj["summary"]["missing"] == 1
    assert obj["missing_timestamps_utc"] == ["2026-01-31T23:59:00Z"]


def test_reject_invalid_json_candle(tmp_path):
    store = CandleStore(tmp_path)
    bad = candles(START, [101, 102])
    bad.loc[0, "close"] = float("nan")
    with pytest.raises(ValueError, match="null or NaN"):
        store.write("BTCUSD", "1m", bad)
    bad.loc[0, "close"] = float("inf")
    with pytest.raises(ValueError, match="Non-finite"):
        store.write("BTCUSD", "1m", bad)


def test_status_atomic_nested_updates(tmp_path):
    path = tmp_path / "status.json"
    status = CollectorStatus(path)
    status.update(state="running", mode="backfill")
    status.timeframe("5m", actual=100, progress_pct=25)
    status.websocket(state="connected", last_price=123)
    obj = read_status(path)
    assert obj["state"] == "running"
    assert obj["timeframes"]["5m"]["actual"] == 100
    assert obj["websocket"]["state"] == "connected"
    assert "updated_utc" in obj


def test_json_files_only_and_missing_is_empty(tmp_path):
    store = CandleStore(tmp_path)
    assert store.load("BTCUSD", "4h").empty
    assert store.latest_time("BTCUSD", "4h") is None
    assert store.tail("BTCUSD", "4h").empty


def test_restart_resume_after_overlap(tmp_path):
    from delta_collector.service import CandleService
    store = CandleStore(tmp_path)
    store.write("BTCUSD", "1m", candles(START, [100, 101, 102, 103]))
    calls = []
    class FakeRest:
        def iter_pages(self, symbol, tf, start, end):
            calls.append(start)
            yield candles(START + timedelta(minutes=1), [201, 202, 203, 204])
    service = CandleService(FakeRest(), store)
    received = service.sync("1m", START, START + timedelta(minutes=5))
    assert received == 4
    assert calls[0] == START + timedelta(minutes=1)
    assert store.load("BTCUSD", "1m")["close"].tolist() == [100, 201, 202, 203, 204]
