"""Config for Project 4."""
from dataclasses import dataclass

SYMBOL = "BTCUSD"
TIMEFRAMES = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400}


@dataclass(frozen=True)
class SignalConfig:
    rsi_buy_min: float = 50.0
    rsi_buy_max: float = 75.0
    rsi_sell_min: float = 25.0
    rsi_sell_max: float = 50.0

    def __post_init__(self):
        if not (0 <= self.rsi_buy_min <= self.rsi_buy_max <= 100):
            raise ValueError("Buy RSI range must be between 0 and 100, min <= max")
        if not (0 <= self.rsi_sell_min <= self.rsi_sell_max <= 100):
            raise ValueError("Sell RSI range must be between 0 and 100, min <= max")
