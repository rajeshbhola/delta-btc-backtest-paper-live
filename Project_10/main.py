"""Command-line entrypoint: demo, optimize, summary."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from wf_lab.data import INTERVAL_SECONDS,load_candles
from wf_lab.backtest import CostConfig
from wf_lab.optimizer import WalkForwardConfig, run_walk_forward
from wf_lab.demo import make_demo


def parser():
    p=argparse.ArgumentParser(description="Mini-Project 10: BTC Walk-Forward Optimizer (offline)")
    sub=p.add_subparsers(dest="command",required=True)
    demo=sub.add_parser("demo",help="Generate synthetic OHLCV dataset")
    demo.add_argument("--output",default="demo_data")
    demo.add_argument("--bars",type=int,default=1500)
    opt=sub.add_parser("optimize",help="Run walk-forward study on saved JSON candles")
    opt.add_argument("--source",default="demo_data",help="Project 2 or 3 JSON data root")
    opt.add_argument("--output",default="results")
    opt.add_argument("--timeframes",nargs="+",choices=list(INTERVAL_SECONDS),default=["5m"])
    opt.add_argument("--max-candles",type=int,default=8000,help="Latest N candles. Set 0 for all historical candles (may be slow).")
    opt.add_argument("--train-bars",type=int,default=500)
    opt.add_argument("--validation-bars",type=int,default=200)
    opt.add_argument("--test-bars",type=int,default=200)
    opt.add_argument("--step-bars",type=int,default=200)
    opt.add_argument("--min-trades",type=int,default=1)
    opt.add_argument("--mode",choices=["long_only","long_short"],default="long_short")
    opt.add_argument("--capital",type=float,default=10000)
    opt.add_argument("--fee-bps",type=float,default=5)
    opt.add_argument("--gst-percent",type=float,default=18)
    opt.add_argument("--spread-bps",type=float,default=1)
    opt.add_argument("--slippage-bps",type=float,default=1)
    summary=sub.add_parser("summary",help="Print fold table from saved results")
    summary.add_argument("--output",default="results")
    summary.add_argument("--timeframe",choices=list(INTERVAL_SECONDS),default="5m")
    return p


def main(args=None):
    a=parser().parse_args(args)
    if a.command=="demo":
        make_demo(a.output,bars=a.bars)
        print(f"Wrote artificial BTCUSD example data to: {a.output}")
        return
    if a.command=="optimize":
        cfg=WalkForwardConfig(train_bars=a.train_bars,validation_bars=a.validation_bars,test_bars=a.test_bars,step_bars=a.step_bars,min_trades=a.min_trades,mode=a.mode,capital=a.capital)
        costs=CostConfig(a.fee_bps,a.gst_percent,a.spread_bps,a.slippage_bps)
        if a.max_candles < 0: raise ValueError("--max-candles must be >= 0")
        for timeframe in a.timeframes:
            candles=load_candles(a.source,timeframe,a.max_candles)
            result=run_walk_forward(candles,timeframe,cfg,costs)
            result["data_origin"] = "SYNTHETIC_DEMO" if (Path(a.source) / "SYNTHETIC_DEMO_NOTICE.json").exists() else "USER_PROVIDED_UNVERIFIED"
            target=Path(a.output)/"BTCUSD"/timeframe/"walk_forward.json"
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(json.dumps(result,indent=2,allow_nan=False),encoding="utf-8")
            s=result["summary"]
            print(f"[{timeframe}] {len(candles):,} candles, {s['folds_evaluated']}/{s['folds_total']} evaluated folds, compounded OOS return {s['oos_compounded_return_pct']:.3f}% → {target}")
        return
    path=Path(a.output)/"BTCUSD"/a.timeframe/"walk_forward.json"
    obj=json.loads(path.read_text(encoding="utf-8"))
    print(json.dumps(obj["summary"],indent=2))
    for f in obj["folds"]:
        print(f"Fold {f['fold']} | {f['status']}" + (f" | {f['parameters']} | train={f['train']['net_return_pct']:.3f}% validation={f['validation']['net_return_pct']:.3f}% TEST={f['test']['net_return_pct']:.3f}%" if f['status']=="EVALUATED" else ""))

if __name__=="__main__":
    main()
