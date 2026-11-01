import pytest
from cost_lab.model import Trade, Costs, calculate, funding_snapshots


def test_delta_taker_fees_and_gst():
    r = calculate(Trade(entry_price=100000, exit_price=100000, contracts=1000),
                  Costs(spread_bps=0, slippage_bps=0, funding_rate_pct=0))
    assert r["entry_fee_usd"] == pytest.approx(50)
    assert r["exit_fee_usd"] == pytest.approx(50)
    assert r["gst_usd"] == pytest.approx(18)
    assert r["net_pnl_usd"] == pytest.approx(-118)


def test_maker_fees_lower():
    t = Trade(entry_price=100000, exit_price=100000, contracts=1000,
              entry_order="maker", exit_order="maker")
    r = calculate(t, Costs(spread_bps=0, slippage_bps=0, funding_rate_pct=0))
    assert r["commission_usd"] == pytest.approx(40)
    assert r["gst_usd"] == pytest.approx(7.2)


@pytest.mark.parametrize("side,entry,exit,expected", [("LONG", 100000, 101000, 10),
                                                         ("SHORT", 101000, 100000, 10),
                                                         ("SHORT", 100000, 101000, -10)])
def test_gross_direction(side, entry, exit, expected):
    r = calculate(Trade(side=side, entry_price=entry, exit_price=exit, contracts=10), Costs())
    assert r["gross_reference_pnl_usd"] == pytest.approx(expected)


def test_spread_and_slippage_separate_not_double_counted():
    r = calculate(Trade(entry_price=100000, exit_price=100000, contracts=10),
                  Costs(spread_bps=4, slippage_bps=2, maker_fee_bps=0,
                        taker_fee_bps=0, gst_pct=0, funding_rate_pct=0))
    assert r["spread_cost_usd"] == pytest.approx(0.4)
    assert r["slippage_cost_usd"] == pytest.approx(0.4)
    assert r["net_pnl_usd"] == pytest.approx(-0.8)
    assert r["total_costs_usd"] == pytest.approx(0.8)


def test_short_spread_slippage_adverse():
    r = calculate(Trade(side="SHORT", entry_price=100000, exit_price=100000, contracts=10),
                  Costs(spread_bps=4, slippage_bps=2, maker_fee_bps=0,
                        taker_fee_bps=0, gst_pct=0, funding_rate_pct=0))
    assert r["net_pnl_usd"] == pytest.approx(-0.8)


def test_funding_long_pays_short_receives():
    c = Costs(spread_bps=0, slippage_bps=0, maker_fee_bps=0, taker_fee_bps=0, gst_pct=0,
              funding_rate_pct=0.01)
    lg = calculate(Trade(entry_price=100000, exit_price=100000, contracts=100, funding_events=2), c)
    sh = calculate(Trade(side="SHORT", entry_price=100000, exit_price=100000, contracts=100, funding_events=2), c)
    assert lg["funding_paid_usd"] == pytest.approx(2)
    assert sh["funding_paid_usd"] == pytest.approx(-2)
    assert sh["net_pnl_usd"] == pytest.approx(2)


def test_negative_funding_flips_payment():
    r = calculate(Trade(entry_price=100000, exit_price=100000, contracts=10, funding_events=1),
                  Costs(spread_bps=0, slippage_bps=0, maker_fee_bps=0, taker_fee_bps=0,
                        funding_rate_pct=-0.01))
    assert r["funding_paid_usd"] == pytest.approx(-0.1)


def test_leverage_changes_margin_not_profit():
    t = Trade()
    a = calculate(t, Costs(leverage=2))
    b = calculate(t, Costs(leverage=5))
    assert a["net_pnl_usd"] == b["net_pnl_usd"]
    assert a["estimated_initial_margin_usd"] > b["estimated_initial_margin_usd"]


def test_funding_snapshots_boundaries_strict():
    assert funding_snapshots("2026-10-01T07:00:00Z", "2026-10-01T09:00:00Z") == 1
    assert funding_snapshots("2026-10-01T08:00:00Z", "2026-10-01T16:00:00Z") == 0
    assert funding_snapshots("2026-10-01T07:30:00+00:00", "2026-10-02T09:30:00+00:00") == 4
    with pytest.raises(ValueError):
        funding_snapshots("2026-10-01T00:00:00", "2026-10-02T00:00:00Z")


@pytest.mark.parametrize("field,value", [("contracts", 0), ("contracts", 1.2),
                                         ("entry_price", -1), ("side", "BUY"),
                                         ("entry_order", "limit"), ("funding_events", -1)])
def test_invalid_trade(field, value):
    from dataclasses import replace
    with pytest.raises(ValueError):
        replace(Trade(), **{field: value})


def test_fee_gst_on_commission_only():
    r = calculate(Trade(), Costs())
    assert r["gst_usd"] == pytest.approx(r["commission_usd"] * 0.18)


def test_accounting_reconciles():
    for side in ("LONG", "SHORT"):
        r = calculate(Trade(side=side, contracts=99, funding_events=3), Costs(funding_rate_pct=-0.015))
        assert r["gross_reference_pnl_usd"] - r["total_costs_usd"] == pytest.approx(r["net_pnl_usd"])
