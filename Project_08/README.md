# Mini-Project 8 — BTC Event-Driven Backtesting Engine

**Standalone beginner-friendly Python project · Delta Exchange India BTCUSD · Historical simulation only**

This app is a **new independent project**. It runs without Projects 1–7 and does **not** connect to Delta, request API keys, send real trades, or place testnet orders. The package includes self-contained, clearly labeled **synthetic** example candles and signals for `1m`, `5m`, `15m`, `1h`, `4h`.

## What you build

A small event-driven backtester that simulates a trading system one historical candle at a time:

```text
Historical candle opens
   └─ Execute previous candle's pending MARKET order at the new candle OPEN
      ├─ Validate exposure, available equity, and per-bar fill capacity
      ├─ Fill all / part of the order, or reject it
      ├─ Apply adverse spread + slippage assumptions, trading fees, and GST
      └─ Update the signed position, cash, and trade log
Historical candle closes
   ├─ Mark open positions to closing price → equity snapshot
   ├─ Read a BUY / SELL / HOLD signal (from Project 4 or bundled demo)
   └─ Queue an order for the NEXT continuous candle open

             Results saved as JSON → Streamlit dashboard
```

**A completed candle is essential:** a BUY after a 10:00–10:05 candle is first eligible to fill **at the 10:05 opening price of the following candle**, not at the signal candle's 10:00 open or a guessed price in its high/low.

### Included features

- Event log with `MARKET_OPEN`, `MARKET_CLOSE`, `SIGNAL`, `ORDER`, `FILL`, `ORDER_REJECT`, `DATA_GAP`, `ORDER_CANCEL`.
- Long-only and long/short trading. SELL **closes a long or opens a short** if flat and shorts are enabled; BUY closes a short or opens a long. **No instant reverse**: an opposite signal closes the current position; another signal is needed to open a reverse position.
- Simulated **market** orders; next-candle-open execution with configurable adverse half-spread and slippage. Does not simulate limit, stop-loss, or take-profit orders.
- Quantity uses **integer BTCUSD contracts**, configurable BTC-per-contract, basic notional/equity leverage cap, optional partial fills per bar.
- Trading fees with optional 18% GST; realized and unrealized PnL, open position, fee costs, equity and drawdown, closed-trade fills, win rate.
- Cancels queued orders when a candle gap is detected instead of inventing a fill; any existing position remains exposed to the market.
- Open positions remain open at the end of historical data (marked to close); unfilled last-bar orders stay pending.
- Read-only Streamlit + Plotly dashboard. JSON orders, fills, trades, events, and equity outputs.
- Loads Project 2/3 candles and Project 4 signal JSON without installing those projects.

## 1. Setup on Windows (VS Code + PowerShell)

Unzip this project and open the folder in VS Code.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 2. Run the first historical backtest

```powershell
.\.venv\Scripts\python.exe main.py run --candles demo_data --signals demo_data --output results --timeframes 5m
```

Output is saved under `results/BTCUSD/5m/`. The source demo data is synthetic and signals are artificially preset, **not the EMA/RSI strategy**, so demonstration returns have zero predictive value.

Run all five timeframes:

```powershell
.\.venv\Scripts\python.exe main.py run --candles demo_data --signals demo_data --output results --timeframes 1m 5m 15m 1h 4h
```

Print the report:

```powershell
.\.venv\Scripts\python.exe main.py summary --output results --timeframe 5m
```

## 3. View the Streamlit dashboard

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard.py
```

Open `http://localhost:8501`. In the sidebar, choose `demo_results` (already bundled), or choose `results` to view the backtests you just ran. You can switch among all five timeframes.

The dashboard offers:
- **Performance:** equity curve, drawdown, metrics.
- **Candles & Fills:** candlesticks with actual simulated order fill markers.
- **Orders & Trades:** all order statuses, individual fills, realized trade records, JSON export.
- **Event Timeline:** chronological event viewer with event-type filtering.
- **Assumptions & Learning:** the simulation assumptions and an explanation of event order.

The dashboard **only reads saved JSON**. It does not start or change a backtest and never places orders.

## 4. Use real Bitcoin history from previous projects

**Option A: Project 2 candles + Project 4 signals**

```powershell
.\.venv\Scripts\python.exe main.py run --candles "C:\path\to\Project_02\data_real" --signals "C:\path\to\Project_04\data_real" --output real_results --timeframes 5m --max-candles 3000
```

**Option B: Project 3 indicator JSON + Project 4 signal JSON**

```powershell
.\.venv\Scripts\python.exe main.py run --candles "C:\path\to\Project_03\data_real" --signals "C:\path\to\Project_04\data_real" --output real_results --timeframes 1m 5m 15m 1h 4h --max-candles 3000
```

Root folders should contain the following layouts (not necessarily both in one place):

```text
Project_02/data_real/clean/BTCUSD/5m/YYYY-MM.json
Project_03/data_real/indicators/BTCUSD/5m/YYYY-MM.json
Project_04/data_real/signals/BTCUSD/5m/YYYY-MM.json
```

Each candle has `timestamp_utc`, `open`, `high`, `low`, `close`, `volume`. Project 4 signals have `timestamp_utc`, `decision_time_utc`, `signal` and optionally `reason`, `gap_before`. `decision_time_utc`, when present, must equal the candle's end. Signal timestamps are matched to candle **start** times.

The inputs are read-only. Project 2/3/4 files are never modified.

**Large 1-year histories:** `--max-candles 3000` is the default for learning and browser responsiveness. Set `--max-candles 0` to run all available candles, but one-year 1m history produces **over one million event records**, so both memory and saved JSON size can grow considerably. Start with `5m` and small windows. The next backtesting enhancements can add event-log streaming and incremental aggregation.

## 5. Experiment with execution costs and partial fills

```powershell
.\.venv\Scripts\python.exe main.py run --candles demo_data --signals demo_data --output custom_results --timeframes 5m --mode long_short --capital 10000 --contracts 8 --contract-btc 0.001 --fee-bps 5 --gst-pct 18 --spread-bps 2 --slippage-bps 1 --max-fill-contracts 3 --max-leverage 2
```

This example requests eight contracts but fills at most three contracts per candle open. You can explore an `ORDER` followed by multiple `FILL` events in the timeline. When closing a partially filled entry, a trade is logged for each exit fill.

Fee assumptions (verify against your actual exchange settings): BTCUSD **lot size 0.001 BTC**, standard taker **0.05% = 5 bps**, maker **0.02% = 2 bps**. GST of **18% is applied to the trading fee**, not the entire position. Fee and settlement details may change. References: [Delta fees](https://www.delta.exchange/fees), [BTCUSD specs](https://www.delta.exchange/contracts).

### Simplified formulas

```text
quantity_btc = filled_contracts × contract_btc
fill_buy_price  = next_open × (1 + (half_spread_bps + slippage_bps) / 10000)
fill_sell_price = next_open × (1 - (half_spread_bps + slippage_bps) / 10000)
fee_incl_GST = filled_contracts × contract_btc × fill_price × fee_bps / 10000 × (1 + GST_pct / 100)
long_gross_PnL = contracts × contract_btc × (sell_fill_price - avg_buy_fill_price)
short_gross_PnL = contracts × contract_btc × (avg_sell_fill_price - buy_fill_price)
equity = cash + unrealized_PnL
```

**Cost caution:** spread and slippage are reflected in *adversely adjusted fill prices*; they should NOT also be deducted a second time. Fees are debited at each fill. Trade-level entry fees are allocated to each exit fill for accurate net trade records.

**Leverage caution:** the `max_leverage` parameter is **only a notional/equity admission cap**, not a real Delta margin model. This app intentionally does not simulate margin calls, liquidation, portfolio margin, real stop orders, mark-price PnL, or funding settlements. Delta India settles in INR, while this teaching app keeps an **USD-equivalent illustrative ledger**. Do not treat its balances as actual exchange balances.

## 6. Project directory

```text
Project_08_BTC_Event_Driven_Backtesting_Engine/
├── main.py                      # CLI: demo, run, summary
├── dashboard.py                 # Read-only Streamlit dashboard
├── event_lab/
│   ├── __init__.py
│   ├── data.py                  # Project 2/3/4 JSON loading and validation
│   ├── engine.py                # Chronological event simulation, fees, positions
│   └── demo.py                  # Deterministic synthetic candle/signal generator
├── demo_data/                  # 5 timeframes: synthetic candles and signals
├── demo_results/               # 5 timeframes: precomputed result JSON
├── tests/
│   └── test_engine.py
├── requirements.txt
├── .gitignore
└── README.md
```

### Saved results

```text
results/BTCUSD/5m/
├── summary.json
├── candles.json
├── orders.json
├── fills.json
├── trades.json
├── events.json
└── equity.json
```

These files make a good input for Project 9 — Performance Analyzer.

## 7. Run tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests cover timing/look-ahead, long and short, fees, price impact, leverage gate, partial fills, data gaps, OHLC quality, Project 4 signal timestamps, and cash/equity accounting.

## 8. Checklist before Mini-Project 9

- [ ] I can run `demo` and `run` without connecting to the broker.
- [ ] I understand why signals fill on the *next candle*, not the same one.
- [ ] I can read `events.json` and trace `SIGNAL` → `ORDER` → `FILL`.
- [ ] I understand `cash`, `unrealized PnL`, `equity`, and net trade PnL.
- [ ] I can show a partial fill and a gap cancellation.
- [ ] I can load Project 4 signals and Project 2/3 candles.
- [ ] I can launch the dashboard on my own machine.
- [ ] All automated tests pass.

**Next:** Mini-Project 9 — Performance Analyzer (Sharpe, Sortino, profit factor, expectancy, drawdown, and trade reports).
