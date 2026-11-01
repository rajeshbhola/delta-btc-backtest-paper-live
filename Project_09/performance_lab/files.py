"""Project 8 JSON input and Project 9 JSON reports."""
from __future__ import annotations
import json
from pathlib import Path
from .metrics import analyze, TIMEFRAME_SECONDS


def read_json(path: Path):
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix+'.tmp')
    with temp.open('w', encoding='utf-8') as f:
        json.dump(value, f, indent=2, allow_nan=False)
    temp.replace(path)


def resolve_source(root: str | Path, timeframe: str) -> Path:
    root = Path(root).expanduser()
    candidates = [root/'BTCUSD'/timeframe, root/timeframe, root]
    for folder in candidates:
        if all((folder/x).is_file() for x in ('equity.json', 'trades.json')):
            return folder
    raise FileNotFoundError(f'Expected equity.json and trades.json in {root}/BTCUSD/{timeframe} (or a direct timeframe directory)')


def process_one(root: str | Path, out: str | Path, timeframe: str,
                risk_free_annual: float = 0.0) -> dict:
    source = resolve_source(root, timeframe)
    summary = read_json(source/'summary.json') if (source/'summary.json').exists() else {}
    equity = read_json(source/'equity.json')
    trades = read_json(source/'trades.json')
    if not isinstance(equity, list) or not isinstance(trades, list) or not isinstance(summary, dict):
        raise ValueError('Malformed input JSON types; equity/trades must be arrays, summary must be an object')
    data = analyze(summary, equity, trades, timeframe, risk_free_annual)
    folder = Path(out)/'BTCUSD'/timeframe
    write_json(folder/'metrics.json', {
        'metadata': data['metadata'],
        'equity_metrics': data['equity_metrics'],
        'trade_metrics': data['trade_metrics'],
        'warnings': data['warnings'],
    })
    write_json(folder/'equity_analysis.json', data['equity_series'])
    write_json(folder/'closed_trades.json', data['closed_trades'])
    write_json(folder/'monthly_returns.json', data['monthly_returns'])
    return data


def report_dir(root: str | Path, timeframe: str) -> Path:
    return Path(root)/'BTCUSD'/timeframe


def load_report(root: str | Path, timeframe: str) -> dict:
    folder=report_dir(root,timeframe)
    metrics=read_json(folder/'metrics.json')
    metrics['equity_series']=read_json(folder/'equity_analysis.json')
    metrics['closed_trades']=read_json(folder/'closed_trades.json')
    metrics['monthly_returns']=read_json(folder/'monthly_returns.json')
    return metrics


def available_timeframes(root: str | Path) -> list[str]:
    return [tf for tf in TIMEFRAME_SECONDS if (report_dir(root,tf)/'metrics.json').exists()]
