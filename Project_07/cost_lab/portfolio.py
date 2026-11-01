"""Standalone portfolio cost-sensitivity tool for Project 6 trade JSON."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
import json
import math
from .model import Costs, Trade, calculate, funding_snapshots, CONTRACT_BTC

SUPPORTED = {"1m", "5m", "15m", "1h", "4h"}


def load_trades(path: str | Path, *, timeframe: str = "5m") -> list[dict]:
    path = Path(path)
    if path.is_dir():
        if timeframe not in SUPPORTED:
            raise ValueError("timeframe must be 1m, 5m, 15m, 1h, or 4h")
        target = path / "trades" / f"BTCUSD_{timeframe}.json"
        if not target.exists():
            target = path / f"BTCUSD_{timeframe}.json"
        path = target
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("Expected a JSON array of trades")
    if not rows:
        raise ValueError("The selected trade file is empty")
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or not {"side", "entry_price", "exit_price"}.issubset(row):
            raise ValueError(f"Trade {i} is missing side/entry_price/exit_price")
    return rows


def _drawdown(curve: list[float]) -> float:
    peak = curve[0]
    worst = 0.0
    for equity in curve:
        peak = max(peak, equity)
        worst = min(worst, (equity / peak - 1) * 100)
    return worst


def run_portfolio(rows: list[dict], costs: Costs = Costs(), *, capital: float = 10000.0,
                  sizing: str = "fixed", contracts: int = 10, estimate_funding: bool = True,
                  entry_order: str = "taker", exit_order: str = "taker") -> dict:
    if not rows:
        raise ValueError("No trades")
    if not math.isfinite(capital) or capital <= 0:
        raise ValueError("capital must be positive")
    if sizing not in {"fixed", "one_x"}:
        raise ValueError("sizing must be fixed or one_x")
    if not isinstance(contracts, int) or contracts <= 0:
        raise ValueError("contracts must be positive integer")
    net_equity = capital
    gross_equity = capital
    records = []
    for i, record in enumerate(rows, start=1):
        entry = float(record["entry_price"])
        exit_price = float(record["exit_price"])
        if sizing == "one_x":
            current_contracts = int(math.floor(net_equity / (entry * CONTRACT_BTC)))
            if current_contracts < 1:
                raise ValueError(f"Trade {i}: equity cannot afford one 1x BTCUSD contract")
        else:
            current_contracts = contracts
        events = 0
        if estimate_funding and record.get("entry_time_utc") and record.get("exit_time_utc"):
            events = funding_snapshots(record["entry_time_utc"], record["exit_time_utc"])
        else:
            events = int(record.get("funding_events", 0)) if estimate_funding else 0
        trade = Trade(side=record["side"], entry_price=entry, exit_price=exit_price,
                      contracts=current_contracts, entry_order=entry_order,
                      exit_order=exit_order, funding_events=events)
        result = calculate(trade, costs)
        gross_equity += result["gross_reference_pnl_usd"]
        net_equity += result["net_pnl_usd"]
        if net_equity <= 0 or gross_equity <= 0:
            raise ValueError(f"Trade {i}: simulated equity became nonpositive; lower sizing or remove leverage")
        records.append({"trade_number": i, "side": trade.side,
                        "entry_time_utc": record.get("entry_time_utc"),
                        "exit_time_utc": record.get("exit_time_utc"),
                        "entry_reference_usd": entry, "exit_reference_usd": exit_price,
                        "contracts": current_contracts, "funding_events_assumed": events,
                        "gross_reference_pnl_usd": result["gross_reference_pnl_usd"],
                        "spread_cost_usd": result["spread_cost_usd"],
                        "slippage_cost_usd": result["slippage_cost_usd"],
                        "commission_usd": result["commission_usd"],
                        "gst_usd": result["gst_usd"],
                        "funding_paid_usd": result["funding_paid_usd"],
                        "net_pnl_usd": result["net_pnl_usd"],
                        "gross_equity_usd": gross_equity, "net_equity_usd": net_equity})
    breakdown = {name: sum(r[name] for r in records)
                 for name in ("spread_cost_usd", "slippage_cost_usd", "commission_usd", "gst_usd", "funding_paid_usd")}
    gross_curve = [capital] + [r["gross_equity_usd"] for r in records]
    net_curve = [capital] + [r["net_equity_usd"] for r in records]
    return {
        "summary": {"starting_capital_usd": capital, "gross_ending_equity_usd": gross_equity,
                    "net_ending_equity_usd": net_equity,
                    "gross_pnl_usd": gross_equity - capital, "net_pnl_usd": net_equity - capital,
                    "net_return_pct": (net_equity / capital - 1) * 100,
                    "gross_return_pct": (gross_equity / capital - 1) * 100,
                    "max_net_drawdown_pct": _drawdown(net_curve),
                    "trade_count": len(records),
                    "net_winning_trades": sum(r["net_pnl_usd"] > 0 for r in records),
                    "total_costs_usd": sum(breakdown.values()),
                    "breakdown": breakdown, "sizing": sizing,
                    "fx_usd_inr_assumption": costs.fx_usd_inr,
                    "note": "Trade-price scenario, NOT a rerun of Project 6. Project 6 rebalances on every bar; this tool uses fixed integer lots per trade. Portfolio curves and sizing may therefore differ. Funding uses assumed rate/snapshots."},
        "trades": records,
        "cost_assumptions": costs.__dict__,
    }
