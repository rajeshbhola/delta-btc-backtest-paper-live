"""Simple, cost-aware, NEXT OPEN backtest on an isolated evaluation window.

Notes: 1x exposure, synthetic execution spread/slippage, no stops, funding,
liquidation, real market liquidity, Delta contract sizing, or margin accounting.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class CostConfig:
    fee_bps: float = 5.0             # illustrative taker commission
    gst_percent: float = 18.0
    spread_bps: float = 1.0          # FULL bid/ask spread
    slippage_bps: float = 1.0        # per transaction

    @property
    def per_side_fraction(self) -> float:
        values = (self.fee_bps, self.gst_percent, self.spread_bps, self.slippage_bps)
        if any(v < 0 for v in values):
            raise ValueError("Trading-cost assumptions cannot be negative")
        return (self.fee_bps*(1+self.gst_percent/100) + self.spread_bps/2 + self.slippage_bps)/10000


def simulate_window(df: pd.DataFrame, targets: np.ndarray, start: int, end: int,
                    costs: CostConfig | None = None, capital: float = 10000.0,
                    include_curve: bool = False) -> dict:
    """Evaluate [start,end). Targets[i-1] known after CLOSE[i-1].

    At window boundaries, start flat / force close at last candle close.
    All windows are independent to avoid position leakage across fold splits.
    """
    if start < 0 or end > len(df) or end - start < 3 or len(targets) != len(df):
        raise ValueError("Invalid window or mismatched signal length")
    if capital <= 0:
        raise ValueError("Starting capital must be positive")
    c = (costs or CostConfig()).per_side_fraction
    opens = df["open"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)
    timestamps = df["timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ").tolist() if include_curve else None
    equity = float(capital)
    peak = equity
    worst_dd = 0.0
    pos = 0
    n_trades = 0
    wins = 0
    trade_entry_equity = None
    outcomes = []
    curve = []
    for i in range(start, end):
        if i > start:
            # Price change since previous open applies to EXISTING position only.
            equity *= 1 + pos * (opens[i]/opens[i-1] - 1)
            if equity <= 0:
                raise ValueError("Simulated equity depleted; 1x strategy exceeded simplified model")
            desired = int(targets[i-1])  # last FINISHED candle only
            if desired != pos:
                prev = pos
                if prev != 0:
                    equity *= (1-c)  # close previous leg
                    n_trades += 1
                    trade_pnl = equity - trade_entry_equity
                    wins += int(trade_pnl > 0)
                    outcomes.append(round(float(trade_pnl), 6))
                    trade_entry_equity = None
                if desired != 0:
                    trade_entry_equity = equity
                    equity *= (1-c)  # open new leg
                pos = desired
        peak = max(peak, equity)
        worst_dd = min(worst_dd, (equity/peak-1)*100)
        if include_curve:
            curve.append({"time_utc": timestamps[i], "equity_usd": round(equity, 6), "position": pos})
    # Final candle OPEN -> CLOSE and forced closing transaction.
    equity *= 1 + pos*(closes[end-1]/opens[end-1]-1)
    if pos:
        equity *= (1-c)
        n_trades += 1
        trade_pnl = equity - trade_entry_equity
        wins += int(trade_pnl > 0)
        outcomes.append(round(float(trade_pnl), 6))
    peak = max(peak, equity)
    worst_dd = min(worst_dd, (equity/peak-1)*100)
    if include_curve:
        curve.append({"time_utc": timestamps[end-1], "equity_usd": round(equity, 6), "position": 0, "final_close": True})
    out = {
        "start_utc": df.iloc[start]["timestamp_utc"].isoformat(),
        "end_utc": df.iloc[end-1]["timestamp_utc"].isoformat(),
        "bars": end-start,
        "start_capital_usd": capital,
        "end_equity_usd": round(equity, 6),
        "net_return_pct": round((equity/capital-1)*100, 6),
        "max_drawdown_pct": round(worst_dd, 6),
        "closed_trades": n_trades,
        "win_rate_pct": round(wins/n_trades*100, 4) if n_trades else None,
    }
    if include_curve:
        out["equity_curve"] = curve
        out["trade_pnl_usd"] = outcomes
    return out


def score(report: dict, min_trades: int) -> float:
    if report["closed_trades"] < min_trades:
        return float("-inf")
    # Simple deterministic learning objective, not a guaranteed optimal metric.
    return report["net_return_pct"] + 0.5*report["max_drawdown_pct"]
