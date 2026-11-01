"""Streaming technical indicators using only Python's standard library.

One candle in -> one row of results out. This is memory efficient for one-year
1m datasets, and uses NO future candles. All warm-up values are None (JSON null).
"""
from __future__ import annotations
from collections import deque
from statistics import pstdev

from .config import INDICATOR_FIELDS


def number(value: float | None) -> float | None:
    """Keep JSON simple and eliminate harmless floating-point noise."""
    return None if value is None else round(float(value), 8)


class SimpleMovingAverage:
    def __init__(self, period: int):
        self.period = period
        self.values: deque[float] = deque(maxlen=period)
        self.total = 0.0

    def update(self, value: float) -> float | None:
        if len(self.values) == self.period:
            self.total -= self.values[0]
        self.values.append(value)
        self.total += value
        return self.total / self.period if len(self.values) == self.period else None


class ExponentialMovingAverage:
    """Seed with the simple average of the first N observations, then recurse."""
    def __init__(self, period: int):
        self.period = period
        self.alpha = 2.0 / (period + 1)
        self.count = 0
        self.seed_total = 0.0
        self.value: float | None = None

    def update(self, price: float) -> float | None:
        if self.value is None:
            self.seed_total += price
            self.count += 1
            if self.count == self.period:
                self.value = self.seed_total / self.period
        else:
            self.value = self.value + self.alpha * (price - self.value)
        return self.value


class WilderRSI:
    """RSI(14), Wilder smoothing; first result after 14 CLOSE changes (15 bars)."""
    def __init__(self, period: int = 14):
        self.period = period
        self.prev: float | None = None
        self.n = 0
        self.seed_gains = self.seed_losses = 0.0
        self.avg_gain: float | None = None
        self.avg_loss: float | None = None

    def update(self, price: float) -> float | None:
        if self.prev is None:
            self.prev = price
            return None
        change = price - self.prev
        self.prev = price
        gain, loss = max(change, 0.0), max(-change, 0.0)
        if self.avg_gain is None:
            self.seed_gains += gain
            self.seed_losses += loss
            self.n += 1
            if self.n < self.period:
                return None
            self.avg_gain = self.seed_gains / self.period
            self.avg_loss = self.seed_losses / self.period
        else:
            self.avg_gain = ((self.period - 1) * self.avg_gain + gain) / self.period
            self.avg_loss = ((self.period - 1) * self.avg_loss + loss) / self.period
        if self.avg_gain == 0 and self.avg_loss == 0:
            return 50.0
        if self.avg_loss == 0:
            return 100.0
        return 100.0 - (100.0 / (1.0 + self.avg_gain / self.avg_loss))


class WilderATR:
    """True range smoothed by Wilder's method; first bar uses high-low."""
    def __init__(self, period: int = 14):
        self.period = period
        self.previous_close: float | None = None
        self.seed_sum = 0.0
        self.count = 0
        self.value: float | None = None

    def update(self, high: float, low: float, close: float) -> float | None:
        tr = high - low if self.previous_close is None else max(
            high - low, abs(high - self.previous_close), abs(low - self.previous_close)
        )
        self.previous_close = close
        if self.value is None:
            self.seed_sum += tr
            self.count += 1
            if self.count == self.period:
                self.value = self.seed_sum / self.period
        else:
            self.value = (self.value * (self.period - 1) + tr) / self.period
        return self.value


class IndicatorEngine:
    """One instance per CONTIGUOUS candle run; reset after a missing interval."""
    def __init__(self):
        self.sma20 = SimpleMovingAverage(20)
        self.sma50 = SimpleMovingAverage(50)
        self.ema9 = ExponentialMovingAverage(9)
        self.ema21 = ExponentialMovingAverage(21)
        self.ema50 = ExponentialMovingAverage(50)
        self.ema12_macd = ExponentialMovingAverage(12)
        self.ema26_macd = ExponentialMovingAverage(26)
        self.macd_signal = ExponentialMovingAverage(9)
        self.rsi = WilderRSI(14)
        self.atr = WilderATR(14)
        self.bb_prices: deque[float] = deque(maxlen=20)

    def update(self, candle: dict) -> dict:
        close = float(candle["close"])
        high, low = float(candle["high"]), float(candle["low"])
        sma20 = self.sma20.update(close)
        sma50 = self.sma50.update(close)
        ema9 = self.ema9.update(close)
        ema21 = self.ema21.update(close)
        ema50 = self.ema50.update(close)
        rsi = self.rsi.update(close)
        e12, e26 = self.ema12_macd.update(close), self.ema26_macd.update(close)
        macd = e12 - e26 if e12 is not None and e26 is not None else None
        signal = self.macd_signal.update(macd) if macd is not None else None
        hist = macd - signal if signal is not None else None
        self.bb_prices.append(close)
        middle = upper = lower = width = None
        if len(self.bb_prices) == 20:
            middle = sum(self.bb_prices) / 20
            stdev = pstdev(self.bb_prices)  # population stdev, ddof=0
            upper, lower = middle + 2 * stdev, middle - 2 * stdev
            width = 100 * (upper - lower) / middle if middle else None
        atr = self.atr.update(high, low, close)
        result = dict(zip(INDICATOR_FIELDS, map(number, (
            sma20, sma50, ema9, ema21, ema50, rsi, macd, signal,
            hist, middle, upper, lower, width, atr
        ))))
        return result
