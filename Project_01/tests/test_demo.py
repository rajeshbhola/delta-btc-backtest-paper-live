from make_demo_data import build_demo
from delta_collector.storage import CandleStore
from delta_collector.status import read_status


def test_synthetic_preview_separated_from_real_data(tmp_path):
    root = build_demo(tmp_path / "demo_data", periods=12)
    assert not (tmp_path / "data").exists()
    assert len(CandleStore(root / "candles").load("BTCUSD", "4h")) == 12
    assert "SYNTHETIC DEMO" in read_status(root / "status.json")["mode"]
