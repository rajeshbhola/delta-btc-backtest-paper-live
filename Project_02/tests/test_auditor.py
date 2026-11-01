from datetime import datetime, timezone
from quality_lab.auditor import build_audit


def d(t): return datetime.fromisoformat(t.replace("Z", "+00:00"))

def test_gap_count_and_ranges():
    clean = [{"timestamp_utc":"2026-10-31T10:00:00Z"},
             {"timestamp_utc":"2026-10-31T10:10:00Z"}]
    r = build_audit(clean, "5m", d("2026-10-31T10:00:00Z"),
                    d("2026-10-31T10:15:00Z"), now=d("2026-10-31T10:30:00Z"))
    assert r["expected"] == 3 and r["present"] == 2 and r["missing"] == 1
    assert r["missing_ranges"][0]["start_utc"] == "2026-10-31T10:05:00Z"


def test_clamps_current_candle():
    r = build_audit([], "5m", d("2026-10-31T10:00:00Z"),
                    d("2026-10-31T10:30:00Z"), now=d("2026-10-31T10:12:00Z"))
    assert r["expected"] == 2 and r["missing"] == 2


def test_empty_window():
    r = build_audit([], "1h", d("2026-10-31T10:01:00Z"),
                    d("2026-10-31T10:30:00Z"), now=d("2026-10-31T12:00:00Z"))
    assert r["expected"] == 0 and r["missing"] == 0
