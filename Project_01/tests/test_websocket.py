import json
import queue
from datetime import datetime, timezone

from delta_collector.live import DeltaPublicCandleWebSocket, parse_public_candle, subscribe_payload


def event(ts_microseconds, tf="5m"):
    return {"type": f"candlestick_{tf}", "sy": "BTCUSD", "res": tf,
            "ts": ts_microseconds, "o": 100, "h": 110, "l": 90, "c": 105, "v": 3}


def test_five_websocket_subscriptions():
    timeframes = ("1m", "5m", "15m", "1h", "4h")
    result = subscribe_payload("BTCUSD", timeframes)
    assert result["type"] == "subscribe"
    assert len(result["payload"]["channels"]) == 5
    assert {x["name"] for x in result["payload"]["channels"]} == {f"candlestick_{x}" for x in timeframes}


def test_ws_microsecond_event_is_provisional_not_open_timestamp():
    start = int(datetime(2026, 10, 31, 15, 1, tzinfo=timezone.utc).timestamp())
    result = parse_public_candle(event(start * 1_000_000), "BTCUSD", ("5m",))
    assert result["provisional"] is True
    assert result["event_bucket_seconds"] == start - 60  # 15:00 open of event bucket
    assert result["event_time_utc"].tzinfo == timezone.utc
    assert parse_public_candle(event(start), "BTCUSD", ("5m",)) is None


def test_ws_boundary_queues_rest_sync():
    q = queue.Queue()
    received = []
    ws = DeltaPublicCandleWebSocket("BTCUSD", ("5m",), q, callback=received.append)
    t1 = int(datetime(2026, 10, 31, 15, 4, tzinfo=timezone.utc).timestamp()) * 1_000_000
    t2 = int(datetime(2026, 10, 31, 15, 5, tzinfo=timezone.utc).timestamp()) * 1_000_000
    ws._handle_message(None, json.dumps(event(t1)))
    assert q.empty()
    ws._handle_message(None, json.dumps(event(t2)))
    assert q.get_nowait() == "5m"
    assert len(received) == 2


def test_ignores_other_symbols_and_invalid_prices():
    t1 = int(datetime(2026, 10, 31, 15, 4, tzinfo=timezone.utc).timestamp()) * 1_000_000
    bad = event(t1)
    bad["sy"] = "ETHUSD"
    assert parse_public_candle(bad, "BTCUSD", ("5m",)) is None
    bad = event(t1)
    bad["h"] = 80
    assert parse_public_candle(bad, "BTCUSD", ("5m",)) is None
