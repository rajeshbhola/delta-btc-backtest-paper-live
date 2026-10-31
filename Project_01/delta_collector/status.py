"""Crash-safe JSON status snapshots for the read-only Streamlit dashboard."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .storage import atomic_write_json


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_status(path: Path | str = "data/status.json") -> dict:
    path = Path(path)
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as fp:
            obj = json.load(fp)
    except (OSError, ValueError):
        return {}
    return obj if isinstance(obj, dict) else {}


class CollectorStatus:
    def __init__(self, path: Path | str = "data/status.json"):
        self.path = Path(path)
        self._lock = threading.Lock()

    def update(self, **changes: Any):
        with self._lock:
            state = read_status(self.path)
            state.update(changes)
            state["updated_utc"] = now_iso()
            atomic_write_json(self.path, state)

    def timeframe(self, timeframe: str, **changes: Any):
        with self._lock:
            state = read_status(self.path)
            progress = state.setdefault("timeframes", {})
            details = progress.setdefault(timeframe, {})
            details.update(changes)
            state["updated_utc"] = now_iso()
            atomic_write_json(self.path, state)

    def websocket(self, **changes: Any):
        with self._lock:
            state = read_status(self.path)
            status = state.setdefault("websocket", {})
            status.update(changes)
            state["updated_utc"] = now_iso()
            atomic_write_json(self.path, state)
