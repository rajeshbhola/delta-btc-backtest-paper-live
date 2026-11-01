import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from indicator_studio.json_files import write_json, read_latest, find_candle_base
from indicator_studio.pipeline import analyze
from indicator_studio.demo import create_demo
from main import main


def make_rows(start: datetime, count: int, step=60, skip=()):
    rows = []
    for i in range(count):
        if i in skip:
            continue
        dt = start + timedelta(seconds=i * step)
        price = 1000 + i
        rows.append({"timestamp_utc": dt.isoformat().replace("+00:00", "Z"),
                     "open": price, "high": price + 2, "low": price - 2,
                     "close": price + 1, "volume": 10})
    return rows


def input_months(root, rows, tf="1m"):
    base = root / "clean" / "BTCUSD" / tf
    by_month = {}
    for row in rows:
        by_month.setdefault(row["timestamp_utc"][:7], []).append(row)
    for month, group in by_month.items():
        write_json(base / f"{month}.json", group)


def test_pipeline_keeps_original_and_works_across_months(tmp_path):
    source, dest = tmp_path / "project2", tmp_path / "project3"
    start = datetime(2026, 9, 30, 23, 30, tzinfo=timezone.utc)
    rows = make_rows(start, 100)
    input_months(source, rows)
    original = (source / "clean/BTCUSD/1m/2026-09.json").read_bytes()
    report = analyze(source, dest, timeframes=["1m"])[0]
    assert report["rows"] == 100
    assert report["missing_candle_slots"] == 0
    # First October row continues the SMA from September, not a new warm-up.
    result = json.loads((dest / "indicators/BTCUSD/1m/2026-10.json").read_text())
    assert result[0]["sma_20"] is not None
    assert (source / "clean/BTCUSD/1m/2026-09.json").read_bytes() == original
    assert len(read_latest(dest, "1m", 10)) == 10


def test_missing_candle_resets_indicator_warmup(tmp_path):
    source, dest = tmp_path / "source", tmp_path / "out"
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    input_months(source, make_rows(start, 110, skip=[65]))
    report = analyze(source, dest, timeframes=["1m"])[0]
    assert report["missing_candle_slots"] == 1
    result = json.loads((dest / "indicators/BTCUSD/1m/2026-10.json").read_text())
    assert result[64]["sma_20"] is not None
    assert result[65]["sma_20"] is None
    assert result[84]["sma_20"] is not None


def test_invalid_and_duplicate_data_fail_clearly(tmp_path):
    src = tmp_path / "src"
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    rows = make_rows(start, 30)
    rows[5]["high"] = 1
    input_months(src, rows)
    with pytest.raises(ValueError, match="row 6"):
        analyze(src, tmp_path / "output", timeframes=["1m"])


def test_unsorted_input_fails(tmp_path):
    src = tmp_path / "src"
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    rows = make_rows(start, 30)
    rows[2], rows[3] = rows[3], rows[2]
    input_months(src, rows)
    with pytest.raises(ValueError, match="out-of-order"):
        analyze(src, tmp_path / "out", timeframes=["1m"])


def test_source_guard(tmp_path):
    source = tmp_path / "input"
    input_months(source, make_rows(datetime(2026, 10, 1, tzinfo=timezone.utc), 30))
    with pytest.raises(ValueError, match="separate folder"):
        analyze(source, source / "output")


def test_project1_path_is_supported(tmp_path):
    root = tmp_path / "project1"
    path = root / "candles/BTCUSD/1h/2026-10.json"
    write_json(path, make_rows(datetime(2026, 10, 1, tzinfo=timezone.utc), 60, step=3600))
    assert find_candle_base(root) == root / "candles" / "BTCUSD"
    report = analyze(root, tmp_path / "output", timeframes=["1h"])[0]
    assert report["rows"] == 60


def test_demo_and_cli(tmp_path, capsys):
    synthetic = tmp_path / "demo"
    output = tmp_path / "output"
    assert main(["demo", "--output", str(synthetic), "--rows", "250"]) == 0
    assert main(["analyze", "--source", str(synthetic), "--output", str(output)]) == 0
    assert main(["summary", "--output", str(output)]) == 0
    text = capsys.readouterr().out
    assert "SYNTHETIC" in text and "missing slots" in text
    assert len(list((output / "reports").glob("*.json"))) == 5
    assert all(json.loads(p.read_text())["missing_candle_slots"] == 1 for p in (output/"reports").glob("*.json"))


def test_all_data_files_have_correct_shape(tmp_path):
    synthetic = tmp_path / "demo"
    assert create_demo(synthetic, rows=300)["1m"] == 299
    with pytest.raises(FileExistsError):
        create_demo(synthetic, rows=300)
    assert create_demo(synthetic, rows=300, overwrite=True)["4h"] == 299
