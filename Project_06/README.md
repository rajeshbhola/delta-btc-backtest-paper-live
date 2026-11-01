# Mini-Project 6 — BTC Vectorized Backtesting Engine

**30-project Python algo-trading roadmap · Phase 2, Project 6 · Completely standalone**

**What you are building:** An **offline**, beginner-friendly Bitcoin BTCUSD historical trading simulator that reads historical **OHLCV monthly JSON** and **BUY/SELL/HOLD signals**, generates positions without look-ahead, computes a simulated equity curve and trade history, and shows results in a **Streamlit + Plotly** dashboard. This is a separate project; **do not copy or install code from Projects 1–5**.

**Not included:** Delta orders, network requests, API keys, live prices, tax analysis, liquidation, margin, perpetual funding, slippage, order-book liquidity, stop-losses or take-profit exits. These arrive later in the roadmap. **No strategy is guaranteed profitable.**

All included demo candles and signals are **synthetic**. They are not real Delta market history. The sample win rate or return says **nothing** about actual trading performance.

## 1. How it builds on earlier projects

| Project | What it produces | How Project 6 uses it |
|---|---|---|
| 1 — Historical Data | Raw JSON: `candles/BTCUSD/5m/YYYY-MM.json` | Can load, but cleaning recommended |
| 2 — Data Cleaner | Clean JSON: `clean/BTCUSD/5m/YYYY-MM.json` | Recommended candles input |
| 3 — Indicators | `indicators/BTCUSD/5m/YYYY-MM.json` | Can be used as candle input (includes OHLCV) |
| 4 — Signals | `signals/BTCUSD/5m/YYYY-MM.json` | **Required** signal input for historical entries |
| 5 — Chart Explorer | Visualizations | Optional; not required |
| **6 — Backtesting** | `equity/`, `trades/`, `reports/` | Simulates historical trades and reports results |

**Supported timeframes:** `1m`, `5m`, `15m`, `1h`, `4h`.

## 2. Files

```text
Project_06_BTC_Vectorized_Backtesting_Engine/
├── main.py                     # CLI entry point
├── dashboard.py                # Streamlit chart/dashboard
├── requirements.txt
├── backtest_lab/
│   ├── __init__.py
│   ├── config.py               # Symbol, timeframe durations
│   ├── data.py                 # Load and validate Projects 1–4 monthly JSON
│   ├── engine.py               # Vectorized position / return / equity calculations
│   └── pipeline.py             # Run all timeframes and save JSON results
├── demo_data/                 # Synthetic indicator candles + synthetic Project 4 signals
│   ├── indicators/BTCUSD/{1m,5m,15m,1h,4h}/YYYY-MM.json
│   └── signals/BTCUSD/{1m,5m,15m,1h,4h}/YYYY-MM.json
├── demo_results/              # Precomputed synthetic backtests; dashboard works immediately
│   ├── equity/BTCUSD_5m.json
│   ├── trades/BTCUSD_5m.json
│   └── reports/BTCUSD_5m.json
├── tests/
├── .streamlit/config.toml
└── README.md
```

## 3. Install on Windows with VS Code (PowerShell)

Open the extracted project directory containing `main.py`.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 4. Open the included demo dashboard immediately

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard.py
```

Open http://localhost:8501 . The default `demo_results` folder is included, so you can explore the dashboard without running a command, downloading market data, or creating an API key.

The dashboard shows:

- **Performance:** Net return, end equity, max drawdown, win rate, trades, equity curve.
- **Trade Log:** Long/short, entry/exit timestamps, prices, net simulated PnL and fees.
- **Price & Signals:** BTCUSD candlesticks, BUY/SELL markers on the *signal bars*.
- **Quality & Learning:** Missing bars, missing signal labels, strategy timing, configuration, cautions.

The dashboard **only reads output JSON**. Run `main.py` in a second terminal to recompute results.

## 5. Run your first backtest (with included synthetic demo)

Default: 5-minute BTC candles, **LONG ONLY**, starting **$10,000 USD** simulated equity, **0 bps fees**.

```powershell
.\.venv\Scripts\python.exe main.py run --candles demo_data --signals demo_data --output results
```

Then show the summary:

```powershell
.\.venv\Scripts\python.exe main.py summary --output results --timeframe 5m
```

In Streamlit, select `results` in the sidebar.

**Run all five timeframes separately in the same invocation:**

```powershell
.\.venv\Scripts\python.exe main.py run --candles demo_data --signals demo_data --output results --timeframes 1m 5m 15m 1h 4h
```

**Try LONG/SHORT mode, with an illustrative basic 5 bps fee per entry/exit:**

```powershell
.\.venv\Scripts\python.exe main.py run --candles demo_data --signals demo_data --output custom_results --timeframes 5m --mode long_short --capital 10000 --fee-bps 5
```

**For a 30-day period, ending at the latest available completed candle:**

```powershell
.\.venv\Scripts\python.exe main.py run --candles demo_data --signals demo_data --output results --timeframes 5m --days 30
```

Set a reproducible final cutoff (UTC):

```powershell
.\.venv\Scripts\python.exe main.py run --candles demo_data --signals demo_data --output results --as-of-utc 2026-11-01T00:00:00+00:00
```

## 6. Backtest with real data from Projects 2–4

Use a folder containing Project 2's **cleaned** candles and Project 4's signal output. Those can be **different** folders; this project reads them but does not modify them.

```powershell
.\.venv\Scripts\python.exe main.py run --candles "C:\path\to\Project_02_BTC_Data_Quality_Lab\data_real" --signals "C:\path\to\Project_04_BTC_Trading_Signal_Generator\data_real" --output results_real --timeframes 1m 5m 15m 1h 4h
```

If you prefer Project 3's indicator output as candle source, replace `--candles` with `C:\path\to\Project_03_BTC_Technical_Indicator_Studio\data_real`. Project 3 indicator rows contain OHLCV plus indicator columns, which are fine.

The loader automatically locates:

```text
candles root: clean/BTCUSD/5m/YYYY-MM.json
          OR candles/BTCUSD/5m/YYYY-MM.json
          OR indicators/BTCUSD/5m/YYYY-MM.json
signals root: signals/BTCUSD/5m/YYYY-MM.json
```

The app will **reject** duplicate timestamps, misaligned candle timestamps, impossible OHLC prices, mismatched signal close prices, and invalid signal decision times. A missing signal label is treated as HOLD **and explicitly counted** in the quality report. A missing candle is **never filled with invented prices**.

For one-year datasets, run only one or a few timeframes at a time if memory is limited. The program reads all monthly records for the selected timeframe into pandas; for 1m over a year this can use substantial memory. Output JSON can also be large. Optimized streaming/memory-mapped processing is outside this beginner project.

## 7. Precisely how the simulation works

### Signals are known **after** the completed candle

Consider a 5-minute BTC candle spanning **10:00–10:05 UTC**:

1. Candle opens at 10:00 UTC. Its final close, RSI, and crossover are **not yet known**.
2. Candle completes at **10:05 UTC**. Project 4 labels it `BUY`.
3. At the **next candle open at 10:05 UTC**, Project 6 takes a simulated LONG position if this candle exists and is contiguous.
4. While long, hypothetical equity changes with the next open-to-open price movement.
5. A later `SELL` means exit at the next available **contiguous** candle open (long-only mode).
6. An open position remaining at the **end of the historical dataset** is marked and closed at the last bar's **close** for a finite result.

This is not a fill guarantee. Real exchange market orders can have spread and slippage; limits can fail to fill.

### What BUY / SELL / HOLD mean

| Signal | `long_only` (default) | `long_short` (experimental) |
|---|---|---|
| BUY | Enter/keep long | Enter/flip to long |
| SELL | Exit long / stay flat | Enter/flip to short |
| HOLD | Keep current position | Keep current position |

An entry or exit always occurs at a **following open**; holding a position across missing data is handled conservatively: it is flattened at the first next available candle open, while the price gap is still booked to the prior holding period. Signals from before gaps are not executed *after* the gap. The first candle never opens a trade because its previous candle signal is unknown.

### Vectorized formula (simplified)

For each bar, `r = (next_open - current_open) / current_open` (last bar: `last_close` instead of `next_open`).

- `position` = **+1** (long), **0** (flat), or **−1** (short).
- `gross_factor = 1 + position × r`.
- `fee_factor = (1 - fee_bps / 10000) ^ number_of_entries_or_exits`.
- `equity = starting_capital × cumulative_product(gross_factor × fee_factor)`.

The engine assumes **1x notional exposure continuously rebalanced each candle**, so long/short compounding may differ from the fixed-contract PnL of an actual Delta BTC futures position. The simple fee parameter is a **teaching approximation**, not verified Delta charges. The phase 2 cost and event-driven projects address more realism.

**Example:** BTC BUY signal detected at 10:05. Next candle opens at 100; eventually exit at 102. With zero fees, a simple two-percent long move corresponds to approximately +$200 on a $10,000 1x nominal account (under the simplified model). This does not include actual Delta contract size, funding, charges or tax.

### What is NOT modeled yet

- Market/limit order matching, fill probability, spread, slippage or partial fills.
- Maker/taker distinction, real Delta product contract multipliers, GST, funding or exchange fees.
- Collateral and margin, leverage, liquidation, cross/isolated modes, tick/lot restrictions.
- Realistic stop-loss or take-profit intrabar execution.
- Chronological out-of-sample validation or statistical significance.

Do not use these outputs to justify real-money trading. The next steps add costs, event-driven execution and realistic risk controls.

## 8. Output JSON

```text
results/
├── equity/
│   ├── BTCUSD_1m.json
│   ├── BTCUSD_5m.json
│   ├── BTCUSD_15m.json
│   ├── BTCUSD_1h.json
│   └── BTCUSD_4h.json
├── trades/
│   └── BTCUSD_5m.json  # and other chosen timeframes
└── reports/
    └── BTCUSD_5m.json  # and other chosen timeframes
```

`equity` files contain simulated equity, position, signal, gross return, simplified fee event count and drawdown for each historical candle. `trades` files list entry/exit and net PnL for each position run. `reports` files contain the summary metrics and input audit. Data is written to a **separate output folder** from your input files.

The latest equity timestamp is labeled `mark_time_utc` (when that account valuation is actually known), rather than incorrectly attributing the return to the candle's start. This prevents chart-based look-ahead.

## 9. Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests cover: next-bar-open timing; final candle close; long-only versus long/short; exit/entry fee accounting; missing candles; short profit; timestamp integrity; bad price data; signal price mismatch; incomplete candle filtering; fee/equity reconciliation; actual Project 4 synthetic JSON compatibility; read-only source behavior; and all five timeframes.

## 10. Definition of done

- [ ] Open included dashboard on synthetic data.
- [ ] Re-run a 5m backtest from bundled JSON and inspect reports.
- [ ] Explain why a BUY at candle close enters at the **next candle open**.
- [ ] Run LONG ONLY and LONG/SHORT; compare equity and drawdown.
- [ ] Run a nonzero simple fee assumption and compare results.
- [ ] Import Project 2 candles + Project 4 signals, one timeframe at a time.
- [ ] Review gaps, missing signals and result limitations.
- [ ] Pass all automated tests.

**Next:** Mini-Project 7 — realistic Delta trading costs, spread, slippage, funding and GST, applied to the backtesting engine. Keep real-money trading disabled.
