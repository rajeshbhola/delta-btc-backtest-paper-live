"""Offline tests: no live Delta connection or Streamlit installation required."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
import pytest
from chart_lab.analytics import audit_window, decisions_for_chart, signal_summary
from chart_lab.config import TIMEFRAMES, candle_interval
from chart_lab.demo import generate_demo
from chart_lab.figures import make_price_figure, make_oscillators
from chart_lab.sources import (
    parse_utc, locate_root, month_files, load_range, latest_timestamp,
    combine_candles_and_indicators, candle_price_conflicts,
)

UTC = timezone.utc


def sample_rows():
    return [{"timestamp_utc": "2026-10-31T23:55:00Z", "open": 100, "high": 105, "low": 95, "close": 101, "volume": 10},
            {"timestamp_utc": "2026-11-01T00:00:00Z", "open": 101, "high": 110, "low": 100, "close": 108, "volume": 12},
            {"timestamp_utc": "2026-11-01T00:05:00Z", "open": 108, "high": 110, "low": 103, "close": 104, "volume": 7}]


def project_json(tmp_path: Path, kind="candles", tf="5m", rows=None):
    rows = sample_rows() if rows is None else rows
    root = tmp_path/kind/"BTCUSD"/tf
    root.mkdir(parents=True, exist_ok=True)
    groups = {}
    for row in rows:
        groups.setdefault(row["timestamp_utc"][:7], []).append(row)
    for month, data in groups.items():
        (root/f"{month}.json").write_text(json.dumps(data), encoding="utf-8")
    return tmp_path


def test_all_five_timeframes_supported():
    assert list(TIMEFRAMES) == ["1m", "5m", "15m", "1h", "4h"]
    assert candle_interval("4h") == timedelta(hours=4)


def test_unsupported_timeframe_rejected():
    with pytest.raises(ValueError):
        candle_interval("3m")


def test_utc_timestamp():
    assert parse_utc("2026-11-01T00:00:00Z") == datetime(2026,11,1,tzinfo=UTC)


def test_naive_timestamp_rejected():
    with pytest.raises(ValueError):
        parse_utc("2026-11-01T00:00:00")


def test_project1_folder_found(tmp_path):
    root = project_json(tmp_path, "candles")
    assert locate_root(root, "candles") == root/"candles"/"BTCUSD"
    assert len(month_files(locate_root(root, "candles"), "5m")) == 2


def test_project2_clean_folder_found(tmp_path):
    root = project_json(tmp_path, "clean")
    assert locate_root(root, "candles") == root/"clean"/"BTCUSD"


def test_project3_indicator_folder_found(tmp_path):
    root = project_json(tmp_path, "indicators")
    assert locate_root(root, "indicators") == root/"indicators"/"BTCUSD"
    assert locate_root(root, "candles") == root/"indicators"/"BTCUSD"


def test_project4_signal_folder_found(tmp_path):
    root = project_json(tmp_path, "signals")
    assert locate_root(root, "signals") == root/"signals"/"BTCUSD"


def test_date_window_across_months(tmp_path):
    root = locate_root(project_json(tmp_path), "candles")
    df, meta = load_range(root, "5m", datetime(2026,10,31,23,55,tzinfo=UTC),datetime(2026,11,1,0,5,tzinfo=UTC),100)
    assert len(df) == 2  # exclusive end
    assert meta["files_read"] == 2
    assert df.timestamp_utc.is_monotonic_increasing


def test_recent_limit_returns_latest_candles(tmp_path):
    root = locate_root(project_json(tmp_path), "candles")
    df, _ = load_range(root, "5m", datetime(2026,10,31,0,0,tzinfo=UTC),datetime(2026,11,2,0,0,tzinfo=UTC),2)
    assert len(df) == 2
    assert df.close.tolist() == [108,104]


def test_latest_timestamp_reads_last_month(tmp_path):
    root = locate_root(project_json(tmp_path), "candles")
    assert latest_timestamp(root, "5m") == datetime(2026,11,1,0,5,tzinfo=UTC)


def test_merge_by_timestamp_not_row_position():
    candles = pd.DataFrame(sample_rows())
    indicators = pd.DataFrame([{"timestamp_utc": sample_rows()[2]["timestamp_utc"], "ema_9": 15}])
    candles["timestamp_utc"] = pd.to_datetime(candles.timestamp_utc, utc=True)
    indicators["timestamp_utc"] = pd.to_datetime(indicators.timestamp_utc, utc=True)
    merged = combine_candles_and_indicators(candles, indicators)
    assert pd.isna(merged.ema_9.iloc[0])
    assert merged.ema_9.iloc[2] == 15


def test_detect_mismatched_close_price():
    candles = pd.DataFrame([{"timestamp_utc": 1, "close": 100.0}])
    indicators = pd.DataFrame([{"timestamp_utc": 1, "close": 102.0}])
    assert candle_price_conflicts(candles, indicators) == 1


def test_gap_audit_finds_missing_five_minute_candle():
    df = pd.DataFrame([sample_rows()[0], sample_rows()[2]])
    quality = audit_window(df, "5m")
    assert quality["gap_slots"] == 1
    assert quality["invalid_ohlc"] == 0


def test_bad_ohlc_detected():
    bad = {**sample_rows()[0], "high": 97, "volume": -2}
    result = audit_window(pd.DataFrame([bad]), "5m")
    assert result["invalid_ohlc"] == 1
    assert result["invalid_volume"] == 1


def test_signal_counts():
    values = pd.DataFrame({"signal": ["BUY", "HOLD", "SELL", "HOLD"]})
    assert signal_summary(values) == {"BUY":1,"SELL":1,"HOLD":2}


def test_decision_time_filters_not_source_open_time():
    df = pd.DataFrame([{"timestamp_utc":"2026-11-01T10:00:00Z", "decision_time_utc":"2026-11-01T10:05:00Z", "close":100,"signal":"BUY"}])
    x = decisions_for_chart(df, pd.Timestamp("2026-11-01T10:05:00Z"), pd.Timestamp("2026-11-01T10:06:00Z"))
    assert len(x)==1
    assert x.decision_time_utc.iloc[0].hour == 10
    y = decisions_for_chart(df, pd.Timestamp("2026-11-01T10:00:00Z"), pd.Timestamp("2026-11-01T10:04:00Z"))
    assert len(y)==0


def test_plotly_chart_renders_ohlcv():
    candles = pd.DataFrame(sample_rows())
    candles["timestamp_utc"] = pd.to_datetime(candles.timestamp_utc, utc=True)
    figure = make_price_figure(candles, pd.DataFrame(), [], True)
    assert len(figure.data) == 2
    assert figure.data[0].type == "candlestick"
    assert "plotly" in figure.to_html(include_plotlyjs="cdn")


def test_oscillators():
    candles = pd.DataFrame(sample_rows())
    candles["timestamp_utc"] = pd.to_datetime(candles.timestamp_utc,utc=True)
    candles["rsi_14"] = [60, 61, 59]
    fig = make_oscillators(candles, ["RSI"])
    assert len(fig.data) == 1


def test_create_own_demo_dataset(tmp_path):
    result = generate_demo(tmp_path, n=100)
    assert set(result)==set(TIMEFRAMES)
    assert (tmp_path/"SYNTHETIC_DATA_NOTICE.txt").is_file()
    for t in TIMEFRAMES:
        for kind in ["candles", "indicators", "signals"]:
            root = locate_root(tmp_path, kind)
            assert len(month_files(root,t))>=1
    root = locate_root(tmp_path,"candles")
    df,_ = load_range(root,"5m",datetime(2026,10,29,tzinfo=UTC),datetime(2026,11,1,tzinfo=UTC),1000)
    assert len(df)==100


def test_no_missing_root_returns_empty(tmp_path):
    assert locate_root(tmp_path/"unknown", "signals") is None
    df,_ = load_range(None,"5m",datetime(2026,10,1,tzinfo=UTC),datetime(2026,11,1,tzinfo=UTC))
    assert df.empty
