# Project 2 — BTC Data Quality Lab (Standalone)

A **new and independent** Python mini-project for learning how to clean Bitcoin OHLCV candles and check whether your historical dataset is trustworthy enough for backtesting.

✅ BTCUSD perpetual futures · ✅ Delta Exchange India **public REST only** · ✅ 1m, 5m, 15m, 1h, 4h · ✅ monthly JSON · ✅ Streamlit dashboard · ✅ 100% independent of Project 1 · ✅ no API keys · ✅ no orders.

## What is different from Project 1?

- **Project 1:** Download candles with REST, maintain latest data with WebSocket, display prices.
- **Project 2:** Clean, validate, deduplicate, audit missing candle slots and optionally request real missing candles from public REST. It **does not need** Project 1 or WebSocket to work.
- If you already have Project 1 JSON data, you can **import a copy** without changing Project 1's files.

## Folder structure

```text
Project_02_BTC_Data_Quality_Lab/
├── main.py                  # All commands (demo, import, download, process, repair)
├── dashboard.py             # Read-only Streamlit UI
├── quality_lab/
│   ├── config.py            # Timeframes, UTC helpers, Delta public URL
│   ├── json_store.py        # Monthly JSON read/write/import
│   ├── delta_rest.py        # Optional REST history download + gap repair
│   ├── cleaner.py           # 6 simple validation rules
│   ├── auditor.py           # Coverage and missing candle ranges
│   ├── pipeline.py          # Run clean + audit + save
│   └── demo.py              # Synthetic candles with intentional errors
├── tests/                   # Offline automated tests
├── requirements.txt
└── README.md
```

The ZIP includes an optional **`demo_data/`** folder containing synthetic sample candles and sample quality reports. You can open the dashboard immediately to explore it. The `data/` folder is created when you run your own data commands:

```text
data/
├── raw/BTCUSD/1m/YYYY-MM.json      # source data, cleaner NEVER edits it
├── raw/BTCUSD/5m/YYYY-MM.json      # same for every timeframe
├── clean/BTCUSD/1m/YYYY-MM.json    # validated, sorted, deduplicated
├── clean/BTCUSD/5m/YYYY-MM.json
├── repairs/BTCUSD/5m/YYYY-MM.json  # optional real Delta repair data
└── reports/BTCUSD_5m_quality.json # counts + gap ranges
```

Other timeframes: `15m`, `1h`, and `4h` use the same layout.

## Step 1. Setup on Windows (PowerShell)

1. Unzip to any folder, open it in VS Code.
2. Open **Terminal → New Terminal**, run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Python 3.11+ recommended (Python 3.12 or 3.13 is a good choice).

## Step 2. First run, without internet or Project 1

```powershell
.\.venv\Scripts\python.exe main.py demo
.\.venv\Scripts\python.exe main.py process --days 2
```

The demo creates **two days of synthetic candles for all five timeframes**. Each deliberately includes a missing candle, an invalid high value, a duplicate and an out-of-order record, so you can see the cleaner fixing or reporting them.

**Expected:** every timeframe reports 1 invalid row and 1 duplicate row, plus at least 2 historical missing candle slots (the bad candle and the missing candle). If the current time moves to a new candle interval between `demo` and `process`, it may report additional recent gaps. Historical gaps are **not fabricated**.

## Step 3. Open the dashboard

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard.py
```

Visit <http://localhost:8501>. If you launch the dashboard before creating `data/`, it automatically previews bundled **synthetic** `demo_data/`. You can change the directory from the dashboard sidebar.

Tabs:
- **Overview:** counts for raw, clean, invalid, missing, coverage % for all 5 timeframes
- **Clean Candles:** candlestick chart, volume, recent rows, download displayed JSON
- **Quality Issues:** reason codes, duplicate counts, gap ranges, report download
- **How to Use:** copy/paste commands

Stop the dashboard with `Ctrl+C`.

## Step 4A. Use Project 1 data (recommended if you have already backfilled it)

**Important:** Demo creates synthetic raw files in `data/`. To keep things simple, use a separate data directory for real candles:

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe main.py --data-dir data_real import --source "C:\path\to\Project_01_Delta_BTC_JSON_Dashboard\data\candles"
.\.venv\Scripts\python.exe main.py --data-dir data_real process --days 365
```

Then launch a second dashboard configured for real data:

```powershell
$env:QUALITY_DATA_DIR="data_real"
.\.venv\Scripts\python.exe -m streamlit run dashboard.py
```

The source files in Project 1 are **copied**, not edited or removed. The importer accepts the Project 1 root folder, its `data` folder, or its `data/candles` folder.

## Step 4B. Or download 365 days independently (no Project 1 needed)

```powershell
.\.venv\Scripts\python.exe main.py --data-dir data_real download --days 365
.\.venv\Scripts\python.exe main.py --data-dir data_real process --days 365
```

The standalone downloader requests all five timeframes through `GET https://api.india.delta.exchange/v2/history/candles`, paging at most **2,000 candle slots/request**. The dataset is written page by page so if interrupted, rerunning the same command skips candles through the latest saved timestamp. Use `--from-start` to explicitly redownload the entire range.

For a tiny first download:

```powershell
.\.venv\Scripts\python.exe main.py --data-dir data_real download --days 1 --timeframes 5m
.\.venv\Scripts\python.exe main.py --data-dir data_real process --days 1 --timeframes 5m
```

The server may not have every requested historical candle. The tool never manufactures missing data. It never sends an order or uses credentials.

## Step 5. Repair specific missing gaps (optional)

After `process` has produced the gap report:

```powershell
.\.venv\Scripts\python.exe main.py --data-dir data_real repair --timeframes 5m --max-gaps 5 --max-candles 2000
.\.venv\Scripts\python.exe main.py --data-dir data_real process --days 365
```

Repair uses public REST and stores received values in **`repairs/`**, leaving original raw JSON alone. Reprocessing merges valid repairs into `clean/`, replacing matching raw timestamps. It cannot guarantee every gap can be filled: older data can be unavailable, there may genuinely be no candle, or the API may return no rows. Don't forward-fill OHLCV or invent prices for backtests.

## Step 6. Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## How cleaning works (basic rules)

1. **Timestamp:** must include timezone and align to the timeframe (e.g., 5m: 10:00, 10:05, 10:10 UTC).
2. **Completed candle:** reject current unfinished or future candles.
3. **OHLC:** prices must be finite and positive; high >= open/close/low; low <= open/close/high.
4. **Volume:** must be finite and >= 0.
5. **Duplicates:** keep the last **valid** record for each timestamp. Prefer an explicit API repair over raw at the same timestamp.
6. **Ordering:** sort by timestamp and report out-of-order raw records.
7. **Coverage:** compare actual closed candles against expected aligned timestamps. Store compact gap **ranges** to keep reports small even for one-year 1m history.
8. **Outliers:** warn if an adjacent close changes by >10%; do **not** silently delete it.

> UTC matters: the candle timestamp is stored with `Z` for UTC. To display India time in a later project, convert from UTC to Asia/Kolkata; never shift timestamps by hand in stored JSON.

## JSON example

```json
[
  {"timestamp_utc":"2026-10-31T10:00:00Z","open":100000.0,"high":100100.0,"low":99950.0,"close":100070.0,"volume":12.2}
]
```

This is an illustrative candle, not a market quote.

## What Project 2 intentionally does not do

- It does not run a WebSocket collector. **Project 1 owns live collection**; Project 2 processes saved JSON files.
- It does not produce strategy signals, backtest returns, or trade orders.
- It does not silently repair or invent missing candles.
- It is a single-writer educational local project. Do not run `import`, `download`, `process` and `repair` concurrently against the same data folder.
- A one-year run with 1m data can require significant memory and disk; use shorter ranges for the first practice session.

## Official API reference

Delta Exchange India: <https://docs.delta.exchange/> (`GET /v2/history/candles`)

## Next project

**Project 3 — Technical Indicator Calculator** will read `data/clean/BTCUSD/<timeframe>/YYYY-MM.json` to calculate EMA, SMA, RSI, MACD and ATR without fetching data again.
