"""Public WebSocket provisional updates + REST reconciliation triggers.

Delta REST candles are stamped in Unix seconds. WebSocket `ts` is microseconds
and denotes the update/event time, *not necessarily candle opening time*.
Do not persist WS updates as final OHLCV; REST confirms closed candles.
"""
from __future__ import annotations

import json
import logging
import queue
import threading
import time
from datetime import datetime, timezone
from typing import Callable

import websocket

from .config import INTERVAL_SECONDS, WS_URL, aligned_open

LOG = logging.getLogger(__name__)


def parse_public_candle(message: dict, symbol: str, timeframes: tuple[str, ...]):
    """Return a normalized provisional WS update; ignore non-candle messages."""
    channel = message.get("type", "")
    if not isinstance(channel, str) or not channel.startswith("candlestick_"):
        return None
    tf = channel.removeprefix("candlestick_")
    if tf not in timeframes or message.get("sy") != symbol:
        return None
    if message.get("res", tf) != tf:
        return None
    # New public WebSocket schema: o/h/l/c/v/sy/ts/res/type.
    try:
        event_microseconds = int(message["ts"])
        if event_microseconds < 10**14:
            return None  # do not confuse historical REST seconds with WS microseconds
        o, h, l, c, v = (float(message[key]) for key in ("o", "h", "l", "c", "v"))
    except (ValueError, TypeError, KeyError):
        return None
    if (h < max(o, l, c)) or (l > min(o, h, c)) or v < 0:
        return None
    event_seconds = event_microseconds // 1_000_000
    # This is an EVENT bucket used to decide when REST might need refreshing;
    # it is NOT stored as the authoritative candle start timestamp.
    bucket = aligned_open(event_seconds, INTERVAL_SECONDS[tf])
    return {"timeframe": tf, "event_time_utc": datetime.fromtimestamp(event_seconds, timezone.utc),
            "event_bucket_seconds": bucket, "open": o, "high": h, "low": l,
            "close": c, "volume": v, "provisional": True}


def subscribe_payload(symbol: str, timeframes: tuple[str, ...]) -> dict:
    return {"type": "subscribe", "payload": {"channels": [
        {"name": f"candlestick_{tf}", "symbols": [symbol]} for tf in timeframes
    ]}}


class DeltaPublicCandleWebSocket:
    def __init__(self, symbol: str, timeframes: tuple[str, ...], refresh_queue: queue.Queue[str],
                 ws_url: str = WS_URL, callback: Callable[[dict], None] | None = None,
                 connection_callback: Callable[[str], None] | None = None):
        self.symbol, self.timeframes = symbol, timeframes
        self.refresh_queue, self.ws_url, self.callback = refresh_queue, ws_url, callback
        self.connection_callback = connection_callback
        self._buckets: dict[str, int] = {}
        self._stopped = threading.Event()
        self._app = None
        self._thread: threading.Thread | None = None

    def _handle_message(self, _ws, raw: str):
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            LOG.warning("Ignoring invalid WS JSON")
            return
        if not isinstance(payload, dict):
            return
        event = parse_public_candle(payload, self.symbol, self.timeframes)
        if event is None:
            return
        tf, bucket = event["timeframe"], event["event_bucket_seconds"]
        prior = self._buckets.get(tf)
        if prior is not None and bucket > prior:
            try:
                self.refresh_queue.put_nowait(tf)  # REST confirms the prior closed candle.
            except queue.Full:
                LOG.warning("WS refresh queue full; periodic REST polling will recover")
        self._buckets[tf] = max(bucket, prior) if prior is not None else bucket
        if self.callback:
            self.callback(event)

    def _connect_loop(self):
        pause = 5
        while not self._stopped.is_set():
            def on_open(ws):
                nonlocal pause
                pause = 5
                LOG.info("WebSocket connected; subscribing to %s", ", ".join(self.timeframes))
                if self.connection_callback:
                    self.connection_callback("connected")
                ws.send(json.dumps(subscribe_payload(self.symbol, self.timeframes)))

            def on_error(_ws, error):
                LOG.warning("WebSocket error: %s", error)

            def on_close(_ws, status, reason):
                LOG.warning("WebSocket disconnected (code=%s): %s", status, reason)
                if self.connection_callback:
                    self.connection_callback("disconnected")

            self._app = websocket.WebSocketApp(self.ws_url, on_open=on_open,
                                              on_message=self._handle_message,
                                              on_error=on_error, on_close=on_close)
            try:
                self._app.run_forever(ping_interval=30, ping_timeout=10)
            except Exception:
                LOG.exception("WS run failed")
            if self._stopped.is_set():
                break
            LOG.warning("WebSocket reconnecting in %ds", pause)
            if self.connection_callback:
                self.connection_callback("reconnecting")
            if self._stopped.wait(pause):
                break
            pause = min(120, pause * 2)

    def start(self):
        if self._thread is not None:
            raise RuntimeError("WebSocket already started")
        self._thread = threading.Thread(target=self._connect_loop, daemon=True, name="delta-public-ws")
        self._thread.start()

    def stop(self):
        self._stopped.set()
        if self.connection_callback:
            self.connection_callback("stopped")
        if self._app is not None:
            self._app.close()
        if self._thread is not None:
            self._thread.join(timeout=10)
