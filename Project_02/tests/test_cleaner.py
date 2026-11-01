from datetime import datetime, timezone
from quality_lab.cleaner import validate_candle, clean_rows

NOW = datetime(2026, 10, 31, 10, 10, tzinfo=timezone.utc)

def bar(ts="2026-10-31T10:00:00Z", **kwargs):
    return {"timestamp_utc": ts, "open": 100.0, "high": 105.0,
            "low": 99.0, "close": 102.0, "volume": 8.0, **kwargs}


def test_good_candle():
    result, error = validate_candle(bar(), "5m", now=NOW)
    assert error is None and result["close"] == 102.0


def test_bad_high_rejected():
    item = bar()
    item["high"] = 101
    _, reason = validate_candle(item, "5m", now=NOW)
    assert reason == "invalid_ohlc"


def test_negative_volume_rejected():
    item = bar()
    item["volume"] = -1
    assert validate_candle(item, "5m", now=NOW)[1] == "negative_volume"


def test_naive_timestamp_rejected():
    assert validate_candle(bar(ts="2026-10-31T10:00:00"), "5m", now=NOW)[1] == "invalid_timestamp"


def test_off_grid_rejected():
    assert validate_candle(bar(ts="2026-10-31T10:01:00Z"), "5m", now=NOW)[1] == "off_grid_timestamp"


def test_unfinished_candle_rejected():
    assert validate_candle(bar(ts="2026-10-31T10:10:00Z"), "5m", now=NOW)[1] == "unclosed_or_future_candle"


def test_nonfinite_rejected():
    item = bar(); item["volume"] = float('nan')
    assert validate_candle(item, "5m", now=NOW)[1] == "non_finite_number"


def test_duplicate_keeps_last_valid_and_sorts():
    a = bar(ts="2026-10-31T10:05:00Z")
    b = bar(ts="2026-10-31T10:00:00Z")
    b2 = dict(b, close=103.0)
    bad = dict(b, high=1)
    cleaned, stats = clean_rows([a, b, b2, bad], "5m", now=NOW)
    assert len(cleaned) == 2
    assert cleaned[0]["close"] == 103
    assert stats["rejected_rows"] == 1
    assert stats["duplicate_rows"] == 1
    assert stats["out_of_order_raw_rows"] == 1


def test_repair_overrides_raw():
    fixed, stats = clean_rows([bar()], "5m", now=NOW,
                              patches=[dict(bar(), close=104.0)])
    assert fixed[0]["close"] == 104 and stats["accepted_repair_rows"] == 1


def test_no_fabricated_candles():
    cleaned, _ = clean_rows([bar(), bar(ts="2026-10-31T10:05:00Z")], "5m", now=NOW)
    assert len(cleaned) == 2
