# Mini-Project 9 — BTC Strategy Performance Analyzer

**Standalone, beginner-friendly Python + JSON + Streamlit application**  
BTCUSD futures · Delta Exchange India learning roadmap · Phase 2 (Backtesting) · Educational simulation only

## Goal

Turn an event-driven backtest's **equity snapshots and closed-trade records** into a trustworthy performance report. Calculate return, max drawdown, Sharpe, Sortino, profit factor, win rate and expectancy, then explore results in a local Streamlit dashboard.

This project **does not connect to Delta Exchange**, does not use API keys, and cannot place orders. Everything runs offline. The bundled Project 8 example data is **SYNTHETIC**.

## Features

- Completely standalone: its own Python source, included sample Project 8 JSON, precomputed analyzed reports, tests and dashboard.
- Reads Project 8's exact output format: `results/BTCUSD/<timeframe>/summary.json`, `equity.json`, `trades.json`.
- Supports **1m, 5m, 15m, 1h, 4h** timeframes.
- Financial metrics from the full equity curve: total return, USD equity change, max/latest drawdown, longest underwater time, optional CAGR/Calmar, Sharpe, Sortino, equity exposure snapshots and a simple gross BTC buy-and-hold comparison.
- Closed-trade metrics: profit factor, expectancy, win rate, average win/loss, payoff ratio, median PnL, best/worst trade, losing streak, holding duration and costs recorded per closed trade.
- Data-quality notes for duplicate timestamps, invalid values, irregular intervals and trade/equity reconciliation differences.
- JSON reports only: no CSV/Parquet/database needed.
- Read-only Streamlit dashboard: charts, tabs, filters, JSON download and learning guide.

## Folder structure

```text
Project_09_BTC_Strategy_Performance_Analyzer/
├── main.py                       # Analyze, summarize, compare CLI
├── dashboard.py                  # Interactive, read-only Streamlit UI
├── performance_lab/
│   ├── __init__.py
│   ├── metrics.py                 # Pure Python metric calculations
│   └── files.py                   # JSON input/output
├── demo_project8/                # Bundled SYNTHETIC Project 8 inputs
│   └── BTCUSD/{1m,5m,15m,1h,4h}/
│       ├── summary.json
│       ├── equity.json
│       └── trades.json
├── demo_reports/                 # Precomputed dashboard example results
│   └── BTCUSD/{1m,5m,15m,1h,4h}/
│       ├── metrics.json
│       ├── equity_analysis.json
│       ├── closed_trades.json
│       └── monthly_returns.json
├── tests/
│   └── test_metrics.py
├── requirements.txt
├── LEARNING_GUIDE.md
└── README.md
```

## Step 1 — Install (Windows PowerShell)

Extract the ZIP. Open the extracted project folder using VS Code, then:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Python 3.11 or later is recommended. No Delta Exchange credentials are needed.

## Step 2 — Open the dashboard immediately

The bundled `demo_reports` folder already contains calculations, so you can start the dashboard before running your own analysis.

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard.py
```

Open **http://localhost:8501**. Select a timeframe in the sidebar. The sample data is synthetic and provided only for learning.

## Step 3 — Run your first analysis

In a different terminal or after stopping Streamlit:

```powershell
.\.venv\Scripts\python.exe main.py analyze --input demo_project8 --output reports --timeframes 5m
```

The command reads the bundled Project 8 equity and trades, calculates metrics, and writes four JSON files under `reports/BTCUSD/5m/`. Select **My own reports** and `reports` in the dashboard sidebar.

Analyze all five timeframes:

```powershell
.\.venv\Scripts\python.exe main.py analyze --input demo_project8 --output reports --timeframes 1m 5m 15m 1h 4h
```

Print detailed 5-minute metrics:

```powershell
.\.venv\Scripts\python.exe main.py summary --output reports --timeframe 5m
```

Compare timeframes:

```powershell
.\.venv\Scripts\python.exe main.py compare --output reports
```

Optional annual risk-free rate (decimal):

```powershell
.\.venv\Scripts\python.exe main.py analyze --input demo_project8 --output reports --timeframes 5m --risk-free-annual 0.05
```

That is an illustrative **5% annual** risk-free assumption, NOT a Delta funding rate.

## Step 4 — Import real historical *backtest results* from Project 8

After running Mini-Project 8 on your historical BTC data, point Project 9 to the **Project 8 results root**:

```powershell
.\.venv\Scripts\python.exe main.py analyze --input "C:\path\to\Project_08\real_results" --output real_reports --timeframes 1m 5m 15m 1h 4h
```

To view these reports, start Streamlit and choose **My own reports**, setting the folder to `real_reports`.

Project 9 does **not** accept raw market OHLCV or Project 4 signal files: it needs actual Project 8 **backtest results** (`equity.json` and `trades.json`). `summary.json` is optional.

**Best practice:** Backtest all timeframes over aligned date ranges using the same assumptions. In Project 8, `--max-candles 0` can request full available history, subject to memory constraints. Several days of backtest results are insufficient to establish long-run performance.

## Step 5 — Run automated tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The tests verify metric formulas, trade classifications, gaps, invalid rows, month boundaries, JSON output, and integration with Project 8 demo data.

## How calculations work

| Metric | Rule |
|---|---|
| Total return | `(last_equity / first_equity - 1) * 100` |
| Maximum drawdown | Largest percentage decline from the preceding equity peak |
| Win rate | `winning_closed_trades / all_closed_trades * 100`, including breakevens in denominator |
| Profit factor | `sum(positive net trade PnL) / abs(sum(negative net trade PnL))`; undefined if there are no losing trades |
| Expectancy | `mean(net closed-trade PnL)` in simulation USD-equivalent |
| Sharpe | Annualized mean *excess per-candle return* divided by sample return standard deviation |
| Sortino | Annualized mean excess per-candle return divided by downside deviation |
| Calmar | `CAGR (%) / abs(max_drawdown_pct)`; only when CAGR exists and drawdown is nonzero |

Crypto trades 24/7, so annualization uses 365 days per year. Only **contiguous, precisely spaced equity snapshots** contribute to Sharpe and Sortino. The full observed curve is still used for total return and drawdown.

Undefined ratios are stored as JSON `null` and shown as **N/A**, not as fabricated zeros. CAGR and Calmar are withheld for histories shorter than 30 days. Sharpe and Sortino are technically displayed when estimable even for short samples, but such annualized ratios are unreliable and the app flags them.

## Important limitations

1. **Do not trade based on demo statistics.** All included prices and trades are from synthetic historical simulations.
2. The underlying Mini-Project 8 backtester uses simplified fills, fees, exposure and margin logic; it does **not** fully model Delta funding, liquidation, margin modes or INR settlement. Project 9 cannot repair missing realism in those inputs.
3. `profit_factor`, win rate, and trade expectancy are calculated from **completed trade records** only. Open positions affect equity, but are not treated as closed trades.
4. Closed-trade PnL and total equity change can differ because of open position value, other cash flows, entry fees on open positions, and other accounting effects. A warning flags a mismatch rather than forcing reconciliation.
5. The benchmark is a **zero-cost BTC buy-and-hold comparison**, not a modeled perpetual futures execution.
6. Market gaps are **not** interpolated. Ratios exclude discontinuous return observations; equity/drawdown still use available mark-to-market snapshots.
7. Source currency is USD-equivalent as used in Project 8, not a genuine Delta India INR settlement ledger.
8. Sharpe/Sortino can become misleadingly extreme for tiny or highly correlated samples. Prefer long, out-of-sample evaluation across regimes.
9. Data is read-only, so no API keys, broker login or live/testnet orders are involved.

## Learning progression

Projects 1–5: data and signal generation → Project 6: vectorized backtest → Project 7: cost estimates → Project 8: event-driven backtest → **Project 9: performance evaluation** → Project 10: walk-forward testing and overfitting prevention.
