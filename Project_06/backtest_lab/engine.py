"""One-asset, 1x-notional, vectorized *educational* backtest.

Signal on candle i closes at t[i]+interval. Position changes only at
next *available, contiguous* candle's open. Returns use open-to-next-open
(or final open-to-close). Long-only by default, no leverage/margin/liquidation.
Position returns are continuously rebalanced to 100% notional per bar.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BacktestConfig:
    starting_capital: float = 10000.0  # simulated USD, NOT actual INR account equity
    mode: str = "long_only"             # long_only: SELL exits; long_short: SELL opens shorts
    fee_bps: float = 0.0                # next project implements real detailed costs

    def __post_init__(self):
        if not np.isfinite(self.starting_capital) or self.starting_capital <= 0:
            raise ValueError("starting_capital must be positive")
        if self.mode not in {"long_only", "long_short"}:
            raise ValueError("mode must be long_only or long_short")
        if not np.isfinite(self.fee_bps) or not 0 <= self.fee_bps < 10000:
            raise ValueError("fee_bps must be between 0 and 10000")


def run_backtest(df: pd.DataFrame, config: BacktestConfig | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Input: validated chronological OHLCV with signal + gap_before from data.prepare()."""
    c = config or BacktestConfig()
    if df.empty:
        raise ValueError("No candles")
    required = {"timestamp_utc", "open", "close", "signal", "gap_before"}
    if not required.issubset(df.columns):
        raise ValueError(f"Missing columns: {required - set(df.columns)}")
    if not df["signal"].isin(["BUY", "SELL", "HOLD"]).all():
        raise ValueError("Invalid signal")
    n = len(df)
    # A BUY/SELL on bar i becomes tradable at the OPEN of bar i+1, never on i.
    direction = df["signal"].map({"BUY": 1, "SELL": (0 if c.mode == "long_only" else -1), "HOLD": np.nan})
    # Reset desired position at any gap before allowing a fresh next-bar signal.
    groups = df["gap_before"].astype(int).cumsum()
    target_after_close = direction.groupby(groups).ffill().fillna(0).astype(int)
    pos = target_after_close.shift(1, fill_value=0)
    pos = pos.where(~df["gap_before"], 0).astype(int).to_numpy()
    opens = df["open"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)
    # Last bar is marked at its close, and position is liquidated for reporting.
    next_prices = np.r_[opens[1:], closes[-1]]
    gross_returns = pos * (next_prices / opens - 1.0)
    gross_factors = 1.0 + gross_returns
    if np.any(gross_factors <= 0):
        raise ValueError("Backtest equity became nonpositive; this toy engine does not model liquidation")
    prev_pos = np.r_[0, pos[:-1]]
    exit_events = (prev_pos != 0) & (prev_pos != pos)
    entry_events = (pos != 0) & (prev_pos != pos)
    total_fees = exit_events.astype(int) + entry_events.astype(int)
    # End-of-history exit is charged at final close (if active).
    if pos[-1] != 0:
        total_fees[-1] += 1
    rate = c.fee_bps / 10000.0
    fee_factors = (1.0 - rate) ** total_fees
    factors = gross_factors * fee_factors
    equity = c.starting_capital * np.cumprod(factors)
    if (equity <= 0).any():
        raise ValueError("Equity became nonpositive")
    curve = pd.DataFrame({
        "timestamp_utc": df["timestamp_utc"].array,
        "mark_time_utc": pd.concat([df["timestamp_utc"].iloc[1:], df["bar_close_utc"].iloc[-1:]], ignore_index=True).array if "bar_close_utc" in df else df["timestamp_utc"].array,
        "open": opens,
        "close": closes,
        "signal": df["signal"].to_numpy(),
        "position": pos,
        "gap_before": df["gap_before"].to_numpy(),
        "mark_price": next_prices,
        "gross_return": gross_returns,
        "fee_events": total_fees,
        "net_return": factors - 1.0,
        "equity": equity,
    })
    full_equity = np.r_[c.starting_capital, equity]
    high_water = np.maximum.accumulate(full_equity)
    curve["drawdown_pct"] = ((full_equity[1:] / high_water[1:]) - 1.0) * 100
    trades = _build_trades(df, pos, gross_factors, c)
    profit = trades["net_pnl"].to_numpy(dtype=float) if not trades.empty else np.array([])
    winners = profit[profit > 0].sum()
    losers = -profit[profit < 0].sum()
    gross_strategy_equity = c.starting_capital * np.prod(gross_factors)
    summary = {
        "mode": c.mode, "starting_capital_usd": c.starting_capital,
        "ending_capital_usd": float(equity[-1]),
        "gross_return_pct_before_fees": float((gross_strategy_equity / c.starting_capital - 1) * 100),
        "net_return_pct": float((equity[-1] / c.starting_capital - 1) * 100),
        "max_drawdown_pct": float((full_equity / high_water - 1.0).min() * 100),
        "trade_count": int(len(trades)),
        "win_rate_pct": float((profit > 0).mean() * 100) if profit.size else 0.0,
        "profit_factor": float(winners / losers) if losers > 0 else None,
        "total_net_pnl_usd": float(equity[-1] - c.starting_capital),
        "fee_bps_per_side": c.fee_bps,
        "exposure_pct": float(np.count_nonzero(pos) / n * 100),
        "signal_counts": {key: int((df["signal"] == key).sum()) for key in ["BUY", "SELL", "HOLD"]},
        "candles": n,
        "note": "Educational, synthetic-equity model. 1x notional, end-of-history liquidation; excludes spread, slippage, funding, GST, margin/liquidation, and real Delta fees. See Project 7.",
    }
    # Trades are reconstructed from contiguous position *runs*; each run
    # includes one entry and one exit fee. They reconcile to equity exactly.
    if not np.isclose(trades["net_pnl"].sum() if not trades.empty else 0.0,
                      equity[-1] - c.starting_capital, rtol=0, atol=0.005):
        raise AssertionError("Trade ledger did not reconcile with equity")
    return curve, trades, summary


def _build_trades(df: pd.DataFrame, pos: np.ndarray, gross: np.ndarray, c: BacktestConfig) -> pd.DataFrame:
    records = []
    rate = c.fee_bps / 10000.0
    start_equity = c.starting_capital
    size = len(pos)
    i = 0
    while i < size:
        if pos[i] == 0:
            i += 1
            continue
        direction = int(pos[i])
        j = i
        while j + 1 < size and pos[j + 1] == direction:
            j += 1
        entry_price = float(df.iloc[i]["open"])
        exit_price = float(df.iloc[j + 1]["open"]) if j + 1 < size else float(df.iloc[-1]["close"])
        exit_time = df.iloc[j + 1]["timestamp_utc"] if j + 1 < size else (df.iloc[-1]["bar_close_utc"] if "bar_close_utc" in df else df.iloc[-1]["timestamp_utc"])
        compounded_return = float(np.prod(gross[i:j + 1]))
        entry_fee = start_equity * rate
        equity_after_entry = start_equity - entry_fee
        before_exit = equity_after_entry * compounded_return
        exit_fee = before_exit * rate
        end_equity = before_exit - exit_fee
        records.append({
            "side": "LONG" if direction == 1 else "SHORT",
            "entry_time_utc": df.iloc[i]["timestamp_utc"],
            "exit_time_utc": exit_time,
            "exit_at_last_close": j == size - 1,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "bars_held": j - i + 1,
            "entry_equity_usd": start_equity,
            "gross_pnl_usd": before_exit - equity_after_entry,
            "fee_paid_usd": entry_fee + exit_fee,
            "net_pnl": end_equity - start_equity,
            "net_pnl_pct": (end_equity / start_equity - 1.0) * 100,
            "exit_equity_usd": end_equity,
        })
        start_equity = end_equity
        i = j + 1
    return pd.DataFrame.from_records(records, columns=[
        "side", "entry_time_utc", "exit_time_utc", "exit_at_last_close", "entry_price", "exit_price",
        "bars_held", "entry_equity_usd", "gross_pnl_usd", "fee_paid_usd", "net_pnl", "net_pnl_pct", "exit_equity_usd",
    ])
