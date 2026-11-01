import json
from pathlib import Path
import pytest
from backtest_lab.data import find_base, load_json_months
from backtest_lab.pipeline import run_project, read_saved

ROOT = Path(__file__).resolve().parents[1]


def test_loads_project4_demo_for_all_timeframes():
    for tf in ("1m","5m","15m","1h","4h"):
        candles=load_json_months(ROOT / "demo_data", "candles", tf)
        signals=load_json_months(ROOT / "demo_data", "signals", tf)
        assert len(candles)==len(signals)>100
        assert "close" in candles and "decision_time_utc" in signals


def test_independent_end_to_end_output(tmp_path):
    reports=run_project(ROOT/"demo_data",ROOT/"demo_data",tmp_path/"out",timeframes=["5m"],fee_bps=5)
    assert reports[0]["trade_count"]>0
    report,curve,trades=read_saved(tmp_path/"out","5m")
    assert report["fee_bps_per_side"]==5
    assert len(curve)==499
    assert len(trades)>0
    assert "mark_time_utc" in curve


def test_output_cannot_overlap_input():
    with pytest.raises(ValueError,match="must not overlap"):
        run_project(ROOT/"demo_data",ROOT/"demo_data",ROOT/"demo_data")


def test_readonly_input_unchanged(tmp_path):
    inp=ROOT/"demo_data"/"signals"/"BTCUSD"/"5m"/"2026-10.json"
    before=inp.read_bytes()
    run_project(ROOT/"demo_data",ROOT/"demo_data",tmp_path/"out")
    assert inp.read_bytes()==before


def test_reject_missing_directory(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_json_months(tmp_path,"candles","5m")


def test_reject_bad_month_record(tmp_path):
    root=tmp_path/"candles"/"BTCUSD"/"5m";root.mkdir(parents=True)
    (root/"2026-01.json").write_text(json.dumps([{"timestamp_utc":"2026-02-01T00:00:00Z"}]))
    with pytest.raises(ValueError,match="Wrong UTC month"):
        load_json_months(tmp_path,"candles","5m")


def test_all_five_timeframes(tmp_path):
    reports=run_project(ROOT/"demo_data",ROOT/"demo_data",tmp_path/"out",timeframes=["1m","5m","15m","1h","4h"])
    assert len(reports)==5
    assert all(r["candles"]>0 for r in reports)
