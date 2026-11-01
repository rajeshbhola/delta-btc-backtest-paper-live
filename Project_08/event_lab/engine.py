"""Educational event-driven futures simulator (never connects to an exchange)."""
from dataclasses import dataclass
from datetime import timedelta
from itertools import count
from math import isfinite
from .data import INTERVALS, iso, parse_dt


@dataclass
class Settings:
    timeframe: str = "5m"
    capital_usd: float = 10000.0
    contracts_per_order: int = 5
    contract_btc: float = 0.001  # example BTCUSD specification, verify current product metadata
    fee_bps: float = 5.0         # illustration: taker fee, 5 basis points
    gst_pct: float = 18.0        # illustrative India GST on trading fee
    spread_bps: float = 1.0      # full spread; half charged per fill
    slippage_bps: float = 1.0    # additional adverse impact per fill
    max_fill_contracts: int = 5
    max_leverage: float = 2.0    # simple notional/equity cap, NOT liquidation simulation
    mode: str = "long_short"

    def validate(self):
        if self.timeframe not in INTERVALS or self.mode not in ("long_short", "long_only"):
            raise ValueError("Invalid timeframe or mode")
        for key in ("capital_usd", "contract_btc", "max_leverage"):
            if not isfinite(getattr(self, key)) or getattr(self, key) <= 0:
                raise ValueError(f"{key} must be positive")
        for key in ("contracts_per_order", "max_fill_contracts"):
            if type(getattr(self, key)) is not int or getattr(self, key) <= 0:
                raise ValueError(f"{key} must be a positive integer")
        for key in ("fee_bps", "gst_pct", "spread_bps", "slippage_bps"):
            if not isfinite(getattr(self, key)) or getattr(self, key) < 0:
                raise ValueError(f"{key} must be non-negative")
        if self.spread_bps + 2 * self.slippage_bps >= 10000:
            raise ValueError("Transaction impact is unrealistically large")


def execute(candles, signals, cfg: Settings):
    cfg.validate()
    cash = cfg.capital_usd
    size = 0  # signed number of open contracts
    avg_entry = 0.0
    first_entry_at = None
    open_entry_fees = 0.0
    order_ids = count(1)
    pending = []
    orders, fills, trades, events, equity_rows = [], [], [], [], []
    previous_dt = None
    previous_close = None
    total_fees = 0.0
    max_notional = 0.0
    gap_count = 0

    def event(kind, when, **fields):
        events.append({"type": kind, "time_utc": when, **fields})

    def new_order(action, qty, when, reason):
        o = {"id": next(order_ids), "action": action, "requested_contracts": qty,
             "remaining_contracts": qty, "created_utc": when, "status": "PENDING", "reason": reason}
        pending.append(o)
        orders.append(o)
        event("ORDER", when, order_id=o["id"], action=action, contracts=qty)

    for bar in candles:
        start_dt = parse_dt(bar["timestamp_utc"])
        start, end = iso(start_dt), iso(start_dt + timedelta(seconds=INTERVALS[cfg.timeframe]))
        contiguous = previous_dt is None or (start_dt - previous_dt).total_seconds() == INTERVALS[cfg.timeframe]
        if not contiguous:
            gap_count += 1
            event("DATA_GAP", start, previous=iso(previous_dt), missing_intervals=int((start_dt-previous_dt).total_seconds()/INTERVALS[cfg.timeframe])-1)
            for o in pending:
                o["status"] = "CANCELLED_GAP"
                event("ORDER_CANCEL", start, order_id=o["id"], reason="Data gap: price unobservable")
            pending.clear()
        open_price = float(bar["open"])
        close_price = float(bar["close"])
        event("MARKET_OPEN", start, price=open_price)

        available = cfg.max_fill_contracts
        still_pending = []
        for o in pending:
            if available == 0:
                still_pending.append(o)
                continue
            action = o["action"]
            qty = min(available, o["remaining_contracts"])
            is_buy = action in ("OPEN_LONG", "CLOSE_SHORT")
            multiplier = 1 + (1 if is_buy else -1) * (cfg.spread_bps/2 + cfg.slippage_bps) / 10000
            fill_price = open_price * multiplier
            notional = qty * cfg.contract_btc * fill_price
            fee = notional * cfg.fee_bps / 10000 * (1 + cfg.gst_pct/100)
            mark_equity = cash + size*cfg.contract_btc*(open_price-avg_entry)
            if action.startswith("OPEN"):
                correct = size >= 0 if is_buy else size <= 0
                projected = (abs(size)+qty)*cfg.contract_btc*fill_price
                if not correct or mark_equity <= 0 or projected > mark_equity*cfg.max_leverage or cash < fee:
                    o["status"] = "REJECTED_RISK"
                    event("ORDER_REJECT", start, order_id=o["id"], reason="Notional exceeds leverage/equity cap or incompatible position")
                    continue
                old_qty = abs(size)
                avg_entry = ((avg_entry*old_qty + fill_price*qty)/(old_qty+qty)) if old_qty else fill_price
                if old_qty == 0:
                    first_entry_at = start
                size += qty * (1 if is_buy else -1)
                open_entry_fees += fee
                cash -= fee
            else:
                correct = (size > 0 and action == "CLOSE_LONG") or (size < 0 and action == "CLOSE_SHORT")
                if not correct or qty > abs(size):
                    o["status"] = "REJECTED_POSITION"
                    event("ORDER_REJECT", start, order_id=o["id"], reason="No compatible open position")
                    continue
                old_qty = abs(size)
                gross = qty * cfg.contract_btc * (fill_price-avg_entry) * (1 if size > 0 else -1)
                allocated_entry_fee = open_entry_fees * qty/old_qty
                open_entry_fees -= allocated_entry_fee
                cash += gross - fee
                trades.append({"entry_utc": first_entry_at, "exit_utc": start,
                               "side": "LONG" if size > 0 else "SHORT", "contracts": qty,
                               "entry_price": round(avg_entry, 8), "exit_price": round(fill_price, 8),
                               "gross_pnl_usd": round(gross, 8),
                               "entry_fee_usd": round(allocated_entry_fee, 8), "exit_fee_usd": round(fee, 8),
                               "net_pnl_usd": round(gross-allocated_entry_fee-fee, 8)})
                size -= qty * (1 if size > 0 else -1)
                if size == 0:
                    avg_entry, open_entry_fees, first_entry_at = 0.0, 0.0, None
            total_fees += fee
            available -= qty
            o["remaining_contracts"] -= qty
            o["status"] = "FILLED" if o["remaining_contracts"] == 0 else "PARTIAL"
            fills.append({"order_id": o["id"], "time_utc": start, "action": action, "contracts": qty,
                          "mid_open_price": open_price, "fill_price": round(fill_price, 8),
                          "notional_usd": round(notional, 8), "fee_incl_gst_usd": round(fee, 8)})
            event("FILL", start, order_id=o["id"], contracts=qty, price=round(fill_price, 6))
            if o["remaining_contracts"]:
                still_pending.append(o)
        pending[:] = still_pending
        max_notional = max(max_notional, abs(size)*cfg.contract_btc*close_price)
        unrealized = size * cfg.contract_btc * (close_price-avg_entry)
        eq = cash + unrealized
        equity_rows.append({"time_utc": end, "equity_usd": round(eq, 8), "cash_usd": round(cash, 8),
                            "unrealized_usd": round(unrealized, 8), "signed_contracts": size,
                            "close_price": close_price})
        event("MARKET_CLOSE", end, price=close_price, equity_usd=round(eq, 6))
        s = signals.get(start, {"signal": "HOLD"})
        signal = s.get("signal", "HOLD")
        if signal != "HOLD":
            event("SIGNAL", end, signal=signal, reason=s.get("reason", ""))
        if pending or s.get("gap_before") or not contiguous:
            if signal != "HOLD":
                event("SIGNAL_SKIPPED", end, reason="Pending order / gap / indicator reset")
        elif signal == "BUY":
            if size < 0:
                new_order("CLOSE_SHORT", abs(size), end, "BUY closes short")
            elif size == 0:
                new_order("OPEN_LONG", cfg.contracts_per_order, end, "BUY opens long")
        elif signal == "SELL":
            if size > 0:
                new_order("CLOSE_LONG", abs(size), end, "SELL closes long")
            elif size == 0 and cfg.mode == "long_short":
                new_order("OPEN_SHORT", cfg.contracts_per_order, end, "SELL opens short")
        previous_dt = start_dt
        previous_close = close_price

    # Orders that have no next candle will remain pending, never silently filled.
    peak = cfg.capital_usd
    max_dd = 0.0
    for p in equity_rows:
        peak = max(peak, p["equity_usd"])
        dd = (p["equity_usd"] / peak-1) * 100 if peak else -100.0
        p["drawdown_pct"] = round(dd, 6)
        max_dd = min(max_dd, dd)
    end_equity = equity_rows[-1]["equity_usd"]
    winners = sum(1 for t in trades if t["net_pnl_usd"] > 0)
    summary = {"timeframe": cfg.timeframe, "mode": cfg.mode, "start_capital_usd": cfg.capital_usd,
               "ending_equity_usd": round(end_equity, 6), "return_pct": round((end_equity/cfg.capital_usd-1)*100, 6),
               "max_drawdown_pct": round(max_dd, 6), "closed_trade_fills": len(trades),
               "win_rate_pct": round(winners/len(trades)*100, 4) if trades else None,
               "total_fees_incl_gst_usd": round(total_fees, 8),
               "realized_gross_pnl_usd": round(sum(t["gross_pnl_usd"] for t in trades), 6),
               "open_signed_contracts": size, "open_unrealized_pnl_usd": round(equity_rows[-1]["unrealized_usd"], 6),
               "pending_order_count": len(pending), "gap_count": gap_count, "max_notional_usd": round(max_notional, 6),
               "order_count": len(orders), "fill_count": len(fills), "event_count": len(events),
               "assumptions": {"contract_btc": cfg.contract_btc,"fee_bps": cfg.fee_bps,"gst_pct": cfg.gst_pct,
                               "spread_bps": cfg.spread_bps,"slippage_bps": cfg.slippage_bps,
                               "max_leverage": cfg.max_leverage,"max_fill_contracts_per_bar": cfg.max_fill_contracts,
                               "currency": "USD-equivalent simulation, NOT Delta INR account ledger",
                               "funding": "not modeled", "liquidation": "not modeled",
                               "fills": "market orders at next contiguous candle OPEN; no intrabar stop/limit simulation"}}
    return {"summary": summary, "orders": orders, "fills": fills, "trades": trades, "events": events,
            "equity": equity_rows, "candles": candles}
