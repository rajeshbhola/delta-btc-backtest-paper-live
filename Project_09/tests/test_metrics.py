from datetime import datetime, timedelta, timezone
from math import isclose
import json
import pytest
from performance_lab.metrics import analyze, analyze_trades, analyze_equity, clean_equity, parse_utc


def equity(values, tfmin=5, t0='2026-10-01T00:00:00Z', positions=None):
    t=datetime.fromisoformat(t0.replace('Z','+00:00'))
    return [{'time_utc':(t+timedelta(minutes=tfmin*i)).isoformat().replace('+00:00','Z'),
             'equity_usd':v,'close_price':100+i,'signed_contracts':positions[i] if positions else 0}
            for i,v in enumerate(values)]


def trade(pnl, i=0, side='LONG'):
    return {'entry_utc':f'2026-10-01T{i:02d}:00:00Z',
            'exit_utc':f'2026-10-01T{i:02d}:30:00Z',
            'net_pnl_usd':pnl, 'gross_pnl_usd':pnl+1,
            'entry_fee_usd':.5,'exit_fee_usd':.5,'side':side,'contracts':1}


def test_total_return():
    r=analyze({},equity([100,110]),[], '5m')
    assert r['equity_metrics']['total_return_pct']==10
    assert r['equity_metrics']['net_equity_change_usd']==10


def test_drawdown_from_peak():
    r=analyze({},equity([100,120,90,95]),[],'5m')
    assert r['equity_metrics']['max_drawdown_pct']==-25
    assert r['equity_metrics']['latest_drawdown_pct']==round((95/120-1)*100,6)


def test_annualized_metrics_finite_for_volatile_returns():
    r=analyze({},equity([100,110,101,111,99,101],tfmin=1),[],'1m')
    assert isinstance(r['equity_metrics']['sharpe_ratio'],float)
    assert isinstance(r['equity_metrics']['sortino_ratio'],float)


def test_constant_equity_ratio_unavailable():
    r=analyze({},equity([100]*5),[],'5m')
    assert r['equity_metrics']['sharpe_ratio'] is None
    assert r['equity_metrics']['sortino_ratio'] is None


def test_no_losses_profit_factor_is_none():
    m,_=analyze_trades([trade(2),trade(3,1)],[])
    assert m['profit_factor'] is None
    assert m['win_rate_pct']==100


def test_only_losses_profit_factor_zero():
    m,_=analyze_trades([trade(-2),trade(-3,1)],[])
    assert m['profit_factor']==0
    assert m['win_rate_pct']==0


def test_profit_factor_win_rate_expectancy():
    m,_=analyze_trades([trade(10),trade(-4,1),trade(0,2)],[])
    assert m['profit_factor']==2.5
    assert m['win_rate_pct']==round(100/3,6)
    assert m['expectancy_usd_per_trade']==2
    assert m['breakeven_trades']==1


def test_trade_costs_and_hold_time():
    m,_=analyze_trades([trade(2),trade(-1,1)],[])
    assert m['closed_trade_fees_usd']==2
    assert m['average_holding_minutes']==30
    assert m['closed_trade_gross_pnl_usd']==3


def test_losing_streak():
    m,_=analyze_trades([trade(4),trade(-1,1),trade(-2,2),trade(-3,3),trade(1,4)],[])
    assert m['longest_losing_streak']==3


def test_empty_trades_safe():
    m,rows=analyze_trades([],[])
    assert rows==[] and m['win_rate_pct'] is None and m['profit_factor'] is None


def test_gaps_excluded_from_ratios():
    d=equity([100,101,99,100])
    d[2]['time_utc']='2026-10-01T00:20:00Z'
    d[3]['time_utc']='2026-10-01T00:25:00Z'
    r=analyze({},d,[],'5m')
    assert r['equity_metrics']['irregular_intervals']==1
    assert r['equity_metrics']['contiguous_return_observations']==2
    assert r['equity_metrics']['total_return_pct']==0


def test_duplicate_timestamp_keeps_first():
    warnings=[]
    d=equity([100,105,110])
    d.append(dict(d[1],equity_usd=900))
    cleaned=clean_equity(d,warnings)
    assert len(cleaned)==3
    assert cleaned[1]['equity_usd']==105
    assert any('Duplicate' in s for s in warnings)


def test_sorts_out_of_order():
    d=equity([100,110,120])
    result=analyze({},[d[1],d[0],d[2]],[],'5m')
    assert result['equity_metrics']['total_return_pct']==20
    assert any('out of order' in x for x in result['warnings'])


def test_invalid_equity_filtered():
    d=equity([100,110,120])
    d.insert(1,{'time_utc':'2026-10-01T00:02:00Z','equity_usd':'NaN'})
    result=analyze({},d,[],'5m')
    assert result['equity_metrics']['observations']==3
    assert any('skipped' in s for s in result['warnings'])


def test_timestamp_requires_timezone():
    with pytest.raises(ValueError):
        parse_utc('2026-10-01T00:00:00')


def test_negative_equity_rejected():
    with pytest.raises(ValueError):
        analyze({},equity([100,-1]),[],'5m')


def test_unsupported_timeframe_rejected():
    with pytest.raises(ValueError):
        analyze({},equity([100,110]),[],'2h')


def test_bad_risk_free_rejected():
    with pytest.raises(ValueError):
        analyze({},equity([100,110]),[],'5m',-1)


def test_cagr_suppressed_for_short_history():
    r=analyze({},equity([100,110]),[],'5m')
    assert r['equity_metrics']['cagr_pct'] is None
    assert r['equity_metrics']['calmar_ratio'] is None


def test_cagr_available_30_days():
    e=equity([100,105],tfmin=30*24*60)
    r=analyze({},e,[],'5m')
    assert r['equity_metrics']['cagr_pct'] is not None
    assert r['equity_metrics']['calmar_ratio'] is None


def test_month_boundary_equity():
    e=equity([100,110,121],t0='2026-10-31T23:50:00Z')
    r=analyze({},e,[],'5m')
    assert [m['month'] for m in r['monthly_returns']]==['2026-10','2026-11']
    assert r['monthly_returns'][0]['return_pct']==10
    assert r['monthly_returns'][1]['return_pct']==10


def test_benchmark_zero_cost():
    r=analyze({},equity([100,103,95]),[],'5m')
    assert r['equity_series'][0]['benchmark_equity_usd']==100
    assert r['equity_series'][-1]['benchmark_equity_usd']==102


def test_exposure_fraction():
    r=analyze({},equity([100,101,102,103],positions=[0,1,1,0]),[],'5m')
    assert r['equity_metrics']['exposure_snapshot_pct']==50


def test_open_position_pnl_warning():
    r=analyze({},equity([100,109]),[trade(2)],'5m')
    assert any('Closed-trade net PnL differs' in x for x in r['warnings'])


def test_invalid_trade_does_not_crash():
    w=[]
    m,valid=analyze_trades([trade(1),{'net_pnl_usd':float('nan')}],w)
    assert len(valid)==1
    assert any('skipped' in x for x in w)


def test_actual_project8_schema_integration():
    from performance_lab.files import process_one
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    demo=root/'demo_project8'
    out=root/'tests'/'_temp_results'
    try:
        result=process_one(demo,out,'5m')
        assert result['trade_metrics']['closed_trades']==9
        assert isclose(result['equity_metrics']['max_drawdown_pct'], -0.124715, abs_tol=.00001)
        assert result['equity_metrics']['irregular_intervals']==1
        assert (out/'BTCUSD/5m/metrics.json').exists()
    finally:
        import shutil
        shutil.rmtree(out,ignore_errors=True)


def test_all_timeframes_integrate():
    from pathlib import Path
    from performance_lab.files import resolve_source, read_json
    root=Path(__file__).resolve().parents[1]/'demo_project8'
    for timeframe in ('1m','5m','15m','1h','4h'):
        d=resolve_source(root,timeframe)
        assert len(read_json(d/'equity.json'))>0
        assert isinstance(read_json(d/'trades.json'),list)


def test_missing_path_fails():
    from performance_lab.files import resolve_source
    with pytest.raises(FileNotFoundError):
        resolve_source('/nonexistent/doesnt-exist','5m')
