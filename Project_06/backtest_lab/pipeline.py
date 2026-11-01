"""Run one or more timeframe backtests and save JSON output."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import tempfile
import pandas as pd
from .config import TIMEFRAMES
from .data import load_json_months, prepare
from .engine import BacktestConfig, run_backtest


def _atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=".", suffix=".tmp", delete=False) as tmp:
        temp_name = tmp.name
        json.dump(value, tmp, allow_nan=False, indent=2)
    os.replace(temp_name, path)


def _records(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", date_format="iso", date_unit="ms"))


def run_project(candles_root: str | Path, signals_root: str | Path, output: str | Path,
                *, timeframes: list[str] | None = None, starting_capital: float = 10000,
                mode: str = "long_only", fee_bps: float = 0.0, days: int | None = None,
                as_of: datetime | None = None) -> list[dict]:
    output = Path(output).expanduser().resolve()
    candles_root = Path(candles_root).expanduser().resolve()
    signals_root = Path(signals_root).expanduser().resolve()
    for root in (candles_root, signals_root):
        if output == root or output.is_relative_to(root) or root.is_relative_to(output):
            raise ValueError("Output must not overlap source directories")
    selected = timeframes if timeframes is not None else ["5m"]
    if not selected or any(tf not in TIMEFRAMES for tf in selected):
        raise ValueError("Unsupported or empty timeframes")
    results = []
    for tf in selected:
        candles = load_json_months(candles_root, "candles", tf)
        signals = load_json_months(signals_root, "signals", tf)
        prepared, info = prepare(candles, signals, tf, days=days, as_of=as_of)
        curve, trades, report = run_backtest(prepared, BacktestConfig(starting_capital, mode, fee_bps))
        report.update({"timeframe": tf, "data_info": info,
                       "data_origin": "SYNTHETIC_DEMO" if (candles_root / "SYNTHETIC_DATA_NOTICE.txt").exists() else "EXTERNAL_USER_DATA_UNVERIFIED",
                       "candles_root": str(candles_root), "signals_root": str(signals_root),
                       "generated_at_utc": datetime.now(timezone.utc).isoformat()})
        _atomic_json(output / "equity" / f"BTCUSD_{tf}.json", _records(curve))
        _atomic_json(output / "trades" / f"BTCUSD_{tf}.json", _records(trades))
        _atomic_json(output / "reports" / f"BTCUSD_{tf}.json", report)
        print(f"{tf}: {info['rows']:,} candles | {report['trade_count']} trades | net return {report['net_return_pct']:+.2f}% | drawdown {report['max_drawdown_pct']:.2f}%")
        results.append(report)
    return results


def read_saved(output: str | Path, tf: str):
    root = Path(output).expanduser().resolve()
    def read(folder):
        file = root / folder / f"BTCUSD_{tf}.json"
        return json.loads(file.read_text(encoding="utf-8"))
    return read("reports"), pd.DataFrame(read("equity")), pd.DataFrame(read("trades"))
