# Mini-Project 4 — BTC Trading Signal Generator (Standalone)

**Goal:** Read completed BTCUSD indicator candles from Project 3; generate educational **BUY / SELL / HOLD labels** using an **EMA(9/21) crossover plus RSI(14) filter**; explore them in a read-only Streamlit dashboard.

**This is a new project, not an edit to Projects 1–3. It requires no API keys, login, REST calls, WebSocket connection or trading account. There is no execution or PnL in Project 4.** You can explore it on day one with included **synthetic demonstration data**. All synthetic records are explicitly labeled.

## 1. Project stages

| Project | Purpose | Main output |
|---|---|---|
| Project 1 | Download Delta BTCUSD candles (REST + WS) | Raw monthly JSON OHLCV |
| Project 2 | Clean candles and detect gaps | Clean monthly JSON OHLCV |
| Project 3 | Calculate technical indicators | `indicators/BTCUSD/5m/YYYY-MM.json` etc. |
| **Project 4** | **Apply simple testable strategy rules** | `signals/BTCUSD/5m/YYYY-MM.json` etc. |
| Project 5 | Visualize price and indicators with more charting | Interactive charting |
| Project 6+ | Backtest strategies | Transaction-aware trading results |

## 2. Folder structure

```text
Project_04_BTC_Trading_Signal_Generator/
├── main.py                    CLI commands (generate, summary)
├── dashboard.py               Streamlit UI (read-only)
├── signal_lab/
│   ├── __init__.py
│   ├── config.py               BTC symbol, timeframe durations, RSI settings
│   ├── json_files.py           Read/validate Project 3 JSON + atomic monthly writes
│   ├── strategy.py             Streaming crossover + RSI confirmation
│   └── pipeline.py             Five-timeframe generator + reports
├── demo_input/                INCLUDED synthetic Project 3-style indicator JSON
├── demo_results/              INCLUDED calculated synthetic BUY/SELL/HOLD results
├── tests/                     Unit and integration tests
├── requirements.txt
├── .streamlit/config.toml
└── README.md
```

## 3. Start in VS Code (Windows PowerShell)

Open the extracted project folder, where `main.py` is located.

### Step A — Install dependencies

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Step B — Open the dashboard immediately

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard.py
```

Visit **http://localhost:8501**. The dashboard defaults to `demo_results/`, which is already bundled. You do NOT need Project 1, 2, or 3 for the demo. Use the timeframe menu to switch between `1m`, `5m`, `15m`, `1h`, `4h`. All prices are synthetic.

### Step C — Generate your first signals yourself

```powershell
.\.venv\Scripts\python.exe main.py generate --source demo_input --output output
.\.venv\Scripts\python.exe main.py summary --output output
```

In the dashboard sidebar, change **Signal output folder** to `output` and inspect the results.

### Step D — Use the real indicator JSON from Project 3

Run Project 3 first against clean Project 2 data. Then point Project 4 at **the Project 3 OUTPUT folder** (the folder containing `indicators/BTCUSD/...`). For example:

```powershell
.\.venv\Scripts\python.exe main.py generate --source "C:\path\to\Project_03_BTC_Technical_Indicator_Studio\data_real" --output data_real
.\.venv\Scripts\python.exe main.py summary --output data_real
```

If the Project 3 results were written to its default `data/` folder, use that folder instead. Avoid pointing at Project 2's `clean/` JSON files: they do not include EMA and RSI indicators.

Switch the dashboard's output folder to `data_real`.

### Step E — Process only a few timeframes

```powershell
.\.venv\Scripts\python.exe main.py generate --source demo_input --output output --timeframes 5m 15m
```

### Step F — Customize RSI confirmation ranges

```powershell
.\.venv\Scripts\python.exe main.py generate --source demo_input --output custom_results --rsi-buy-min 55 --rsi-buy-max 70 --rsi-sell-min 30 --rsi-sell-max 45
```

These are hypothetical research parameters, not optimized or proven profitable rules. Running a new configuration in a separate output folder preserves earlier results for comparison.

### Step G — Run tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## 4. Rules in plain English

We use **EMA 9** as the fast trend estimate, **EMA 21** as the slower trend estimate, and **RSI 14** to filter momentum.

| Label | Required conditions | Why |
|---|---|---|
| BUY | Prior EMA 9 <= EMA 21, current EMA 9 > EMA 21, and **50 <= RSI <= 75** | Fast EMA crossed up and momentum is in chosen window |
| SELL | Prior EMA 9 >= EMA 21, current EMA 9 < EMA 21, and **25 <= RSI <= 50** | Fast EMA crossed down and momentum is in chosen window |
| HOLD | Anything else, including indicator warm-up and detected gaps | No qualifying crossover |

**Important:** SELL means *bearish directional label*. It is not an instruction to sell an existing holding or initiate a short. Project 4 does **not** track position state or generate actual orders.

A crossover that fails the RSI filter becomes HOLD; it does not automatically turn into a BUY or SELL later when RSI changes. Only a **new** EMA crossover is considered.

## 5. Timing and look-ahead safety

A historical candle is identified by its **opening** timestamp. For example:

- `timestamp_utc` = `2026-10-31T10:00:00Z` for a 5m bar.
- `decision_time_utc` = `2026-10-31T10:05:00Z`, the earliest time the candle's complete indicator values can be known.

Do not assume a strategy could execute a trade at the 10:00 candle's closing price with zero delay or slippage. Future Project 6 must simulate a next-bar or explicit post-close fill.

- The engine skips candles not yet finished at its `as_of` time.
- Only current and earlier completed candles are consulted. There are no future indicator values.
- On a time gap, previous EMA crossover state is reset; no crossover is inferred across the missing interval.
- Missing indicators (`null`) produce HOLD with reason `INDICATOR_NOT_READY`.
- A crossover is allowed across a **month boundary** if adjacent candles are continuous.

You may pass a fixed `--as-of-utc 2026-11-01T00:00:00Z` for reproducible research runs.

## 6. Output structure

```text
output/
├── signals/BTCUSD/
│   ├── 1m/2026-10.json
│   ├── 5m/2026-10.json
│   ├── 15m/2026-10.json
│   ├── 1h/2026-10.json
│   └── 4h/2026-10.json
└── reports/
    ├── BTCUSD_1m_signals.json
    ├── BTCUSD_5m_signals.json
    ├── BTCUSD_15m_signals.json
    ├── BTCUSD_1h_signals.json
    └── BTCUSD_4h_signals.json
```

The engine creates additional monthly files when processing a year. It **never changes the input indicator JSON files**.

Example signal record (illustrative, NOT real BTC data):

```json
{
  "timestamp_utc": "2026-10-31T10:00:00Z",
  "decision_time_utc": "2026-10-31T10:05:00Z",
  "close": 100100.0,
  "ema_9": 100080.0,
  "ema_21": 100050.0,
  "rsi_14": 61.0,
  "signal": "BUY",
  "reason": "BULLISH_EMA_CROSSOVER_RSI_CONFIRMED",
  "gap_before": false
}
```

`signal` is the label; `reason` is *why* the label was produced. The example assumes the prior EMA9 was at or below EMA21. One row alone cannot prove that a crossover happened.

## 7. Dashboard tabs

1. **Price & Signals**: recent candle closes, EMA9/EMA21 lines, BUY/SELL markers, and RSI chart.
2. **Signal Explorer**: filter BUY/SELL/HOLD, view timestamps and reasoning, export recent rows to CSV or JSON.
3. **Data Quality**: missing candle slots, incomplete candles skipped, counts and source origin.
4. **Learn the Rules**: readable buy/sell conditions and why decisions only occur after candle close.

The dashboard reads only a recent sample of the monthly files (100–2,000 bars), so it does not load a full year of 1m JSON into a plot.

## 8. Common problems

**"Indicator JSON not found"** — The source must be the Project 3 *output root*, containing `indicators/BTCUSD/1m/YYYY-MM.json`, not the Project 2 cleaned candle folder.

**All signals HOLD** — An indicator may still be warming up; EMA may not cross during this window; the RSI filter may reject crossings. That is not automatically a bug.

**Dashboard doesn't show new output** — Enter the exact value of `--output` in the sidebar, then refresh the browser.

**A signal appears one bar late** — The chart plots the candle at its start timestamp, but the decision timestamp marks its completion. The latter is the correct knowledge time.

**Can I run live trades?** — No. This project has no order API; connect that only in the much later testnet-first execution phase with separate risk controls.

## 9. Completion checklist

- [ ] Dashboard opens with synthetic demo results.
- [ ] Generate my own five-timeframe signals from `demo_input`.
- [ ] Inspect at least one BUY, SELL, HOLD example and its reason.
- [ ] Verify `decision_time_utc` is exactly one timeframe after candle opening.
- [ ] Run Project 3 on clean BTCUSD data and import results here.
- [ ] Inspect gaps and indicator warm-up.
- [ ] Automated tests pass.

**Next project:** Mini-Project 5 — Interactive BTC Market Chart (candles + indicators + signal overlays), or move to vectorized backtesting when you're comfortable with Project 4.
