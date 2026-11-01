from datetime import datetime, timezone, timedelta
import pytest
from signal_lab.config import SignalConfig
from signal_lab.strategy import SignalGenerator

T = datetime(2026, 1, 1, tzinfo=timezone.utc)


def candle(fast=100.0, slow=101.0, rsi=50.0):
    return {"close": 100, "ema_9": fast, "ema_21": slow, "rsi_14": rsi}


def run(eng, i, **kwargs):
    return eng.update(candle(**kwargs), T + timedelta(minutes=5*i), 300)


def test_warmup_reset_and_baseline():
    engine = SignalGenerator()
    assert engine.update({"close": 100, "ema_9": None, "ema_21": 100, "rsi_14": 50}, T, 300)["reason"] == "INDICATOR_NOT_READY"
    assert run(engine, 1, fast=99, slow=100)["reason"] == "BASELINE"
    assert run(engine, 2, fast=101, slow=100, rsi=60)["signal"] == "BUY"


def test_buy_confirmed_only_on_crossover():
    e = SignalGenerator()
    run(e, 0, fast=99, slow=100)
    bought = run(e, 1, fast=101, slow=100, rsi=60)
    assert bought["signal"] == "BUY"
    assert bought["decision_time_utc"] == "2026-01-01T00:10:00Z"
    assert run(e, 2, fast=102, slow=100, rsi=60)["signal"] == "HOLD"


def test_sell_confirmed_only_on_crossover():
    e = SignalGenerator()
    run(e, 0, fast=102, slow=100)
    assert run(e, 1, fast=99, slow=100, rsi=40)["signal"] == "SELL"


def test_rsi_rejects_and_does_not_emit_late_buy():
    e = SignalGenerator()
    run(e, 0, fast=99, slow=100)
    rejected = run(e, 1, fast=101, slow=100, rsi=90)
    assert rejected["reason"] == "BULLISH_CROSSOVER_RSI_REJECTED"
    assert run(e, 2, fast=102, slow=100, rsi=65)["signal"] == "HOLD"


def test_gap_never_triggers_false_signal():
    e = SignalGenerator()
    run(e, 0, fast=99, slow=100)
    after_gap = e.update(candle(fast=102, slow=100, rsi=60), T + timedelta(minutes=20), 300, gap=True)
    assert after_gap["signal"] == "HOLD"
    assert after_gap["reason"] == "GAP_RESET"


def test_new_indicator_warmup_stops_previous_cross():
    e = SignalGenerator()
    run(e, 0, fast=99, slow=100)
    e.update(candle(fast=None, slow=None, rsi=None), T + timedelta(minutes=5), 300)
    assert run(e, 2, fast=101, slow=100)["reason"] == "BASELINE"


def test_config_validation():
    with pytest.raises(ValueError):
        SignalConfig(rsi_buy_min=80, rsi_buy_max=50)
    with pytest.raises(ValueError):
        SignalConfig(rsi_sell_min=-1)


def test_rsi_boundaries_inclusive():
    e = SignalGenerator()
    run(e, 0, fast=99, slow=100)
    assert run(e, 1, fast=101, slow=100, rsi=50)["signal"] == "BUY"
