import math
from indicator_studio.indicators import IndicatorEngine, SimpleMovingAverage, ExponentialMovingAverage
from indicator_studio.config import INDICATOR_FIELDS


def candle(close=100.0, high=None, low=None):
    return {"open": close, "high": high if high is not None else close + 2,
            "low": low if low is not None else close - 2, "close": close, "volume": 12.0}


def test_sma_warmup_and_value():
    calc = SimpleMovingAverage(3)
    assert [calc.update(x) for x in (10, 20, 30, 40)] == [None, None, 20, 30]


def test_ema_seed_and_next_step():
    calc = ExponentialMovingAverage(3)
    assert [calc.update(x) for x in (10, 20, 30, 40)] == [None, None, 20, 30]


def test_flat_market_indicators():
    engine = IndicatorEngine()
    out = [engine.update(candle()) for _ in range(65)]
    assert all(name in out[-1] for name in INDICATOR_FIELDS)
    assert out[13]["atr_14"] == 4
    assert out[18]["sma_20"] is None
    assert out[19]["sma_20"] == 100
    assert out[13]["rsi_14"] is None
    assert out[14]["rsi_14"] == 50
    assert out[32]["macd_signal"] is None
    assert out[33]["macd_signal"] == 0
    assert out[-1]["bb_lower"] == 100
    assert out[-1]["bb_upper"] == 100
    assert out[-1]["atr_14"] == 4


def test_rsi_uptrend_and_downtrend():
    rising, falling = IndicatorEngine(), IndicatorEngine()
    for i in range(60):
        up = rising.update(candle(100 + i))
        down = falling.update(candle(100 - i, high=102-i, low=98-i))
    assert up["rsi_14"] == 100
    assert down["rsi_14"] == 0


def test_macd_histogram_relation_and_bounds():
    engine = IndicatorEngine()
    out = None
    for i in range(100):
        out = engine.update(candle(100 + math.sin(i / 5) * 4 + 0.25 * i))
    assert abs(out["macd"] - out["macd_signal"] - out["macd_histogram"]) < 3e-8
    assert 0 <= out["rsi_14"] <= 100
    assert out["bb_lower"] < out["bb_middle"] < out["bb_upper"]
