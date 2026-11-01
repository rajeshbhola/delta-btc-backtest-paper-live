import json
from pathlib import Path
import pytest
from cost_lab.demo import make_demo_trades
from cost_lab.model import Costs
from cost_lab.portfolio import load_trades, run_portfolio
from cost_lab.files import save_json
from main import main


def test_demo_portfolio_reconciles():
    p = run_portfolio(make_demo_trades())
    s = p["summary"]
    assert len(p["trades"]) == 14
    assert s["gross_pnl_usd"] - s["total_costs_usd"] == pytest.approx(s["net_pnl_usd"])
    assert 0 <= s["net_winning_trades"] <= s["trade_count"]
    assert s["max_net_drawdown_pct"] <= 0


def test_one_x_sizing_changes_with_equity():
    p = run_portfolio(make_demo_trades(), sizing="one_x")
    assert p["trades"][0]["contracts"] == 100


def test_no_funding_events_flag():
    p = run_portfolio(make_demo_trades(), estimate_funding=False)
    assert all(r["funding_events_assumed"] == 0 for r in p["trades"])


def test_load_project6_layout(tmp_path):
    file = tmp_path / "trades" / "BTCUSD_5m.json"
    save_json(file, make_demo_trades())
    rows = load_trades(tmp_path, timeframe="5m")
    assert len(rows) == 14


def test_load_rejects_bad_file(tmp_path):
    file = tmp_path / "bad.json"
    save_json(file, [{"side": "LONG"}])
    with pytest.raises(ValueError):
        load_trades(file)


def test_cli_single_writes_json(tmp_path, capsys):
    out = tmp_path / "single.json"
    main(["single", "--entry", "100000", "--exit", "101000", "--output", str(out)])
    assert json.loads(out.read_text())["net_pnl_usd"] < 10
    assert "Net PnL" in capsys.readouterr().out


def test_cli_batch_writes_json(tmp_path):
    src = save_json(tmp_path / "trades.json", make_demo_trades())
    out = tmp_path / "result.json"
    main(["batch", "--trades", str(src), "--output", str(out)])
    assert json.loads(out.read_text())["summary"]["trade_count"] == 14


def test_cli_demo(tmp_path):
    out = tmp_path / "demo"
    main(["demo", "--output", str(out)])
    assert (out / "trades.json").exists()
    assert (out / "batch_results.json").exists()
