import json
from datetime import datetime, timedelta, timezone
import pytest
from event_lab.engine import Settings, execute
from event_lab.data import load_candles, load_signals, dump_json, iso


def fixture_data(prices, tf="5m", buys=(), sells=(), gap_after=None):
    base = datetime(2026, 10, 1, tzinfo=timezone.utc)
    bars, signals = [], {}
    secs = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400}[tf]
    for i, price in enumerate(prices):
        index = i+(1 if gap_after is not None and i > gap_after else 0)
        t = iso(base+timedelta(seconds=index*secs))
        bars.append({"timestamp_utc": t, "open": price, "high": price+5, "low": price-5, "close": price, "volume": 10})
        signals[t] = {"signal": "BUY" if i in buys else "SELL" if i in sells else "HOLD"}
    return bars, signals


def no_cost(**extra):
    return Settings(capital_usd=10000, contracts_per_order=5, max_fill_contracts=5,
                    fee_bps=0, gst_pct=0, spread_bps=0, slippage_bps=0, **extra)


def test_signal_on_last_bar_never_fills():
    bars, signals = fixture_data([100, 110], buys=[1])
    result=execute(bars,signals,no_cost())
    assert result['summary']['fill_count'] == 0
    assert result['summary']['pending_order_count'] == 1


def test_no_same_bar_fill_then_mark_to_market():
    bars, signals = fixture_data([100, 110, 120], buys=[0])
    result=execute(bars,signals,no_cost())
    assert result['fills'][0]['time_utc'] == bars[1]['timestamp_utc']
    assert result['fills'][0]['fill_price'] == 110
    assert result['summary']['open_signed_contracts'] == 5
    assert result['summary']['ending_equity_usd'] == pytest.approx(10000+5*.001*10)


def test_close_long_records_pnl_and_fees():
    bars, signals=fixture_data([100,110,130,140,145],buys=[0],sells=[2])
    r=execute(bars,signals,no_cost())
    assert r['trades'][0]['side'] == 'LONG'
    assert r['trades'][0]['net_pnl_usd'] == pytest.approx((140-110)*.005)
    assert r['summary']['open_signed_contracts'] == 0
    assert r['summary']['ending_equity_usd'] == pytest.approx(10000+.15)


def test_short_profit_falling_prices():
    bars,signals=fixture_data([150,140,120,100,95],sells=[0],buys=[2])
    r=execute(bars,signals,no_cost())
    assert r['fills'][0]['action'] == 'OPEN_SHORT'
    assert r['trades'][0]['side'] == 'SHORT'
    assert r['trades'][0]['gross_pnl_usd'] == pytest.approx(.2)


def test_long_only_sell_does_not_open_short():
    bars,signals=fixture_data([100,105,110],sells=[0])
    r=execute(bars,signals,Settings(mode='long_only'))
    assert r['summary']['order_count'] == 0


def test_fee_reduces_equity_once():
    bars,signals=fixture_data([100,110,120,130],buys=[0],sells=[1])
    cfg=Settings(fee_bps=5, gst_pct=18, spread_bps=0, slippage_bps=0)
    r=execute(bars,signals,cfg)
    fee1=110*.005*.0005*1.18
    fee2=120*.005*.0005*1.18
    assert r['summary']['total_fees_incl_gst_usd'] == pytest.approx(fee1+fee2)
    assert r['summary']['ending_equity_usd'] == pytest.approx(10000+.005*10-fee1-fee2)
    assert r['trades'][0]['net_pnl_usd'] == pytest.approx(.05-fee1-fee2)


def test_half_spread_plus_slippage_harms_long_and_short():
    bars,signals=fixture_data([100,100,100,100],buys=[0],sells=[1])
    cfg=Settings(fee_bps=0,gst_pct=0,spread_bps=2,slippage_bps=1)
    r=execute(bars,signals,cfg)
    assert r['fills'][0]['fill_price'] > 100
    assert r['fills'][1]['fill_price'] < 100
    assert r['trades'][0]['net_pnl_usd'] < 0


def test_partial_fills_across_bars():
    bars,signals=fixture_data([100]*6,buys=[0])
    cfg=Settings(fee_bps=0,gst_pct=0,spread_bps=0,slippage_bps=0,
                 contracts_per_order=5,max_fill_contracts=2)
    r=execute(bars,signals,cfg)
    assert [f['contracts'] for f in r['fills']] == [2,2,1]
    assert r['orders'][0]['status'] == 'FILLED'
    assert r['summary']['open_signed_contracts'] == 5


def test_gaps_cancel_pending_order_not_fill():
    bars,signals=fixture_data([100,110,120],buys=[0],gap_after=0)
    r=execute(bars,signals,no_cost())
    assert r['summary']['fill_count'] == 0
    assert r['orders'][0]['status'] == 'CANCELLED_GAP'
    assert r['summary']['gap_count'] == 1


def test_gap_does_not_flatten_existing_position():
    bars,signals=fixture_data([100,110,120,130],buys=[0],gap_after=1)
    r=execute(bars,signals,no_cost())
    assert r['summary']['gap_count'] == 1
    assert r['summary']['open_signed_contracts'] == 5


def test_leverage_guard_rejects_entry():
    bars,signals=fixture_data([100000,100000,100000],buys=[0])
    cfg=Settings(capital_usd=100,contracts_per_order=1000,max_fill_contracts=1000,
                 fee_bps=0, gst_pct=0,spread_bps=0,slippage_bps=0,max_leverage=1)
    r=execute(bars,signals,cfg)
    assert r['orders'][0]['status']=='REJECTED_RISK'
    assert r['summary']['open_signed_contracts']==0


def test_drawdown_negative_after_loss():
    bars,signals=fixture_data([100,110,90,80],buys=[0])
    r=execute(bars,signals,no_cost())
    assert r['summary']['max_drawdown_pct'] < 0


def test_invalid_configuration():
    with pytest.raises(ValueError):
        Settings(contracts_per_order=0).validate()
    with pytest.raises(ValueError):
        Settings(fee_bps=-1).validate()
    with pytest.raises(ValueError):
        Settings(mode='wrong').validate()


def test_load_monthly_project_4_schema(tmp_path):
    bars,signals = fixture_data([100,110,120],buys=[0])
    dump_json(tmp_path/'indicators'/'BTCUSD'/'5m'/'2026-10.json',bars)
    interval=timedelta(minutes=5)
    rows=[{'timestamp_utc':r['timestamp_utc'],
           'decision_time_utc':iso(datetime.fromisoformat(r['timestamp_utc'].replace('Z','+00:00'))+interval),
           'signal':signals[r['timestamp_utc']]['signal'] } for r in bars]
    dump_json(tmp_path/'signals'/'BTCUSD'/'5m'/'2026-10.json',rows)
    candles=load_candles(tmp_path,'5m')
    loaded=load_signals(tmp_path,'5m',candles)
    assert len(candles)==3
    assert sum(v['signal']=='BUY' for v in loaded.values())==1


def test_reject_incorrect_decision_time(tmp_path):
    bars,_=fixture_data([100])
    dump_json(tmp_path/'signals'/'BTCUSD'/'5m'/'2026-10.json',[
        {'timestamp_utc':bars[0]['timestamp_utc'], 'decision_time_utc':bars[0]['timestamp_utc'], 'signal':'BUY'}])
    with pytest.raises(ValueError,match='decision timestamp'):
        load_signals(tmp_path,'5m',bars)


def test_reject_duplicate_candles(tmp_path):
    bars,_=fixture_data([100,110])
    dump_json(tmp_path/'candles'/'BTCUSD'/'5m'/'2026-10.json',bars+bars[:1])
    with pytest.raises(ValueError,match='Duplicate'):
        load_candles(tmp_path,'5m')


def test_reject_invalid_candle(tmp_path):
    bars,_=fixture_data([100])
    bars[0]['high']=80
    dump_json(tmp_path/'candles'/'BTCUSD'/'5m'/'2026-10.json',bars)
    with pytest.raises(ValueError,match='Invalid OHLCV'):
        load_candles(tmp_path,'5m')


def test_json_write_atomic_roundtrip(tmp_path):
    target=tmp_path/'summary.json'
    dump_json(target,[{'a':1}])
    assert json.loads(target.read_text())==[{'a':1}]
    assert not (tmp_path/'summary.json.tmp').exists()


def test_signal_with_gap_before_skipped():
    bars,signals=fixture_data([100,110,120],buys=[0])
    signals[bars[0]['timestamp_utc']]['gap_before']=True
    r=execute(bars,signals,no_cost())
    assert r['summary']['order_count']==0


def test_open_position_is_not_forced_closed_at_end():
    bars,signals=fixture_data([100,110],buys=[0])
    r=execute(bars,signals,no_cost())
    assert len(r['trades']) == 0
    assert r['summary']['open_signed_contracts'] == 5


def test_events_have_correct_order():
    bars,signals=fixture_data([100,110],buys=[0])
    r=execute(bars,signals,no_cost())
    kinds=[x['type'] for x in r['events']]
    assert kinds.index('MARKET_CLOSE') < kinds.index('SIGNAL') < kinds.index('ORDER') < kinds.index('FILL')


def test_returns_after_realized_loss():
    bars,signals=fixture_data([100,100,70,60],buys=[0],sells=[1])
    r=execute(bars,signals,no_cost())
    assert r['summary']['return_pct'] < 0
    assert r['summary']['ending_equity_usd'] == pytest.approx(10000+5*.001*(70-100))
