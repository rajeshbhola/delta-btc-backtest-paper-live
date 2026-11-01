"""Transparent, deliberately simplified Delta Exchange India BTCUSD fee scenarios.

All accounting is in USD-equivalent. Delta India actually margins/settles in INR:
the optional manually entered USD/INR rate is only a display conversion.
Actual fees may use exchange index/spot notional and funding settlement marks.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
import math

CONTRACT_BTC = 0.001  # BTCUSD lot size; verify current contract specifications
DEFAULT_FEE_BPS = {"maker": 2.0, "taker": 5.0}


def finite(name: str, value: float, *, positive: bool = False, nonnegative: bool = False) -> None:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite number")
    if positive and value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    if nonnegative and value < 0:
        raise ValueError(f"{name} must be nonnegative")


@dataclass(frozen=True)
class Costs:
    maker_fee_bps: float = 2.0
    taker_fee_bps: float = 5.0
    gst_pct: float = 18.0
    spread_bps: float = 2.0    # FULL quoted bid-ask spread, half charged per side
    slippage_bps: float = 1.0  # adverse per executed side
    funding_rate_pct: float = 0.01  # signed rate per funding snapshot; + means longs pay
    fx_usd_inr: float = 85.0    # USER ASSUMPTION, not a live exchange rate
    leverage: float = 2.0

    def __post_init__(self):
        for name in ("maker_fee_bps", "taker_fee_bps", "gst_pct", "spread_bps", "slippage_bps"):
            finite(name, getattr(self, name), nonnegative=True)
        finite("funding_rate_pct", self.funding_rate_pct)
        finite("fx_usd_inr", self.fx_usd_inr, positive=True)
        finite("leverage", self.leverage, positive=True)
        if self.gst_pct > 100:
            raise ValueError("GST percent must be <= 100")
        if self.spread_bps >= 10000 or self.slippage_bps >= 10000:
            raise ValueError("spread/slippage are too large")


@dataclass(frozen=True)
class Trade:
    side: str = "LONG"
    entry_price: float = 100000.0  # reference midpoint (USD per BTC)
    exit_price: float = 101000.0
    contracts: int = 10
    entry_order: str = "taker"
    exit_order: str = "taker"
    funding_events: int = 0

    def __post_init__(self):
        if self.side not in {"LONG", "SHORT"}:
            raise ValueError("side must be LONG or SHORT")
        for name in ("entry_price", "exit_price"):
            finite(name, getattr(self, name), positive=True)
        if type(self.contracts) is not int or self.contracts <= 0:
            raise ValueError("contracts must be a positive integer")
        if self.entry_order not in DEFAULT_FEE_BPS or self.exit_order not in DEFAULT_FEE_BPS:
            raise ValueError("order types must be maker or taker")
        if type(self.funding_events) is not int or self.funding_events < 0:
            raise ValueError("funding_events must be a nonnegative integer")


def funding_snapshots(entry: str, exit: str) -> int:
    """Count STRICTLY interior assumed BTC funding boundaries 00/08/16 UTC.

    The first/last boundary is excluded because intraboundary order timing
    is unknowable from backtest timestamps alone. Validate against real funding.
    """
    def parse(s: str) -> datetime:
        ts = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            raise ValueError("Funding timestamps must have a timezone")
        return ts.astimezone(timezone.utc)
    start, end = parse(entry), parse(exit)
    if end <= start:
        raise ValueError("exit_time_utc must follow entry_time_utc")
    boundary = start.replace(hour=0, minute=0, second=0, microsecond=0)
    count = 0
    while boundary < end:
        if start < boundary < end:
            count += 1
        boundary += timedelta(hours=8)
    return count


def calculate(trade: Trade, costs: Costs = Costs()) -> dict:
    """Calculate a complete entry + exit for fixed, integral BTCUSD contracts.

    The spread/slippage adjust synthetic execution prices only. The costs are
    NOT subtracted a second time. Funding is signed (+cost, -credit).
    """
    d = 1 if trade.side == "LONG" else -1
    quantity_btc = trade.contracts * CONTRACT_BTC
    half_spread = costs.spread_bps / 20000.0
    slip = costs.slippage_bps / 10000.0
    # Long enters by BUY (+), exits by SELL (-); short reverses.
    entry_spread = trade.entry_price * (1 + d * half_spread)
    exit_spread = trade.exit_price * (1 - d * half_spread)
    actual_entry = trade.entry_price * (1 + d * (half_spread + slip))
    actual_exit = trade.exit_price * (1 - d * (half_spread + slip))
    reference_gross = d * quantity_btc * (trade.exit_price - trade.entry_price)
    after_spread_gross = d * quantity_btc * (exit_spread - entry_spread)
    execution_gross = d * quantity_btc * (actual_exit - actual_entry)
    spread_cost = reference_gross - after_spread_gross
    slippage_cost = after_spread_gross - execution_gross
    entry_fee_bps = costs.maker_fee_bps if trade.entry_order == "maker" else costs.taker_fee_bps
    exit_fee_bps = costs.maker_fee_bps if trade.exit_order == "maker" else costs.taker_fee_bps
    entry_fee = actual_entry * quantity_btc * entry_fee_bps / 10000.0
    exit_fee = actual_exit * quantity_btc * exit_fee_bps / 10000.0
    fee = entry_fee + exit_fee
    gst = fee * costs.gst_pct / 100.0
    # Funding uses entry reference notional as a constant MARK PRICE PROXY.
    # Exact exchange funding uses snapshot-dependent mark price and rate.
    funding_paid = d * (trade.entry_price * quantity_btc) * costs.funding_rate_pct / 100.0 * trade.funding_events
    net = execution_gross - fee - gst - funding_paid
    all_costs = spread_cost + slippage_cost + fee + gst + funding_paid
    answer = {
        "trade": asdict(trade),
        "assumptions": asdict(costs),
        "quantity_btc": quantity_btc,
        "reference_notional_usd": trade.entry_price * quantity_btc,
        "estimated_initial_margin_usd": trade.entry_price * quantity_btc / costs.leverage,
        "estimated_initial_margin_inr": trade.entry_price * quantity_btc / costs.leverage * costs.fx_usd_inr,
        "modeled_entry_fill_usd": actual_entry,
        "modeled_exit_fill_usd": actual_exit,
        "gross_reference_pnl_usd": reference_gross,
        "spread_cost_usd": spread_cost,
        "slippage_cost_usd": slippage_cost,
        "entry_fee_usd": entry_fee,
        "exit_fee_usd": exit_fee,
        "commission_usd": fee,
        "gst_usd": gst,
        "funding_paid_usd": funding_paid,
        "total_costs_usd": all_costs,
        "net_pnl_usd": net,
        "net_pnl_inr_estimate": net * costs.fx_usd_inr,
        "breakeven_reference_move_usd_approx": all_costs / quantity_btc,
        "net_pnl_pct_on_reference_notional": net / (trade.entry_price * quantity_btc) * 100,
        "currency_note": "USD-equivalent modeled PnL. INR numbers use manual indicative FX rate, not actual Delta settlement FX.",
        "limits": "Scenario model, not a broker statement: assumes both sides fill, no liquidation/partial fills, fixed full spread and per-side slippage, constant funding rate and entry notional proxy; actual fee notional may use index price.",
    }
    return answer
