from datetime import datetime, timezone
import numpy as np
import pandas as pd
import pytest
from backtest_lab.data import prepare
from backtest_lab.engine import BacktestConfig, run_backtest

ASOF = datetime(2026, 1, 2, tzinfo=timezone.utc)


def sample(opens=(100,100,110,120), signals=("BUY","HOLD","SELL","HOLD"), times=None):
    timestamps = times if times is not None else pd.date_range("2026-01-01T00:00:00Z", periods=len(opens), freq="5min")
    candles = pd.DataFrame({"timestamp_utc": timestamps, "open": opens,
                            "high": [p + 5 for p in opens], "low": [p - 5 for p in opens],
                            "close": opens, "volume": [1]*len(opens)})
    signal_rows = pd.DataFrame({"timestamp_utc": timestamps, "decision_time_utc": [t + pd.Timedelta(minutes=5) for t in timestamps],
                                "signal": signals, "close": opens})
    return candles, signal_rows


def backtest(opens=(100,100,110,120), signals=("BUY","HOLD","SELL","HOLD"), mode="long_only", fee_bps=0):
    c,s=sample(opens,signals)
    ready,_=prepare(c,s,"5m",as_of=ASOF)
    return run_backtest(ready,BacktestConfig(mode=mode,fee_bps=fee_bps))


def test_buy_filled_only_next_open():
    curve, trades, result = backtest()
    assert list(curve.position) == [0,1,1,0]
    assert result["ending_capital_usd"] == pytest.approx(12000)
    assert len(trades)==1
    assert trades.iloc[0].entry_time_utc == pd.Timestamp("2026-01-01T00:05:00Z")
    assert trades.iloc[0].exit_time_utc == pd.Timestamp("2026-01-01T00:15:00Z")


def test_sell_without_buy_does_not_short_long_only():
    _, trades, result = backtest(opens=(100,90,80,70), signals=("SELL","HOLD","HOLD","HOLD"))
    assert trades.empty
    assert result["ending_capital_usd"] == 10000


def test_short_profit_when_price_drops():
    curve, trades, result = backtest(opens=(100,100,90,80), signals=("SELL","HOLD","BUY","HOLD"), mode="long_short")
    assert list(curve.position)==[0,-1,-1,1]
    assert trades.iloc[0]["side"]=="SHORT"
    assert result["ending_capital_usd"] > 10000
    assert trades.iloc[-1].exit_at_last_close


def test_fee_two_sides_no_price_move():
    curve,trades,result = backtest(opens=(100,100,100,100),signals=("BUY","HOLD","SELL","HOLD"),fee_bps=10)
    assert result["ending_capital_usd"] == pytest.approx(10000*(1-0.001)**2)
    assert trades.iloc[0].fee_paid_usd > 0
    assert sum(trades.net_pnl) == pytest.approx(result["total_net_pnl_usd"])


def test_reversal_has_both_exit_and_entry_fee():
    curve,trades,result = backtest(opens=(100,100,100,100),signals=("BUY","SELL","HOLD","HOLD"),mode="long_short",fee_bps=10)
    assert list(curve.position)==[0,1,-1,-1]
    assert list(curve.fee_events)==[0,1,2,1]
    assert len(trades)==2
    assert result["ending_capital_usd"] == pytest.approx(10000*(1-.001)**4)


def test_gap_forces_flat_but_does_not_erase_gap_pnl():
    ts=pd.to_datetime(["2026-01-01T00:00:00Z","2026-01-01T00:05:00Z","2026-01-01T00:20:00Z","2026-01-01T00:25:00Z"])
    c,s=sample(opens=(100,100,130,135),signals=("BUY","HOLD","HOLD","HOLD"),times=ts)
    ready,info=prepare(c,s,"5m",as_of=ASOF)
    curve,trades,result=run_backtest(ready)
    assert info["gaps"] == 1
    assert list(curve.position)==[0,1,0,0]
    assert result["ending_capital_usd"] == pytest.approx(13000)
    assert len(trades)==1


def test_final_position_closed_at_last_candle_close():
    c,s=sample(opens=(100,100,100,100),signals=("BUY","HOLD","HOLD","HOLD"))
    c.loc[3,"close"] = 110
    c.loc[3,"high"] = 115
    s.loc[3,"close"] = 110
    ready,_=prepare(c,s,"5m",as_of=ASOF)
    curve,trades,result=run_backtest(ready)
    assert result["ending_capital_usd"]==pytest.approx(11000)
    assert trades.iloc[0].exit_at_last_close
    assert trades.iloc[0].exit_time_utc == pd.Timestamp("2026-01-01T00:20:00Z")
    assert curve.iloc[-1].mark_time_utc == pd.Timestamp("2026-01-01T00:20:00Z")


def test_last_signal_never_executed():
    curve,trades,result = backtest(opens=(100,110,120,130), signals=("HOLD","HOLD","HOLD","BUY"))
    assert not curve.position.any()
    assert trades.empty


def test_missing_signal_is_hold():
    c,s=sample()
    s=s.iloc[:1]
    ready,info=prepare(c,s,"5m",as_of=ASOF)
    assert info["missing_signal_rows"]==3
    assert ready.iloc[1].signal=="HOLD"


def test_reject_signal_close_mismatch():
    c,s=sample();s.loc[0,"close"]=999
    with pytest.raises(ValueError,match="does not match"):
        prepare(c,s,"5m",as_of=ASOF)


def test_reject_future_decision_timestamp():
    c,s=sample();s.loc[0,"decision_time_utc"]="2026-01-01T00:20:00Z"
    with pytest.raises(ValueError,match="decision_time"):
        prepare(c,s,"5m",as_of=ASOF)


def test_reject_bad_ohlc():
    c,s=sample();c.loc[2,"high"]=20
    with pytest.raises(ValueError,match="OHLC"):
        prepare(c,s,"5m",as_of=ASOF)


def test_reject_duplicate_timestamps():
    c,s=sample();c.loc[1,"timestamp_utc"]=c.loc[0,"timestamp_utc"]
    with pytest.raises(ValueError,match="duplicate"):
        prepare(c,s,"5m",as_of=ASOF)


def test_reject_misaligned_timestamps():
    c,s=sample();c.loc[1,"timestamp_utc"]=pd.Timestamp("2026-01-01T00:06:00Z")
    with pytest.raises(ValueError,match="aligned"):
        prepare(c,s.iloc[:0],"5m",as_of=ASOF)


def test_excludes_unfinished_candles():
    c,s=sample()
    ready,info=prepare(c,s,"5m",as_of=datetime(2026,1,1,0,12,tzinfo=timezone.utc))
    assert len(ready)==2
    assert ready.iloc[-1].timestamp_utc == pd.Timestamp("2026-01-01T00:05:00Z")


def test_reject_invalid_config():
    with pytest.raises(ValueError): BacktestConfig(starting_capital=0)
    with pytest.raises(ValueError): BacktestConfig(fee_bps=-1)
    with pytest.raises(ValueError): BacktestConfig(mode="random")


def test_returns_vs_trades_reconciled():
    for mode in ("long_only","long_short"):
        for fee in (0,2,10):
            _,trades,report=backtest(opens=(100,100,107,99),signals=("BUY","SELL","BUY","SELL"),mode=mode,fee_bps=fee)
            assert trades.net_pnl.sum() == pytest.approx(report["total_net_pnl_usd"],abs=.00001)


def test_data_window_days_positive():
    c,s=sample()
    with pytest.raises(ValueError,match="days"):
        prepare(c,s,"5m",days=0,as_of=ASOF)
