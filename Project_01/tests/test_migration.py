from datetime import datetime, timezone

import pandas as pd

from migrate_parquet_to_json import migrate
from delta_collector.storage import CandleStore


def test_optional_converter_does_not_delete_parquet(tmp_path, monkeypatch):
    source = tmp_path / "old" / "BTCUSD" / "1m"
    source.mkdir(parents=True)
    (source / "2026-01.parquet").write_bytes(b"unchanged")
    frame = pd.DataFrame({
        "timestamp_utc": [datetime(2026, 1, 2, tzinfo=timezone.utc)],
        "open": [100.], "high": [110.], "low": [95.], "close": [105.], "volume": [2.]})
    monkeypatch.setattr(pd, "read_parquet", lambda path: frame)
    destination = tmp_path / "json"
    assert migrate(tmp_path / "old", destination, "BTCUSD", ("1m",)) == {"1m": 1}
    assert (source / "2026-01.parquet").read_bytes() == b"unchanged"
    assert len(CandleStore(destination).load("BTCUSD", "1m")) == 1
