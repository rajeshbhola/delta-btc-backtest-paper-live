# Project 3 — BTC Technical Indicator Studio (Standalone)

**Goal:** calculate and explore technical indicators for BTCUSD perpetual futures candles. This is a fresh, standalone mini-project with its own Python application, monthly JSON outputs, sample data, Streamlit dashboard, and automated tests.

| Project | Job |
| --- | --- |
| Project 1 | Download Delta BTCUSD candles via REST, follow current candles via WebSocket |
| Project 2 | Check, clean and repair (where possible) monthly JSON candle data |
| **Project 3** | **Compute SMA, EMA, RSI, MACD, Bollinger Bands, ATR and chart them** |
| Project 4 | Use indicators to generate BUY/SELL/HOLD signals (not implemented here) |

No Delta API key, WebSocket, broker account, positions or orders are used by Project 3. **All supplied demo prices are synthetic, not real BTC prices.** Demo-origin reports and the UI carry a persistent warning even when you choose a generic output folder name.

## File layout

```text
Project_03_BTC_Technical_Indicator_Studio/
├── main.py                   # CLI: demo, analyze, summary
├── dashboard.py              # Read-only Streamlit UI
├── indicator_studio/
│   ├── config.py             # Timeframe and indicator names
│   ├── indicators.py         # Streaming SMA/EMA/RSI/MACD/BB/ATR calculations
│   ├── json_files.py         # JSON read/write and Project 2 compatibility
│   ├── pipeline.py           # Monthly analysis and gap reports
│   └── demo.py               # Synthetic BTCUSD candles
├── demo_data/clean/BTCUSD/   # Included synthetic input dataset
├── demo_results/            # Included computed synthetic output
├── tests/                   # Automated offline tests
├── requirements.txt
└── README.md
```

## Windows PowerShell: step-by-step

### 1. Open the extracted folder in VS Code

Open a PowerShell terminal in the folder containing `main.py`.

### 2. Set up Python

Python 3.11+ is recommended.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Launch dashboard right away (built-in demo)

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard.py
```

Open http://localhost:8501. The included `demo_results/` folder previews all six indicators in all five timeframes. **Its prices are synthetic**. Use the dashboard's sidebar to select a timeframe and switch to real data later.

### 4. Recalculate demo indicators yourself

```powershell
.\.venv\Scripts\python.exe main.py analyze --source demo_data --output data
.\.venv\Scripts\python.exe main.py summary --output data
```

Dashboard's data folder will default to `data` once it exists. For a newly generated synthetic dataset:

```powershell
.\.venv\Scripts\python.exe main.py demo --output my_demo --rows 500
.\.venv\Scripts\python.exe main.py analyze --source my_demo --output data
```

**One intentionally missing candle** exists in each demo timeframe. The analyzer reports it and starts fresh indicator warm-up after the gap. It does not fabricate candles.

### 5. Analyze real cleaned Project 2 data

For Project 2's `data_real/clean/BTCUSD/1m/YYYY-MM.json` files (and all other timeframes):

```powershell
.\.venv\Scripts\python.exe main.py analyze --source "C:\path\to\Project_02_BTC_Data_Quality_Lab\data_real" --output data_real
```

Or point directly at its `clean` directory:

```powershell
.\.venv\Scripts\python.exe main.py analyze --source "C:\path\to\Project_02_BTC_Data_Quality_Lab\data_real\clean" --output data_real
```

To process only two timeframes:

```powershell
.\.venv\Scripts\python.exe main.py analyze --source "C:\path\to\Project_02_BTC_Data_Quality_Lab\data_real" --output data_real --timeframes 5m 15m
```

Switch the dashboard's **Project 3 output folder** to `data_real`.

**Project 1 JSON is also supported** using `--source "C:\path\to\Project_01\data\candles"`, but Project 2 cleaned JSON is safer. If invalid, duplicated, or unsorted candles are found, Project 3 stops and asks you to clean them first rather than silently accepting bad values.

### 6. Run offline tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## How the six indicator families work

| Family | Output fields | Calculation |
| --- | --- | --- |
| SMA | `sma_20`, `sma_50` | Mean of last 20 or 50 closes |
| EMA | `ema_9`, `ema_21`, `ema_50` | EMA with alpha 2/(period+1), SMA-seeded |
| RSI | `rsi_14` | Wilder-smoothed relative strength, period 14 |
| MACD | `macd`, `macd_signal`, `macd_histogram` | EMA12 - EMA26, EMA9 of MACD, difference |
| Bollinger Bands | `bb_middle`, `bb_upper`, `bb_lower`, `bb_width_pct` | SMA20 ± 2 population standard deviations |
| ATR | `atr_14` | Wilder-smoothed true range over 14 bars |

**Calculation choices:** The EMA is seeded using the first N prices' SMA, rather than starting the EMA at the first close. RSI starts after 14 *changes* (15 candles); flat price results in RSI = 50. ATR includes high-low on the first candle and starts after 14 bars. MACD's signal starts once nine MACD values exist (first fully ready at bar 34, counting from 1: after 26 bars of EMA26 + 8 additional). Bollinger uses population stdev (ddof=0). Other charting packages can seed indicators differently; compare like-for-like when validating outputs.

**Critical for backtesting:** All indicators only use current and previous completed candle values. `null` means insufficient warm-up, not zero. After a missing candle interval, each indicator is restarted to prevent pretending the price series is continuous. The engine carries indicator state precisely across month boundaries, and processes monthly files sequentially to avoid loading the entire year of 1m candles into memory.

## Result files

```text
data_real/
├── indicators/BTCUSD/
│   ├── 1m/YYYY-MM.json
│   ├── 5m/YYYY-MM.json
│   ├── 15m/YYYY-MM.json
│   ├── 1h/YYYY-MM.json
│   └── 4h/YYYY-MM.json
└── reports/
    ├── BTCUSD_1m_indicators.json
    ├── BTCUSD_5m_indicators.json
    └── ...
```

Every JSON row includes original OHLCV plus indicators, for example:

```json
{
  "timestamp_utc": "2026-10-30T09:15:00Z", "open": 100000.0,
  "high": 100150.0, "low": 99950.0, "close": 100100.0,
  "volume": 7.5, "sma_20": 100030.2, "ema_9": 100055.3,
  "rsi_14": 58.4, "macd": 15.2, "macd_signal": 11.8,
  "macd_histogram": 3.4, "bb_middle": 100030.2,
  "bb_upper": 100240.5, "bb_lower": 99819.9,
  "bb_width_pct": 0.4205, "atr_14": 125.8
}
```

That record is only an illustrative *subset* of keys. Real output includes all 14 indicator fields; warm-up values may be `null`.

## Dashboard tabs

1. **Price & Trends** — candlestick/volume plus user-selected SMA, EMA and Bollinger overlays.
2. **Momentum** — RSI chart with reference lines at 30 and 70; MACD with signal/histogram.
3. **Volatility** — Bollinger bands and ATR volatility chart.
4. **Data & Learning** — recent JSON rows, JSON/CSV downloads, gap warnings, formula explanations.

The dashboard reads only the latest selected candles (100–2,000), so opening a 1-year dataset is fast. The user chooses the timeframe and output directory. Dashboard does not run the analyzer or modify the source candles.

## Common questions

**Can I use it without Project 1 or Project 2?** Yes, use the bundled synthetic demo files. For live-market history, import real cleaned JSON from Project 2.

**Does Project 3 fetch Delta market data?** No. The job is calculation and visualization, not collection. Project 1 handles REST and WebSocket ingestion.

**Is a BUY signal automatically generated when RSI < 30?** No. Indicators are observations, not trade rules. Project 4 will generate testable signals and check for look-ahead bias.

**Will it overwrite Project 2?** No. `--source` is input-only. Project 3 writes only to `--output`, and refuses an output path nested under the input source directory.

**What if gaps exist?** They are reported, and indicator warm-up starts over after each gap. Repair missing history in Project 2 and rerun Project 3.

**Is this production/live trading software?** No. It is intentionally read-only and contains no private API authentication or trading methods.
