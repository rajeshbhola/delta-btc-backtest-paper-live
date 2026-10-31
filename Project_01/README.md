# Project 1 — Delta Exchange India BTCUSD: REST + WebSocket + JSON + Dashboard

**Market data only · No API keys · No trading orders · Python 3.11+**

This is the updated Mini-Project 1. It backfills **365 days** of **completed** BTCUSD OHLCV candles using Delta India's **public REST** API, keeps them current using **public WebSocket notifications plus REST reconciliation**, persists candles as **monthly JSON files**, and visualizes everything in a **read-only Streamlit dashboard**.

## What's new in this version

- ✅ **JSON instead of Parquet** (no `pyarrow` needed for normal operation).
- ✅ Monthly `.json` files: easy to inspect, ingest, and use from other languages.
- ✅ Read-only Streamlit UI: candlestick & volume chart, EMA 9/21 overlays, coverage table, REST progress, WebSocket state and last provisional price, audit reports, JSON download.
- ✅ Atomic JSON writes, deduplication, restart/resume, REST pagination, gap auditing, optional CSV export.
- ✅ Optional **Parquet-to-JSON migration script** for people with older Project 1 data (requires `pyarrow` *only for conversion*).
- ✅ Automated offline tests.

## Architecture

```text
Delta India REST (historical OHLCV) -- pages <= 2,000 bars --> CandleService
           |                                                  |
           |                                                  v
           |                                             CandleStore
           |                                         monthly JSON (atomic)
           |                                                  |
           |                                                  v
Delta public WS (provisional prices) --> REST refresh ---> Streamlit Dashboard
                                     triggers       (separate read-only process)
```

No WebSocket provisional candle is considered complete or persisted as an authoritative candle. Each candle is confirmed with the REST API *after* the candle period has ended. The app does not attempt broker authentication.

## Data sources

| Data | Endpoint |
| --- | --- |
| REST completed candles | `GET https://api.india.delta.exchange/v2/history/candles` |
| Public WebSocket | `wss://public-socket.india.delta.exchange` |
| Candlestick subscriptions | `candlestick_1m`, `candlestick_5m`, `candlestick_15m`, `candlestick_1h`, `candlestick_4h` with symbol `BTCUSD` |

REST `time` is in seconds; WebSocket `ts` is event time in microseconds. Both are handled separately.

Official reference: https://docs.delta.exchange/

## 1. Install (Windows PowerShell)

From the **unzipped project root**:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

For macOS/Linux: `python3 -m venv .venv` then `.venv/bin/python -m pip install -r requirements.txt`.

## 2. Start with a tiny download

```powershell
.\.venv\Scripts\python.exe main.py backfill --days 1 --timeframes 5m
```

The downloaded JSON file appears under `data/candles/BTCUSD/5m/YYYY-MM.json`.

## 3. Backfill one year for all five intervals

```powershell
.\.venv\Scripts\python.exe main.py backfill --days 365
```

This downloads ~**676,710** expected candle slots if a complete 365-day history is available:

| Timeframe | Candle slots | Minimum REST pages |
| --- | ---: | ---: |
| 1m | 525,600 | 263 |
| 5m | 105,120 | 53 |
| 15m | 35,040 | 18 |
| 1h | 8,760 | 5 |
| 4h | 2,190 | 2 |
| **Total** | **676,710** | **341** |

The count is theoretical, **not a promise of availability**. The script paginates at <=2,000 candles/request, rate-limits requests, handles temporary errors, and saves each page immediately. Rerun the same command after an interruption to resume from the last saved candle, with overlap. **Older gaps are reported rather than repaired automatically**.

## 4. Open the Streamlit dashboard

Open **a separate terminal** in the same folder:

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard.py
```

Visit the URL printed by Streamlit, usually **http://localhost:8501**.

Dashboard tabs:

1. **Overview** — collector mode/state, WebSocket connection, provisional WS last price, months saved, counts, latest timestamps, timeframe progress.
2. **Candles** — BTCUSD candlestick chart + volume, EMA 9/21 overlay, timeframe selector, recent candle table and JSON export.
3. **Data quality** — report counts of missing candle timestamps and download complete JSON gap reports.
4. **Collector** — raw runtime status, example CLI commands.

The overview/chart automatically refresh about every 15 seconds. The **dashboard is read-only**: it does not start, stop, or send orders through the exchange. It displays JSON data produced by the CLI collector. To fetch data you must run the collector in another terminal.

## 5. Live WebSocket + REST reconciliation

**Finish the backfill before starting `live`**. In a separate terminal:

```powershell
.\.venv\Scripts\python.exe main.py live --poll-seconds 60
```

The collector subscribes to all five WebSocket candlestick channels and updates `data/status.json`. On detected interval boundaries, and at periodic intervals, it uses REST to capture finalized candles. Reconnects use exponential backoff. Stop with Ctrl+C. Close the live process before launching another backfill—**use only one writer per `data/candles` directory**.

## 6. Audit gaps

```powershell
.\.venv\Scripts\python.exe main.py audit --days 365
```

Find reports at `data/reports/BTCUSD_1m_missing.json`, etc. **No missing bars are made up, synthesized, or forward-filled.** The dashboard displays the last saved audit results; run the command to refresh them.

## 7. Optional CSV export

JSON is the primary storage format. If CSV is useful for Excel:

```powershell
.\.venv\Scripts\python.exe main.py export-csv
```

## 8. Convert older Parquet archives to JSON (optional)

**If you already downloaded a year using the prior Parquet version**:

1. Stop any running backfill/live process.
2. Rename your previous `data/candles` folder to `data/candles_parquet` (keep a copy/backup first).
3. Install Parquet support for this one-time task:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install pyarrow
   ```

4. Run the converter:

   ```powershell
   .\.venv\Scripts\python.exe migrate_parquet_to_json.py --source data/candles_parquet --dest data/candles
   ```

The converter **does not delete Parquet**. If you do not have older Parquet files, skip this step entirely.

## Storage layout

```text
data/
├── status.json                  # CLI collector / WS status for UI
├── candles/
│   └── BTCUSD/
│       ├── 1m/
│       │   ├── 2025-11.json
│       │   └── 2025-12.json
│       ├── 5m/
│       ├── 15m/
│       ├── 1h/
│       └── 4h/
├── reports/
│   ├── BTCUSD_1m_missing.json
│   ├── BTCUSD_5m_missing.json
│   └── ...
└── csv/                         # optional
```

Candle storage is a **JSON array per UTC month**, with one object per completed candle:

```json
[
  {
    "timestamp_utc": "2026-10-31T10:00:00Z",
    "open": 100000.0,
    "high": 100120.0,
    "low": 99920.0,
    "close": 100085.0,
    "volume": 1250.0
  }
]
```

**The numbers above are illustrative, not actual prices**. All times are ISO-8601 **UTC**. Convert to IST only for display, and never shift timestamps in stored files.

### Read the data from another project

```python
from delta_collector.storage import CandleStore

store = CandleStore("data/candles")
df = store.load("BTCUSD", "5m")
print(df.tail())
# Or read only the latest 500 completed candles:
print(store.tail("BTCUSD", "5m", n=500))
```

### Trade-offs of JSON versus Parquet

JSON is human-readable and convenient for APIs and the dashboard, but **takes more disk space** and is **slower to read** than Parquet, especially for 1-minute candles spanning a year. Monthly partitioning, recent-window loading, and dashboard caching keep this introductory project manageable. For heavy research later, a columnar analytical format may be worth reintroducing.

## Automated tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests cover JSON schemas, monthly atomic write/rewrite, deduplication, resume, missing candles, converter safety, status persistence, REST pagination, validation/rate limiting, WebSocket parsing and refresh triggers. Tests use simulated market/API data: **real year-long REST downloads and persistent public WebSocket connectivity require running the project on your own internet-connected machine**.

## Safety and operation

- Public read-only market data only; there is no `.env`, private account access, order API or trading code.
- Never run two writer processes for the same data directory. The dashboard reads safely while a writer atomically replaces JSON.
- Keep the terminal running while collecting live data; use external scheduling/supervision if running 24/7.
- Data may be incomplete; inspect `data/reports` before any backtesting.
- No guarantee of historical coverage or trading results.

## Optional: preview the dashboard without internet or a year-long download

```powershell
.\.venv\Scripts\python.exe make_demo_data.py
.\.venv\Scripts\python.exe -m streamlit run dashboard.py
```

In the dashboard sidebar, change **Candle data folder** from `data/candles` to `demo_data/candles`. The generator creates a **synthetic** price series for the charts, stored outside the actual data folder, and marks the collector as synthetic. **Never use this generated data for backtesting or trading.** Switch back to `data/candles` when real REST backfill starts.
