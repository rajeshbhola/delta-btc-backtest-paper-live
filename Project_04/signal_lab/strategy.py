"""Pure, streaming EMA crossover + RSI confirmation strategy; NO orders.

Uses only the current completed candle and previously completed candles.
BUY and SELL are directional *research labels*, not broker trade instructions.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from .config import SignalConfig


class SignalGenerator:
    def __init__(self, config: SignalConfig | None = None):
        self.config = config or SignalConfig()
        self.previous_difference: float | None = None

    def update(self, row: dict, timestamp: datetime, interval_seconds: int, *, gap: bool = False) -> dict:
        if timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        decision_time = timestamp + timedelta(seconds=interval_seconds)
        ema_fast = row.get("ema_9")
        ema_slow = row.get("ema_21")
        rsi = row.get("rsi_14")
        signal, reason = "HOLD", "NO_CROSSOVER"
        if gap:
            self.previous_difference = None
        if ema_fast is None or ema_slow is None or rsi is None:
            signal, reason = "HOLD", "INDICATOR_NOT_READY"
            self.previous_difference = None
        else:
            current_difference = float(ema_fast) - float(ema_slow)
            if gap:
                reason = "GAP_RESET"
            elif self.previous_difference is None:
                reason = "BASELINE"
            elif self.previous_difference <= 0 < current_difference:
                if self.config.rsi_buy_min <= float(rsi) <= self.config.rsi_buy_max:
                    signal, reason = "BUY", "BULLISH_EMA_CROSSOVER_RSI_CONFIRMED"
                else:
                    reason = "BULLISH_CROSSOVER_RSI_REJECTED"
            elif self.previous_difference >= 0 > current_difference:
                if self.config.rsi_sell_min <= float(rsi) <= self.config.rsi_sell_max:
                    signal, reason = "SELL", "BEARISH_EMA_CROSSOVER_RSI_CONFIRMED"
                else:
                    reason = "BEARISH_CROSSOVER_RSI_REJECTED"
            self.previous_difference = current_difference
        return {
            "timestamp_utc": timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "decision_time_utc": decision_time.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "close": float(row["close"]),
            "ema_9": None if ema_fast is None else float(ema_fast),
            "ema_21": None if ema_slow is None else float(ema_slow),
            "rsi_14": None if rsi is None else float(rsi),
            "signal": signal,
            "reason": reason,
            "gap_before": bool(gap),
        }
