# Mini-Project 10 — BTC Walk-Forward Strategy Optimizer

A **new, independent, read-only Python project** in the Delta Exchange India BTCUSD learning roadmap. This app compares simple EMA/RSI strategy parameters on strictly chronological train → validation → test slices. It **does not** connect to Delta, use API keys, or place orders.

> The bundled demo candles are SYNTHETIC, generated deterministically. Demo returns are not Bitcoin returns. This is educational research software, not a trading recommendation.

## 1. Start here (Windows / PowerShell)

Extract the ZIP and open this folder in VS Code. With Python 3.11+ installed:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Open the **precomputed demo dashboard immediately**:

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard.py
```

Visit http://localhost:8501. In the sidebar, use `demo_reports` and select 1m, 5m, 15m, 1h, or 4h.

To **run your own optimization** on the included synthetic candles:

```powershell
.\.venv\Scripts\python.exe main.py optimize --source demo_data --output results --timeframes 5m
.\.venv\Scripts\python.exe main.py summary --output results --timeframe 5m
```

Point the dashboard sidebar to `results` to see newly generated results.

Run all five timeframes:

```powershell
.\.venv\Scripts\python.exe main.py optimize --source demo_data --output results --timeframes 1m 5m 15m 1h 4h
```

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## 2. The walk-forward idea

Each chronological fold uses **500 training candles**, **200 validation candles**, then **200 unseen test candles**, and rolls ahead by **200**. With 1,500 demo candles this creates four test folds.

```text
FOLD 1: [ TRAIN 0..499 ][ VALIDATE 500..699 ][ TEST 700..899 ]
FOLD 2:        [ TRAIN 200..699 ][ VALIDATE 700..899 ][ TEST 900..1099 ]
FOLD 3:                  [ TRAIN 400..899 ][ VALIDATE 900..1099 ][ TEST 1100..1299 ]
FOLD 4:                            [ TRAIN 600..1099 ][ VALIDATE 1100..1299 ][ TEST 1300..1499 ]
```

Training chooses the top 3 by `net return % + 0.5 * max drawdown %` (negative drawdown penalizes the score), subject to the minimum completed-trades requirement. Validation ranks those 3 and chooses the winner. Only then do we evaluate that strategy on the reserved test fold exactly once. Selected parameters can change each fold. **Never retune the strategy based on test results.**

Across folds, older test periods can later become training data, as would happen in real chronological deployment. No test period overlaps the next test period.

## 3. Candidate parameters and strategy

Eight combinations are evaluated:

- Fast EMA: `5` or `9`
- Slow EMA: `21` or `34`
- Minimum RSI for LONG: `50` or `55` (14-period Wilder-style RSI)
- SHORT allowed when fast EMA is below slow EMA and RSI <= `100 - minimum RSI`.

This is an **EMA trend + RSI confirmation** model, not an EMA crossover-only trigger. Signal observed at **candle close i** can only be traded at **next candle open i+1**. The study assumes 1× long/short exposure and positions may change when either filter condition changes. Each train, validation, and test segment starts flat, and any remaining position is force-closed on the last candle close of that segment. Indicators are computed causally using prior prices (including earlier-window history for proper warm-up), never future prices.

The project charges a configurable approximate round-trip trading cost for position changes. Defaults are **5 bps trading commission per transaction**, 18% GST on commission, **1 bp full bid–ask spread** (half per side) and **1 bp slippage per transaction**. These are *scenario assumptions*, not actual historical Delta fills, verified fee-tier eligibility, or historical funding. No funding or liquidations are modeled.

## 4. Connect Project 2 or Project 3's JSON history

The optimizer accepts monthly JSON like:

```text
C:\Projects\Project_02\data_real\clean\BTCUSD\5m\2026-10.json
```

It also recognizes Project 1's `candles/BTCUSD` and Project 3's `indicators/BTCUSD` layouts. For a clean Project 2 dataset:

```powershell
.\.venv\Scripts\python.exe main.py optimize --source "C:\Projects\Project_02\data_real" --output real_reports --timeframes 5m 15m 1h 4h
```

The default uses **the most recent 8,000 candles** per timeframe to keep the beginner project quick. To allow the entire available year (potentially slow and memory-heavy, especially 1m):

```powershell
.\.venv\Scripts\python.exe main.py optimize --source "C:\Projects\Project_02\data_real" --output real_reports --timeframes 1m 5m 15m 1h 4h --max-candles 0
```

The program **refuses historical gaps, duplicate timestamps, invalid OHLC, and negative volumes**, rather than pretending the market traded continuously. If your input fails this quality gate, use Mini-Project 2 to investigate and repair the input and try again. The optimizer does not fetch or clean historical exchange data itself.

Change fold lengths (all values in number of candles, not days):

```powershell
.\.venv\Scripts\python.exe main.py optimize --source demo_data --output custom_reports --timeframes 5m --train-bars 600 --validation-bars 200 --test-bars 200 --step-bars 200 --min-trades 1
```

To avoid overlapping test windows, this learning version requires `--step-bars` equal to `--test-bars`.

## 5. Main files

```text
Project_10_BTC_Walk_Forward_Optimizer/
├── main.py                   CLI: demo, optimize, summary
├── dashboard.py              Read-only Streamlit / Plotly app
├── wf_lab/
│   ├── data.py               JSON loader + strict data quality checks
│   ├── strategy.py           Causal EMA + RSI logic
│   ├── backtest.py           1× next-open execution and costs
│   ├── optimizer.py          Train/validate/test rolling-fold process
│   └── demo.py               Deterministic fake data generator
├── demo_data/                Fake candles in Project 2 layout
├── demo_reports/             Precomputed JSON optimization reports
├── tests/                    21 automated tests
├── requirements.txt
├── LEARNING_GUIDE.md
└── README.md
```

## 6. Output report

Reports go to `results/BTCUSD/{timeframe}/walk_forward.json` and include:

- An explicit list of train/validation/test UTC date ranges for every fold
- Parameter values selected for each fold
- Train, validation, and untouched test return and drawdown
- Number of trades and test win rate
- Train-to-test performance gaps
- Compounded out-of-sample equity curve
- Candidate grid, cost inputs, and simulation limitations

The dashboard displays stitched out-of-sample test equity, fold comparisons, selected parameter settings, and the original JSON. A positive synthetic result says nothing about a live strategy edge.

## 7. Important limitations and safety

- No broker connection, orders, API secrets, real funds, or real-time execution.
- Synthetic demo data deliberately has market regimes; it is not a performance sample of Bitcoin.
- **No funding**, liquidation, contract-size rounding, margin accounting, order-book depth, delays, rejected orders, or real maker/taker fill determination.
- Default 1× returns are in a simplified USD-equivalent equity model, not your Delta India INR ledger.
- Default short train/validation/test periods, especially on 1m/5m, have poor statistical power. For credible real-data analysis, choose substantially longer periods and hold out a truly untouched final period, including multiple market regimes.
- Repeatedly changing the model after seeing the out-of-sample report makes the so-called test data part of optimization. Preserve a never-used final holdout for later research.
- Signals can change based on RSI fluctuations; this is a simple educational example, not a validated BTC strategy.

**Next:** Project 11 — Delta Exchange REST client (read-only public data first).
