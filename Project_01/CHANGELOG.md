# Project 1 — Changes in the JSON + Dashboard edition

- Changed primary monthly storage from Parquet to **JSON arrays**; `pyarrow` is no longer required for normal operation.
- Added atomic JSON writes, saved UTC ISO-8601 timestamps, numeric OHLCV validation, resumable deduplicated partitioning.
- Changed gap reports to `.json` with summary and missing UTC timestamp array.
- Added read-only dark-mode Streamlit UI: overview, candlestick and volume chart, optional EMA 9/21, timeframe selection, status and gap reports, JSON export.
- Added `data/status.json` snapshot updates for historical REST fetch progress and live WebSocket connection/price monitoring.
- Added `migrate_parquet_to_json.py` to preserve and convert existing Parquet data (optional, never deletes source).
- Retained 365-day historical REST backfill, 1m/5m/15m/1h/4h public WS subscriptions, periodic REST closed-candle reconciliation, timeout/429 backoff, restart/resume and CSV export.
- Added offline regression tests (JSON storage, resume, audits, status, migration, REST and WS).
- Added `make_demo_data.py` for a clearly labelled offline UI preview (synthetic data are never mixed with real market data).
