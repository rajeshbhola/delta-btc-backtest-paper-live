"""Analyze recorded strategy equity and *closed* trades, not real-time prices.

Inputs match Mini-Project 8's summary.json, equity.json and trades.json.
No broker connection or trading capability exists in this project.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from math import isfinite, sqrt
from statistics import mean, median, stdev
from typing import Any

TIMEFRAME_SECONDS = {'1m': 60, '5m': 300, '15m': 900, '1h': 3600, '4h': 14400}
SECONDS_PER_YEAR = 365 * 24 * 3600  # Crypto trades every day.


def parse_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Timestamp must include a timezone (UTC Z or offset).')
    return dt.astimezone(timezone.utc)


def finite_float(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f'{field}: bool is not a price or amount')
    result = float(value)
    if not isfinite(result):
        raise ValueError(f'{field}: must be finite')
    return result


def round_or_none(value: float | None, digits: int = 6) -> float | None:
    return round(value, digits) if value is not None and isfinite(value) else None


def clean_equity(records: list[dict[str, Any]], warnings: list[str]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for number, row in enumerate(records, 1):
        try:
            dt = parse_utc(row['time_utc'])
            equity = finite_float(row['equity_usd'], 'equity_usd')
            if equity <= 0:
                raise ValueError('equity_usd must be positive for percentage-return metrics')
            price = None
            if row.get('close_price') is not None:
                price = finite_float(row['close_price'], 'close_price')
                if price <= 0:
                    price = None
            signed = finite_float(row.get('signed_contracts', 0), 'signed_contracts')
            cleaned.append({'dt': dt, 'time_utc': dt.isoformat().replace('+00:00','Z'),
                            'equity_usd': equity, 'signed_contracts': signed,
                            'close_price': price})
        except (KeyError, ValueError, TypeError, OverflowError) as exc:
            warnings.append(f'Equity row {number} skipped: {exc}')
    if cleaned != sorted(cleaned, key=lambda r: r['dt']):
        warnings.append('Equity timestamps were out of order; sorted chronologically.')
    cleaned.sort(key=lambda r: r['dt'])
    result = []
    for r in cleaned:
        if result and r['dt'] == result[-1]['dt']:
            warnings.append(f'Duplicate equity timestamp {r["time_utc"]}; retained first.')
            continue
        result.append(r)
    if len(result) < 2:
        raise ValueError('At least two positive, unique equity snapshots are required.')
    return result


def analyze_trades(records: list[dict[str, Any]], warnings: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    trades = []
    for i, row in enumerate(records, 1):
        try:
            pnl = finite_float(row['net_pnl_usd'], 'net_pnl_usd')
            gross = finite_float(row.get('gross_pnl_usd', pnl), 'gross_pnl_usd')
            entry_fee = finite_float(row.get('entry_fee_usd', 0), 'entry_fee_usd')
            exit_fee = finite_float(row.get('exit_fee_usd', 0), 'exit_fee_usd')
            entry, exit_ = parse_utc(row['entry_utc']), parse_utc(row['exit_utc'])
            if exit_ < entry:
                raise ValueError('exit occurs before entry')
            side = str(row.get('side', 'UNKNOWN')).upper()
            trades.append({
                'entry_utc': entry.isoformat().replace('+00:00','Z'),
                'exit_utc': exit_.isoformat().replace('+00:00','Z'),
                'side': side,
                'contracts': row.get('contracts', None),
                'gross_pnl_usd': round(gross, 8),
                'net_pnl_usd': round(pnl, 8),
                'fees_usd': round(entry_fee + exit_fee, 8),
                'holding_minutes': round((exit_-entry).total_seconds()/60, 3),
            })
        except (ValueError, KeyError, TypeError, OverflowError) as exc:
            warnings.append(f'Trade row {i} skipped: {exc}')
    pnls = [t['net_pnl_usd'] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    zeros = len(pnls) - len(wins) - len(losses)
    gross_profit, gross_loss = sum(wins), abs(sum(losses))
    streak = max_streak = 0
    for p in pnls:
        streak = streak + 1 if p < 0 else 0
        max_streak = max(max_streak, streak)
    metrics = {
        'closed_trades': len(trades),
        'winning_trades': len(wins), 'losing_trades': len(losses), 'breakeven_trades': zeros,
        'win_rate_pct': round_or_none(len(wins) / len(pnls) * 100 if pnls else None),
        'gross_profit_usd': round(sum(wins), 6),
        'gross_loss_usd': round(sum(losses), 6),
        # No losing trades yields an undefined/infinite profit factor, not a misleading 0 or 999.
        'profit_factor': round_or_none(gross_profit / gross_loss if gross_loss > 0 else None),
        'expectancy_usd_per_trade': round_or_none(mean(pnls) if pnls else None),
        'average_win_usd': round_or_none(mean(wins) if wins else None),
        'average_loss_usd': round_or_none(mean(losses) if losses else None),
        'payoff_ratio': round_or_none(mean(wins)/abs(mean(losses)) if wins and losses else None),
        'median_trade_pnl_usd': round_or_none(median(pnls) if pnls else None),
        'best_trade_usd': round_or_none(max(pnls) if pnls else None),
        'worst_trade_usd': round_or_none(min(pnls) if pnls else None),
        'longest_losing_streak': max_streak,
        'closed_trade_net_pnl_usd': round(sum(pnls), 6),
        'closed_trade_gross_pnl_usd': round(sum(t['gross_pnl_usd'] for t in trades), 6),
        'closed_trade_fees_usd': round(sum(t['fees_usd'] for t in trades), 6),
        'average_holding_minutes': round_or_none(mean(t['holding_minutes'] for t in trades) if trades else None),
        'long_trades': sum(t['side']=='LONG' for t in trades),
        'short_trades': sum(t['side']=='SHORT' for t in trades),
    }
    if len(trades) < 30:
        warnings.append('Fewer than 30 closed trade records: trade statistics have high uncertainty.')
    if not losses:
        warnings.append('Profit factor undefined because there are no losing closed trades.')
    return metrics, trades


def analyze_equity(records: list[dict[str, Any]], timeframe: str,
                   risk_free_annual: float, warnings: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    if timeframe not in TIMEFRAME_SECONDS:
        raise ValueError(f'Unsupported timeframe: {timeframe}')
    if risk_free_annual <= -1 or not isfinite(risk_free_annual):
        raise ValueError('Annual risk-free rate must be finite and greater than -100%.')
    data = clean_equity(records, warnings)
    expected = TIMEFRAME_SECONDS[timeframe]
    annual_bars = SECONDS_PER_YEAR / expected
    per_period_rf = (1+risk_free_annual)**(1/annual_bars)-1
    returns, equity_rows = [], []
    peak = data[0]['equity_usd']
    max_dd = 0.0
    gaps = 0
    longest_underwater_seconds, underwater_start = 0.0, None
    previous = None
    for r in data:
        now = r['dt']
        equity = r['equity_usd']
        if previous is not None:
            delta = (now-previous['dt']).total_seconds()
            if delta == expected:
                returns.append(equity / previous['equity_usd']-1)
            else:
                gaps += 1
        if equity >= peak:
            peak = equity
            if underwater_start is not None:
                longest_underwater_seconds = max(longest_underwater_seconds, (now-underwater_start).total_seconds())
                underwater_start = None
        elif underwater_start is None:
            underwater_start = previous['dt'] if previous else now
        dd_pct = (equity / peak - 1) * 100
        max_dd = min(max_dd, dd_pct)
        equity_rows.append({
            'time_utc': r['time_utc'], 'equity_usd': round(equity, 8),
            'drawdown_pct': round(dd_pct, 8),
            'close_price': r['close_price'],
            'signed_contracts': r['signed_contracts'],
            'benchmark_equity_usd': None,
        })
        previous = r
    if underwater_start is not None:
        longest_underwater_seconds = max(longest_underwater_seconds, (data[-1]['dt']-underwater_start).total_seconds())
    excess = [x-per_period_rf for x in returns]
    sharpe = None
    if len(excess) >= 2:
        volatility = stdev(excess)
        if volatility > 1e-12:
            sharpe = mean(excess)/volatility*sqrt(annual_bars)
    downside = sqrt(mean([min(0, x)**2 for x in excess])) if excess else 0
    sortino = mean(excess)/downside*sqrt(annual_bars) if downside > 1e-12 else None
    if gaps:
        warnings.append(f'{gaps} irregular/missing equity intervals excluded from Sharpe and Sortino returns; total return and drawdown still use observed equity values.')
    if len(returns) < 30:
        warnings.append('Fewer than 30 contiguous return observations: annualized risk ratios are unstable.')
    if sharpe is None:
        warnings.append('Sharpe ratio unavailable (insufficient observations or zero return volatility).')
    if sortino is None:
        warnings.append('Sortino ratio unavailable (insufficient downside volatility).')
    start, end = data[0], data[-1]
    time_days = (end['dt']-start['dt']).total_seconds() / 86400
    total_return_pct = (end['equity_usd']/start['equity_usd']-1)*100
    cagr_pct = (end['equity_usd']/start['equity_usd'])**(365/time_days)*100-100 if time_days >= 30 else None
    if cagr_pct is None:
        warnings.append('CAGR/Calmar suppressed because less than 30 days of equity data are available.')
        warnings.append('Annualized Sharpe/Sortino values on a very short history can be extremely large and are not decision-grade.')
    # Simple zero-cost buy-and-hold benchmark, NOT a tradable Delta perpetual execution simulation.
    first_price = start['close_price']
    if first_price is not None:
        for r in equity_rows:
            if r['close_price'] is not None:
                r['benchmark_equity_usd'] = round(start['equity_usd']*r['close_price']/first_price, 8)
    else:
        warnings.append('No first close_price; buy-and-hold benchmark unavailable.')
    months = []
    previous_month_end = None
    for month in sorted(set(r['time_utc'][:7] for r in equity_rows)):
        month_rows = [r for r in equity_rows if r['time_utc'].startswith(month)]
        start_eq = previous_month_end if previous_month_end is not None else month_rows[0]['equity_usd']
        end_eq = month_rows[-1]['equity_usd']
        months.append({'month': month, 'return_pct': round((end_eq/start_eq-1)*100, 6), 'start_equity_usd':start_eq, 'end_equity_usd':end_eq})
        previous_month_end = end_eq
    metrics = {
        'timeframe': timeframe,
        'observations': len(data),
        'contiguous_return_observations': len(returns),
        'irregular_intervals': gaps,
        'start_utc': start['time_utc'], 'end_utc': end['time_utc'],
        'duration_days': round(time_days, 6),
        'starting_equity_usd': round(start['equity_usd'], 6),
        'ending_equity_usd': round(end['equity_usd'], 6),
        'total_return_pct': round_or_none(total_return_pct),
        'net_equity_change_usd': round_or_none(end['equity_usd']-start['equity_usd']),
        'cagr_pct': round_or_none(cagr_pct),
        'max_drawdown_pct': round_or_none(max_dd),  # Negative means decline from prior peak.
        'latest_drawdown_pct': round_or_none(equity_rows[-1]['drawdown_pct']),
        'longest_underwater_days': round(longest_underwater_seconds/86400, 6),
        'sharpe_ratio': round_or_none(sharpe),
        'sortino_ratio': round_or_none(sortino),
        'calmar_ratio': round_or_none(cagr_pct / abs(max_dd) if cagr_pct is not None and max_dd < 0 else None),
        'risk_free_annual_pct': round_or_none(risk_free_annual*100),
        'exposure_snapshot_pct': round_or_none(100*sum(r['signed_contracts']!=0 for r in data)/len(data)),
        'benchmark_return_pct': round_or_none((data[-1]['close_price']/first_price-1)*100 if first_price and data[-1]['close_price'] else None),
    }
    return metrics, equity_rows, months


def analyze(summary: dict[str, Any], equity: list[dict[str, Any]], trades: list[dict[str, Any]],
            timeframe: str, risk_free_annual: float = 0.0) -> dict[str, Any]:
    warnings: list[str] = []
    eq, enriched, monthly = analyze_equity(equity, timeframe, risk_free_annual, warnings)
    tr, valid_trades = analyze_trades(trades, warnings)
    source_start = summary.get('start_capital_usd')
    source_end = summary.get('ending_equity_usd')
    if source_start is not None:
        if abs(finite_float(source_start, 'start_capital_usd')-eq['starting_equity_usd']) > .01:
            warnings.append('Source starting capital differs from first observed equity snapshot.')
    if source_end is not None:
        if abs(finite_float(source_end, 'ending_equity_usd')-eq['ending_equity_usd']) > .01:
            warnings.append('Source ending equity differs from last observed equity snapshot.')
    # Closed-trade PnL need not match equity change: fees of open positions, unrealized PnL,
    # missing funding and other cash flows may differ. Do not pretend they reconcile.
    if abs(eq['net_equity_change_usd'] - tr['closed_trade_net_pnl_usd']) > 0.01:
        warnings.append('Closed-trade net PnL differs from equity change; check open positions, cash flows, and fee allocation.')
    assumptions = summary.get('assumptions', {})
    return {
        'metadata': {'project': 'Mini-Project 9', 'symbol': 'BTCUSD', 'timeframe': timeframe,
                     'data_kind': 'historical simulation; not live execution',
                     'source_assumptions': assumptions, 'analysis_risk_free_annual': risk_free_annual},
        'equity_metrics': eq,
        'trade_metrics': tr,
        'monthly_returns': monthly,
        'equity_series': enriched,
        'closed_trades': valid_trades,
        'warnings': list(dict.fromkeys(warnings)),
    }
