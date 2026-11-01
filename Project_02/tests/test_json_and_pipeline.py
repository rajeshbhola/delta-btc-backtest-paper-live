from datetime import datetime, timezone
from pathlib import Path
import json

from quality_lab.json_store import JsonStore, atomic_json, import_project1
from quality_lab.pipeline import process
from quality_lab.demo import create_demo

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


def test_demo_and_process_all_timeframes(tmp_path):
    store = JsonStore(tmp_path)
    assert len(create_demo(store, now=NOW)) == 5
    for tf in ("1m", "5m", "15m", "1h", "4h"):
        report = process(store, tf, days=2, now=NOW)
        assert report["quality"]["rejected_rows"] == 1
        assert report["quality"]["duplicate_rows"] == 1
        assert report["quality"]["out_of_order_raw_rows"] >= 1
        assert report["coverage"]["missing"] == 2
        assert store.files("clean", tf)
        assert store.read_report(tf)["coverage"]["missing"] == 2


def test_import_project1_layout_without_touching_original(tmp_path):
    source = tmp_path / "p1" / "data" / "candles" / "BTCUSD" / "5m" / "2026-10.json"
    raw = [{"timestamp_utc":"2026-10-31T10:00:00Z", "open":1,"high":2,"low":1,"close":2,"volume":1}]
    atomic_json(source, raw)
    target = JsonStore(tmp_path / "p2")
    assert import_project1(tmp_path / "p1", target)["5m"] == 1
    assert import_project1(tmp_path / "p1", target)["5m"] == 0
    assert json.loads(source.read_text()) == raw
    assert target.read("raw", "5m") == raw


def test_repairs_preserve_original_source(tmp_path):
    store = JsonStore(tmp_path)
    original = [{"timestamp_utc":"2026-10-31T10:00:00Z","open":100,"high":110,"low":90,"close":105,"volume":2}]
    store.replace_months("raw", "5m", original)
    store.merge_by_timestamp("repairs", "5m", [dict(original[0], close=108)])
    report = process(store, "5m", days=1, now=NOW)
    assert store.read("raw", "5m")[0]["close"] == 105
    assert store.read("clean", "5m")[0]["close"] == 108
    assert report["quality"]["accepted_repair_rows"] == 1
