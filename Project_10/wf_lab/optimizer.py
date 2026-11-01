"""Chronological rolling walk-forward optimization with untouched test windows."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from itertools import product
from typing import Sequence
import math
import numpy as np
import pandas as pd
from .strategy import StrategyParams, target_positions
from .backtest import CostConfig, score, simulate_window

@dataclass(frozen=True)
class WalkForwardConfig:
    train_bars: int = 500
    validation_bars: int = 200
    test_bars: int = 200
    step_bars: int = 200
    min_trades: int = 1
    top_n: int = 3
    mode: str = "long_short"
    capital: float = 10000.0

    def check(self):
        if min(self.train_bars, self.validation_bars, self.test_bars, self.step_bars) <= 0:
            raise ValueError("Fold window sizes must all be positive")
        if self.min_trades < 0 or self.top_n < 1 or self.capital <= 0:
            raise ValueError("Invalid min_trades, top_n or capital")
        if self.step_bars < self.test_bars:
            raise ValueError("step_bars must be >= test_bars, to avoid test overlap")
        if self.step_bars != self.test_bars:
            raise ValueError("This teaching project requires step_bars == test_bars for continuous OOS reporting")


def fold_slices(length: int, cfg: WalkForwardConfig) -> list[dict]:
    cfg.check()
    folds = []
    width = cfg.train_bars + cfg.validation_bars + cfg.test_bars
    for start in range(0, length-width+1, cfg.step_bars):
        a = start
        b = a + cfg.train_bars
        c = b + cfg.validation_bars
        d = c + cfg.test_bars
        folds.append({"fold": len(folds)+1, "train": (a,b), "validation": (b,c), "test": (c,d)})
    if not folds:
        raise ValueError(f"Need at least {width} consecutive candles, only {length} supplied. Use smaller --train-bars/--validation-bars/--test-bars or more history.")
    return folds


def default_candidates() -> list[StrategyParams]:
    return [StrategyParams(fast, slow, thresh) for fast,slow,thresh in product([5,9], [21,34], [50,55])]


def run_walk_forward(df: pd.DataFrame, timeframe: str,
                     cfg: WalkForwardConfig | None = None,
                     cost: CostConfig | None = None,
                     candidates: Sequence[StrategyParams] | None = None) -> dict:
    cfg = cfg or WalkForwardConfig()
    cost = cost or CostConfig()
    candidates = list(candidates) if candidates is not None else default_candidates()
    if not candidates:
        raise ValueError("Candidate list cannot be empty")
    for p in candidates:
        p.validate()
    folds = fold_slices(len(df), cfg)
    # All features are causal: only earlier or current candle CLOSE enters indicators.
    # Even though cached over the entire series, values at i never depend on j > i.
    targets_cache = {p: target_positions(df, p, mode=cfg.mode) for p in candidates}
    results = []
    compounded = 1.0
    out_of_sample_curve = []
    for fs in folds:
        rankings = []
        for candidate in candidates:
            r = simulate_window(df, targets_cache[candidate], *fs["train"], cost, cfg.capital)
            rankings.append((score(r, cfg.min_trades),candidate,r))
        rankings.sort(key=lambda v: (v[0], -v[1].fast_ema, -v[1].slow_ema, -v[1].rsi_threshold),reverse=True)
        shortlist = [v for v in rankings if math.isfinite(v[0])][:cfg.top_n]
        validation_results = []
        for train_score, candidate, train_result in shortlist:
            v = simulate_window(df, targets_cache[candidate], *fs["validation"], cost, cfg.capital)
            validation_results.append((score(v,cfg.min_trades),candidate,train_result,v,train_score))
        validation_results.sort(key=lambda v: (v[0],v[4]),reverse=True)
        eligible = [v for v in validation_results if math.isfinite(v[0])]
        ranges = {
            name: {"start_utc": df.iloc[lo]["timestamp_utc"].isoformat(), "end_utc": df.iloc[hi-1]["timestamp_utc"].isoformat(), "bars": hi-lo}
            for name,(lo,hi) in ((n,fs[n]) for n in ("train","validation","test"))
        }
        if not eligible:
            results.append({"fold":fs["fold"],"status":"SKIPPED_INSUFFICIENT_TRADES","ranges":ranges,"train_candidates":len(candidates),"test_evaluated":False})
            continue
        _, chosen, train_report, validation_report,_ = eligible[0]
        # The test window is touched ONLY ONCE, after training + validation selection.
        test_report = simulate_window(df, targets_cache[chosen], *fs["test"], cost, cfg.capital, include_curve=True)
        compounded *= (1+test_report["net_return_pct"]/100)
        fold_entry = {
            "fold":fs["fold"],"status":"EVALUATED","ranges":ranges,
            "parameters":chosen.to_dict(),
            "train":train_report,"validation":validation_report,
            "test":{k:v for k,v in test_report.items() if k not in ("equity_curve","trade_pnl_usd")},
            "generalization_gap_pct_points":round(train_report["net_return_pct"]-test_report["net_return_pct"],6),
            "candidate_count":len(candidates),"test_evaluated":True,
            "shortlisted": [{"parameters":x[1].to_dict(),"train_score":round(x[4],6),"validation_score":round(x[0],6) if math.isfinite(x[0]) else None} for x in validation_results],
        }
        results.append(fold_entry)
        for point in test_report["equity_curve"]:
            # Start each test segment at the previous compounded OOS equity level.
            scale = compounded / (1+test_report["net_return_pct"]/100)
            out_of_sample_curve.append({"time_utc":point["time_utc"], "oos_equity_usd":round(cfg.capital*scale*point["equity_usd"]/cfg.capital,6), "fold":fs["fold"]})
    completed = [f for f in results if f["status"] == "EVALUATED"]
    combined_return_pct = (compounded-1)*100
    summary = {
        "folds_total":len(folds),"folds_evaluated":len(completed),"folds_skipped":len(folds)-len(completed),
        "oos_compounded_return_pct":round(combined_return_pct,6),
        "oos_positive_fold_pct":round(100*sum(f["test"]["net_return_pct"]>0 for f in completed)/len(completed),4) if completed else None,
        "average_test_return_pct":round(sum(f["test"]["net_return_pct"] for f in completed)/len(completed),6) if completed else None,
        "average_train_to_test_gap_pct_points":round(sum(f["generalization_gap_pct_points"] for f in completed)/len(completed),6) if completed else None,
    }
    return {
        "project":"Mini-Project 10 BTC Walk-Forward Optimizer",
        "symbol":"BTCUSD", "timeframe":timeframe,
        "data_source":"Historical JSON (origin supplied separately; demo is synthetic)",
        "config":asdict(cfg),"costs":asdict(cost),
        "candidate_grid":[c.to_dict() for c in candidates],
        "summary":summary,"folds":results,"oos_equity_curve":out_of_sample_curve,
        "notes":[
            "Indicators use past/current closed candles only; execution uses next candle OPEN.",
            "Each rolling fold tunes on TRAIN, chooses among the best candidates on VALIDATION, and runs TEST once.",
            "Every segment begins flat and exits by the final candle close. Simplified 1x BTC price-return simulation.",
            "Trading costs configurable; no funding, liquidity, liquidation, or exact Delta contract settlement.",
            "Do not use test results to repeatedly retune the strategy; that contaminates the holdout.",
        ],
    }
