"""Tests: correctness, no leakage, split isolation, source format compatibility."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from wf_lab.data import load_candles
from wf_lab.strategy import StrategyParams,target_positions
from wf_lab.backtest import CostConfig,simulate_window
from wf_lab.optimizer import WalkForwardConfig, fold_slices,run_walk_forward,default_candidates
from wf_lab.demo import make_demo


def candles(n=1200):
    rng=np.random.default_rng(8)
    close=10000*np.exp(np.cumsum(rng.normal(0.0001,0.003,size=n)))
    openp=np.insert(close[:-1],0,10000)
    return pd.DataFrame({"timestamp_utc":pd.date_range("2026-01-01",periods=n,freq="5min",tz="UTC"),"open":openp,"high":np.maximum(openp,close)*1.001,"low":np.minimum(openp,close)*0.999,"close":close,"volume":50.0})


def test_default_grid_has_eight_unique_candidates():
    assert len(default_candidates())==8
    assert len(set(default_candidates()))==8

@pytest.mark.parametrize("fast,slow,threshold",[(9,9,50),(30,21,55),(1,21,55),(9,21,80)])
def test_invalid_parameters(fast,slow,threshold):
    with pytest.raises(ValueError): StrategyParams(fast,slow,threshold).validate()


def test_target_is_causal_when_future_prices_change():
    base=candles(450)
    params=StrategyParams(9,21,50)
    original=target_positions(base,params)
    modified=base.copy()
    modified.loc[300:,"close"]*=2.0
    observed=target_positions(modified,params)
    assert np.array_equal(original[:300],observed[:300])


def test_no_short_in_long_only_mode():
    signals=target_positions(candles(400),StrategyParams(5,21,55),mode="long_only")
    assert set(signals)<= {0,1}


def test_fold_splits_do_not_overlap():
    f=fold_slices(1500,WalkForwardConfig())
    assert len(f)==4
    for a in f:
        assert a["train"][1]==a["validation"][0]
        assert a["validation"][1]==a["test"][0]
    assert all(f[i]["test"][1] <= f[i+1]["test"][0] for i in range(len(f)-1))


def test_overlap_settings_rejected():
    with pytest.raises(ValueError): fold_slices(1200,WalkForwardConfig(step_bars=100))


def test_insufficient_candles_raise():
    with pytest.raises(ValueError):fold_slices(250,WalkForwardConfig())


def test_next_open_prevents_signal_close_fill():
    d=candles(8)
    d.loc[0,"close"] = 20000.0
    # This signal at candle 0 closes, execution only at candle 1 open,
    # not at candle 0's manipulated close price.
    targets=np.array([1,1,1,1,1,1,1,1])
    result=simulate_window(d,targets,0,8,CostConfig(0,0,0,0),10000)
    assert result["closed_trades"]==1
    assert result["net_return_pct"] < 100


def test_no_position_is_carried_across_splits():
    d=candles(50)
    t=np.ones(len(d),dtype=int)
    a=simulate_window(d,t,0,20,CostConfig(0,0,0,0))
    b=simulate_window(d,t,20,40,CostConfig(0,0,0,0))
    assert a["closed_trades"]==1 and b["closed_trades"]==1
    assert b["start_capital_usd"]==10000


def test_flat_signals_zero_return_even_when_prices_move():
    d=candles(50)
    r=simulate_window(d,np.zeros(len(d),dtype=int),0,len(d))
    assert r["net_return_pct"]==0
    assert r["closed_trades"]==0


def test_fees_decrease_return():
    d=candles(60)
    t=np.ones(len(d),dtype=int)
    free=simulate_window(d,t,0,len(d),CostConfig(0,0,0,0))["net_return_pct"]
    charged=simulate_window(d,t,0,len(d),CostConfig(5,18,1,1))["net_return_pct"]
    assert charged<free


def test_invalid_costs_rejected():
    with pytest.raises(ValueError): _=CostConfig(-1,18,1,1).per_side_fraction


def test_walk_forward_results_and_test_holds_out():
    d=candles(1500)
    r=run_walk_forward(d,"5m",WalkForwardConfig(min_trades=0),CostConfig(),candidates=[StrategyParams(5,21,50),StrategyParams(9,34,55)])
    assert r["summary"]["folds_total"]==4
    for f in r["folds"]:
        assert f["status"]=="EVALUATED"
        assert f["ranges"]["validation"]["end_utc"]<f["ranges"]["test"]["start_utc"]


def test_test_price_changes_do_not_change_first_fold_selection():
    d=candles(1100)
    cfg=WalkForwardConfig(min_trades=0)
    original=run_walk_forward(d,"5m",cfg,candidates=default_candidates())
    altered=d.copy()
    altered.loc[700:899,["open","high","low","close"]] *= 1.8
    changed=run_walk_forward(altered,"5m",cfg,candidates=default_candidates())
    assert original["folds"][0]["parameters"]==changed["folds"][0]["parameters"]


def test_demo_imports_same_layout_as_project2(tmp_path):
    make_demo(tmp_path,1400)
    d=load_candles(tmp_path,"5m")
    assert len(d)==1400
    assert len(list((tmp_path/"clean"/"BTCUSD"/"5m").glob("*.json")))>=1


def test_missing_intervals_are_rejected(tmp_path):
    make_demo(tmp_path,100)
    path=next((tmp_path/"clean"/"BTCUSD"/"5m").glob("*.json"))
    data=json.loads(path.read_text())
    data.pop(20)
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match="missing/irregular"):
        load_candles(tmp_path,"5m")


def test_duplicate_candles_are_rejected(tmp_path):
    make_demo(tmp_path,100)
    path=next((tmp_path/"clean"/"BTCUSD"/"5m").glob("*.json"))
    data=json.loads(path.read_text())
    data.append(data[-1])
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match="Duplicate"):
        load_candles(tmp_path,"5m")


def test_summary_json_serializes_without_nan():
    d=candles(1200)
    r=run_walk_forward(d,"5m",WalkForwardConfig(min_trades=10000))
    assert r["summary"]["folds_skipped"]==2
    json.dumps(r,allow_nan=False)
