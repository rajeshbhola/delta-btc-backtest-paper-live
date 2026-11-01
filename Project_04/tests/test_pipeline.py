import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from signal_lab.pipeline import generate
from signal_lab.json_files import find_indicator_base, parse_candle, latest_rows
from main import main

T = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_row(i, fast=None, slow=None, rsi=None):
    return {"timestamp_utc": (T + timedelta(minutes=5*i)).isoformat().replace('+00:00','Z'),
            "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1.0,
            "ema_9": fast, "ema_21": slow, "rsi_14": rsi}


def build_input(root, month='2026-01', rows=None):
    base = root / 'indicators' / 'BTCUSD' / '5m'
    base.mkdir(parents=True, exist_ok=True)
    (base / f'{month}.json').write_text(json.dumps(rows if rows is not None else [make_row(0, 99, 100, 50)]))
    return root


def test_standalone_pipeline_and_preserves_input(tmp_path):
    source = build_input(tmp_path / 'source', rows=[make_row(0, 99, 100, 55),make_row(1, 101, 100, 60),make_row(2, 102, 100, 60)])
    contents = (source / 'indicators' / 'BTCUSD' / '5m' / '2026-01.json').read_bytes()
    out = tmp_path / 'new_output'
    result = generate(source, out, timeframes=['5m'], as_of=T+timedelta(days=1))
    assert result[0]['signals'] == {'BUY': 1, 'SELL': 0, 'HOLD': 2}
    assert (source / 'indicators' / 'BTCUSD' / '5m' / '2026-01.json').read_bytes() == contents
    assert latest_rows(out, '5m', 2)[0]['signal'] == 'BUY'


def test_gap_and_month_boundary(tmp_path):
    source = build_input(tmp_path/'source', rows=[make_row(0, 99, 100, 55),make_row(2,101,100,60),make_row(3,99,100,40),make_row(4,101,100,60)])
    report = generate(source, tmp_path/'out',timeframes=['5m'],as_of=T+timedelta(days=1))[0]
    assert report['missing_candle_slots'] == 1
    assert report['signals']['BUY'] == 1
    assert report['signals']['SELL'] == 1


def test_crosses_over_month_boundary(tmp_path):
    source = tmp_path/'source'
    base = source/'indicators'/'BTCUSD'/'1h'
    base.mkdir(parents=True)
    first = make_row(0, 99, 100, 60)
    first['timestamp_utc'] = '2026-01-31T23:00:00Z'
    second = make_row(0, 101, 100, 60)
    second['timestamp_utc'] = '2026-02-01T00:00:00Z'
    (base/'2026-01.json').write_text(json.dumps([first]))
    (base/'2026-02.json').write_text(json.dumps([second]))
    report = generate(source, tmp_path/'out',timeframes=['1h'],as_of=datetime(2026,2,2,tzinfo=timezone.utc))[0]
    assert report['signals']['BUY']==1


def test_skips_incomplete_candle(tmp_path):
    source=build_input(tmp_path/'source',rows=[make_row(0,99,100,50),make_row(1,101,100,55)])
    report = generate(source,tmp_path/'out',timeframes=['5m'],as_of=T+timedelta(minutes=9))[0]
    assert report['total_rows']==1
    assert report['incomplete_candles_skipped']==1


def test_rejects_bad_data_and_overlapping_folders(tmp_path):
    source=build_input(tmp_path/'source',rows=[make_row(0,99,100,55),make_row(0,101,100,60)])
    with pytest.raises(ValueError,match='duplicate|out of order'):
        generate(source,tmp_path/'out',timeframes=['5m'],as_of=T+timedelta(days=1))
    with pytest.raises(ValueError,match='separate'):
        generate(source,source/'output',timeframes=['5m'],as_of=T+timedelta(days=1))


def test_rejects_invalid_rsi():
    row=make_row(0,99,100,110)
    with pytest.raises(ValueError,match='RSI'):
        parse_candle(row,'5m')


def test_cli_end_to_end(tmp_path):
    source=build_input(tmp_path/'source',rows=[make_row(0,99,100,55),make_row(1,101,100,60)])
    output=tmp_path/'out'
    assert main(['generate','--source',str(source),'--output',str(output),'--timeframes','5m','--as-of-utc','2026-01-03T00:00:00Z'])==0
    assert main(['summary','--output',str(output)])==0


def test_no_indicator_data(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_indicator_base(tmp_path/'not-a-source')


def test_garbage_future_candles_are_not_used(tmp_path):
    source=build_input(tmp_path/'source',rows=[make_row(0,99,100,55),make_row(1,101,100,60),make_row(2,99,100,40)])
    report=generate(source,tmp_path/'out',timeframes=['5m'],as_of=T+timedelta(minutes=5))[0]
    assert report['total_rows']==1
    assert report['signals']['BUY']==0


def test_no_stale_months(tmp_path):
    source=build_input(tmp_path/'source',rows=[make_row(0,99,100,55)])
    out=tmp_path/'out'
    extra=out/'signals'/'BTCUSD'/'5m'
    extra.mkdir(parents=True)
    (extra/'2025-12.json').write_text('[]')
    generate(source,out,timeframes=['5m'],as_of=T+timedelta(days=1))
    assert not (extra/'2025-12.json').exists()
