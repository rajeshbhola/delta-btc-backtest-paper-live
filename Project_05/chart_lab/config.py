from datetime import timedelta

SYMBOL = "BTCUSD"
TIMEFRAMES = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400}
INDICATORS = (
    "sma_20", "sma_50", "ema_9", "ema_21", "ema_50",
    "rsi_14", "macd", "macd_signal", "macd_histogram",
    "bb_middle", "bb_upper", "bb_lower", "atr_14",
)
OVERLAYS = ("ema_9", "ema_21", "ema_50", "sma_20", "sma_50", "bb_upper", "bb_middle", "bb_lower")

def candle_interval(timeframe: str) -> timedelta:
    if timeframe not in TIMEFRAMES:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    return timedelta(seconds=TIMEFRAMES[timeframe])
