"""Shared project settings: all candle timestamps use UTC."""

SYMBOL = "BTCUSD"
TIMEFRAMES = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400}
INDICATOR_FIELDS = (
    "sma_20", "sma_50", "ema_9", "ema_21", "ema_50", "rsi_14",
    "macd", "macd_signal", "macd_histogram", "bb_middle", "bb_upper",
    "bb_lower", "bb_width_pct", "atr_14",
)
