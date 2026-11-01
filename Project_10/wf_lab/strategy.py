"""Causal EMA-trend + RSI confirmation indicators, no forward-looking inputs."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class StrategyParams:
    fast_ema: int
    slow_ema: int
    rsi_threshold: int

    def validate(self) -> None:
        if not (2 <= self.fast_ema < self.slow_ema <= 300):
            raise ValueError("Require 2 <= fast EMA < slow EMA <= 300")
        if not (50 <= self.rsi_threshold <= 75):
            raise ValueError("RSI threshold must be between 50 and 75")

    def to_dict(self):
        return asdict(self)


def rsi_wilder(close: pd.Series, length: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1/length, adjust=False, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1/length, adjust=False, min_periods=length).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    result = 100 - 100 / (1 + rs)
    result = result.mask((avg_loss == 0) & (avg_gain > 0), 100)
    result = result.mask((avg_loss > 0) & (avg_gain == 0), 0)
    return result.mask((avg_loss == 0) & (avg_gain == 0), 50)


def target_positions(df: pd.DataFrame, params: StrategyParams, *, mode: str = "long_short") -> np.ndarray:
    """Signal at CLOSE[i], executed no earlier than OPEN[i+1].

    Value 1=long, -1=short, 0=flat. This is an EMA *trend* filter,
    not a crossover-only entry system.
    """
    params.validate()
    if mode not in {"long_only", "long_short"}:
        raise ValueError("mode must be long_only or long_short")
    close = df["close"].astype(float)
    fast = close.ewm(span=params.fast_ema, adjust=False, min_periods=params.fast_ema).mean()
    slow = close.ewm(span=params.slow_ema, adjust=False, min_periods=params.slow_ema).mean()
    rsi = rsi_wilder(close)
    long_mask = (fast > slow) & (rsi >= params.rsi_threshold)
    short_mask = (fast < slow) & (rsi <= 100 - params.rsi_threshold)
    targets = np.zeros(len(close), dtype=np.int8)
    targets[long_mask.to_numpy()] = 1
    if mode == "long_short":
        targets[short_mask.to_numpy()] = -1
    return targets
