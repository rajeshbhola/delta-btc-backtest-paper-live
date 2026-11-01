# Mini-Project 5 — BTC Interactive Chart & Signal Explorer

**A NEW, fully standalone Python application** · Delta Exchange India BTCUSD futures · Streamlit + Plotly · JSON only · **READ ONLY**

## Goal

Learn to visualize historical **BTCUSD OHLCV candlesticks**, Project 3 technical indicators, and Project 4 BUY/SELL/HOLD labels in one simple interface. It supports **1m, 5m, 15m, 1h and 4h** data, including monthly JSON history collected over one year. It does **not** need any API key, Delta login, REST or WebSocket service, or trading account.

All files under `demo_data/` are **SYNTHETIC**. They are for learning the UI—not for backtesting real market behavior or trading with money.

## 1. What you will build

```text
Project 1: historical candles    -> candles/BTCUSD/<timeframe>/YYYY-MM.json
Project 2: clean candles         -> clean/BTCUSD/<timeframe>/YYYY-MM.json
Project 3: technical indicators  -> indicators/BTCUSD/<timeframe>/YYYY-MM.json
Project 4: BUY/SELL/HOLD labels  -> signals/BTCUSD/<timeframe>/YYYY-MM.json
                                           |
                                           v
                    PROJECT 5: BTC Chart & Signal Explorer
                    - candlestick + volume chart
                    - overlays: EMA 9/21/50, SMA 20/50, Bollinger Bands
                    - panels: RSI 14, MACD, ATR 14
                    - BUY/SELL markers placed at decision time
                    - signal table / JSON download / offline HTML chart export
                    - data-quality warnings (missing candle slots, OHLC)
```

**Standalone guarantee:** Use `demo_data/` immediately without installing or running Projects 1–4. To view your own data later, supply their JSON output folder paths. No project-to-project Python imports are needed.

## 2. Windows setup (VS Code / PowerShell)

1. Extract the ZIP, then open the folder containing `dashboard.py` in VS Code.
2. Open Terminal -> New Terminal.
3. Create virtual environment and install packages:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

4. Launch the UI:

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard.py
```

5. Open the URL Streamlit prints (typically **http://localhost:8501**).
6. Leave **Bundled synthetic demo** selected and switch between 1m / 5m / 15m / 1h / 4h.
7. Try an EMA overlay, the MACD and RSI panels, and the **Signals Explorer** tab.

**macOS/Linux**: `python3 -m venv .venv`, then `.venv/bin/python -m pip install -r requirements.txt`, and `.venv/bin/python -m streamlit run dashboard.py`.

## 3. What every dashboard tab shows

| Tab | What you learn |
| --- | --- |
| Interactive Chart | BTCUSD OHLCV candlestick + volume; choose EMA/SMA/Bollinger overlays, view RSI/MACD/ATR, BUY/SELL markers, export standalone HTML |
| Signals Explorer | Filter Project 4 labels, inspect reasons and `decision_time_utc`, download JSON |
| Data Quality | Report shown-window missing timestamps, invalid OHLC, negative volume, source-price disagreements |
| Learning Guide | Understand input data and indicator/decision-time semantics |

**Important signal timing**: candles use the **opening** timestamp `timestamp_utc`; labels become known only at `decision_time_utc` after the source candle closes. The chart's BUY/SELL markers are plotted at **decision time**, not candle open. They are not executable orders. This project **does not backtest**, infer fills or compute PnL.

## 4. Use the original Project 1/2/3/4 JSON data

Open the sidebar and select **My Project 1–4 JSON folders**.

- **Candles root**: paste the **Project 1 output root** that contains `candles/BTCUSD/` **or** the Project 2 output root that contains `clean/BTCUSD/` (recommended).
- **Indicators root**: paste the **Project 3 output root** that contains `indicators/BTCUSD/`.
- **Signals root**: paste the **Project 4 output root** that contains `signals/BTCUSD/`.

Example Windows paths:

```text
Candles:    C:\Projects\Project_02_BTC_Data_Quality_Lab\data_real
Indicators: C:\Projects\Project_03_BTC_Technical_Indicator_Studio\data_real
Signals:    C:\Projects\Project_04_BTC_Trading_Signal_Generator\data_real
```

The folder could be named `data`, `data_real`, `output`, etc. What matters is the nested `clean/BTCUSD/`, `indicators/BTCUSD/`, or `signals/BTCUSD/` structure. You can point directly at the `BTCUSD/` folder too.

**If you only have Project 1:** the app displays candles + volume but has no Project 3 indicator overlays or Project 4 signals. **If you only have Project 3:** the indicator JSON also contains OHLCV, so you can use its root for indicators without providing a separate candle folder. **If you only have Project 4:** its signal JSON has `close` but not OHLC, so a full candlestick chart still needs Project 1/2/3 data.

Use the same timeframe and timestamp convention across all sources. The dashboard joins indicator values to candles by **exact UTC timestamp**. It does not forward-fill values or fabricate missing candles. If matched `close` prices disagree between the two sources, it warns you.

## 5. UI performance on a one-year 1m dataset

A complete year of 1m BTCUSD candles is approximately 525,600 bars. Plotting them all at once would be inefficient.

Select a start and end **UTC date** in the sidebar. The program reads only monthly JSON files overlapping the selected window and shows **the most recent N candles** within that window (default N=1500, adjustable to 5000). It reads at most one month into memory at a time. This cap applies to what you see, not to what is stored. Thus **data-quality results describe only the displayed window**, not the entire historical year. Use Project 2 for full-history audits.

## 6. Additional simple CLI commands

Create a fresh set of synthetic monthly JSON in a separate folder:

```powershell
.\.venv\Scripts\python.exe main.py demo --output my_demo
```

Print a quick summary of existing demo candles and signals:

```powershell
.\.venv\Scripts\python.exe main.py inspect --timeframe 5m --days 7
```

Export a self-contained interactive chart that works without Streamlit or internet:

```powershell
.\.venv\Scripts\python.exe main.py export --timeframe 5m --days 7 --output exports/BTCUSD_5m_chart.html
```

Open the resulting `exports/BTCUSD_5m_chart.html` in your browser. Plotly JavaScript is embedded into this HTML file.

Inspect your own data instead of `demo_data`:

```powershell
.\.venv\Scripts\python.exe main.py inspect --timeframe 15m --days 30 --candles "C:\Projects\Project_02\data_real" --indicators "C:\Projects\Project_03\data_real" --signals "C:\Projects\Project_04\data_real"
```

### Export and data folder structure

```text
Project_05_BTC_Interactive_Chart_Explorer/
├── main.py                  CLI: demo, inspect, export
├── dashboard.py             read-only Streamlit UI
├── chart_lab/
│   ├── config.py            five timeframe durations
│   ├── sources.py           JSON loader + cross-project compatibility
│   ├── analytics.py         gap/quality and signal summaries
│   ├── figures.py           Plotly candlesticks, volume and oscillators
│   └── demo.py              synthetic demo generator
├── demo_data/
│   ├── SYNTHETIC_DATA_NOTICE.txt
│   ├── candles/BTCUSD/{1m,5m,15m,1h,4h}/YYYY-MM.json
│   ├── indicators/BTCUSD/{1m,5m,15m,1h,4h}/YYYY-MM.json
│   └── signals/BTCUSD/{1m,5m,15m,1h,4h}/YYYY-MM.json
├── tests/
├── .streamlit/config.toml
├── requirements.txt
└── README.md
```

## 7. Run automated tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Offline tests cover source detection for Projects 1–4, month boundaries, UTC time handling, recent-N loading, candle/indicator matching, price mismatches, gap detection, invalid OHLC, signal timestamps, Plotly figures and demo generation. No exchange keys or external network access are required.

## 8. Troubleshooting

- **No candle files found:** use the output ROOT (e.g. `data_real`) containing `clean/BTCUSD/5m/YYYY-MM.json`, not an individual JSON file. Confirm the selected timeframe exists.
- **No BUY/SELL markers:** the selected Project 4 output may have no qualifying crossover in this window; try a wider range, or check the Signals Explorer tab.
- **No EMA/RSI values:** choose Project 3's *output*, not Project 2's raw/clean candle folder. Indicator warm-up values may correctly be `null`.
- **Signal marker appears later than its candle:** correct; it shows when the signal became knowable, not the bar's opening time.
- **Charts use synthetic $100k BTC prices:** the bundled demo is entirely fictional. Select your own JSON folders to see downloaded market data.
- **Very large files slow down the UI:** select a shorter UTC window or lower the `Max recent candles` slider.
- **Duplicate or missing records:** clean the source with Project 2; this app does not change original data.
- **No API connection:** expected. Project 5 is a read-only local viewer and does not connect to Delta Exchange.

## 9. Completion checklist

- [ ] Dashboard loads synthetic candles for all five timeframes.
- [ ] EMA/SMA/Bollinger overlays show on the price chart.
- [ ] RSI/MACD/ATR indicators render in separate panels.
- [ ] BUY/SELL decision-time markers align with Project 4 JSON.
- [ ] Signal Explorer filters and JSON download work.
- [ ] Export an interactive `.html` chart successfully.
- [ ] Connect one real clean JSON dataset from Project 2 and indicators from Project 3.
- [ ] Review gaps and source mismatches before interpreting any chart.
- [ ] Run automated tests successfully.

**Next: Project 6 — Vectorized BTC Strategy Backtester.** It will use cleaned candles and signals, model *next-bar* entries, trading fees, and PnL. Project 5 itself never places trades.
