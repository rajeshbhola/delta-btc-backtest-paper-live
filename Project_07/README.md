# Mini-Project 7 — BTC Trading Fee, Slippage & Funding Simulator

> **Standalone beginner-friendly Python project.** Works without Projects 1–6, Delta API keys, internet access, or a trading account. All included trade examples are **synthetic**. Read-only simulation: this application **never places orders**.

## 1. Goal

Understand how a profitable-looking BTC futures trade can become a worse trade (or a loss) after exchange commission, 18% GST on commission, bid–ask spread, adverse fills, and perpetual funding. You get:

- An **interactive Streamlit dashboard**: edit prices, trade side, contracts, maker/taker type, costs, funding, leverage, illustrative USD/INR conversion.
- A **single-trade CLI calculator** with JSON export.
- A **multi-trade cost comparison** with gross and net equity lines, import from Project 6's `trades/BTCUSD_<timeframe>.json`.
- **14 self-contained synthetic demo trades**, plus saved demo results and tests.

## 2. Directory layout

```text
Project_07_BTC_Trading_Cost_Simulator/
├── main.py                      # Run demo, single trade, batch trade comparison
├── dashboard.py                 # Browser UI (Streamlit + Plotly)
├── cost_lab/
│   ├── model.py                 # Contract sizes, fills, costs, funding formulas
│   ├── portfolio.py             # Process historical completed trades
│   ├── files.py                 # JSON persistence
│   └── demo.py                  # Generate synthetic trade examples
├── demo_data/trades.json        # Synthetic input trades
├── demo_results/batch_results.json
├── tests/
├── requirements.txt
└── README.md
```

## 3. Run on Windows (PowerShell)

**Step 1** — Extract ZIP and open the extracted directory in VS Code.

**Step 2** — Create an environment and install dependencies:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**Step 3** — Launch the standalone dashboard:

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard.py
```

Open http://localhost:8501 in your browser. The dashboard includes example trades and does not need any broker credentials.

**Step 4** — Calculate a single LONG trade:

```powershell
.\.venv\Scripts\python.exe main.py single --side LONG --entry 100000 --exit 101000 --contracts 10 --output results/single_trade.json
```

A SHORT example (with a single assumed funding snapshot):

```powershell
.\.venv\Scripts\python.exe main.py single --side SHORT --entry 101000 --exit 100000 --contracts 10 --funding-events 1 --output results/short_trade.json
```

**Step 5** — Analyze the bundled example trades and write a JSON result:

```powershell
.\.venv\Scripts\python.exe main.py batch --trades demo_data/trades.json --output results/demo_comparison.json
```

**Step 6** — Verify the project:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## 4. Connect to the previous Project 6 (optional)

Project 6 exports a JSON trade history in its `demo_results/trades/` or `results/trades/` directory.

**Load the Project 6 `results` folder (5m):**

```powershell
.\.venv\Scripts\python.exe main.py batch --trades "C:\path\to\Project_06_BTC_Vectorized_Backtesting_Engine\demo_results" --timeframe 5m --contracts 10 --output results/project6_5m_costs.json
```

Other options: `--timeframe 1m`, `5m`, `15m`, `1h`, `4h`; `--sizing one_x`; `--entry-order maker`; `--exit-order taker`; `--spread-bps 3`; `--slippage-bps 2`; `--funding-rate-pct -0.01`; `--usd-inr 86.0`; `--leverage 3`.

**IMPORTANT:** Project 6's model rebalances notional exposure on every bar and has no fixed integer contract count. Project 7 reconstructs **completed-trade price scenarios** with your specified contract quantity (or one-times account-equity lot sizing). The two equity curves therefore **will not exactly match**, even with fees turned off. Project 7 is a **cost-sensitivity study**, not a replacement for rerunning Project 6's strategy engine. Full per-bar cost integration is planned for later projects.

## 5. Understand the math (worked synthetic example)

Imagine a LONG position:

- Entry price (reference midpoint): **$100,000 / BTC**
- Exit price (reference midpoint): **$101,000 / BTC**
- **10 contracts** × 0.001 BTC = **0.01 BTC**
- Entry and exit both taker, fee **0.05% on each side**
- GST **18% on commission only**
- Quoted FULL spread: **2 bps** (1 bps adverse on entry; 1 bps adverse on exit)
- Slippage: **1 bp adverse per side** (2 bps total for entry + exit)
- No funding snapshot (0)

Baseline PnL without costs: `(101000 - 100000) × 0.01 BTC = $10`.

Modeled entry price = `$100,000 × (1 + 0.0001 + 0.0001) = $100,020`.

Modeled exit price = `$101,000 × (1 - 0.0001 - 0.0001) = $100,979.80`.

Executed-price PnL = `(100979.80 - 100020) × 0.01 BTC = $9.598`.

Commission: `($100020 × 0.01 × 0.0005) + ($100979.80 × 0.01 × 0.0005)` = about `$1.005`.

GST: `commission × 0.18` ≈ `$0.181`.

**Net PnL ≈ $8.41**. (Exact floating result in JSON.)

The **spread and slippage adjust fill prices**; they are NOT deducted a second time. The resulting breakdown:

```text
Reference gross PnL
  - Spread impact
  - Slippage impact
  - Entry + exit commissions
  - GST on commissions
  - Funding paid (or + funding received)
= Estimated net PnL
```

### Funding sign and scheduling

- **Positive funding:** LONG pays, SHORT receives (assuming the snapshot applies).
- **Negative funding:** LONG receives, SHORT pays.
- Model estimates `funding = sign × entry reference notional × assumed signed funding rate × #snapshots`.
- The **default 0.01% funding is a scenario assumption, not a live or historical BTCUSD funding rate.** Change it to inspect other cases.
- BTCUSD currently documents funding at **00:00, 08:00, 16:00 UTC** (05:30, 13:30, 21:30 IST); verify the current contract schedule. When importing Project 6's timestamps, the app counts only snapshots **strictly between** entry and exit, excluding exact-edge times due to execution uncertainty. Real rates and snapshot mark prices vary.

## 6. USD and INR distinction

BTCUSD prices and the example PnL are in USD-*equivalent* terms, but Delta India settles/margins in **INR**. `--usd-inr 85` is a **manual input for illustrative conversion**; this project does **not** fetch real exchange conversion rates, implement broker-specific settlement conversion, or estimate income tax. Do not compare its assumed INR directly to an exchange statement.

### Margin vs PnL

Approx margin = USD reference notional ÷ assumed leverage. Real initial/maintenance margin, reserves, fees, liquidation, and platform risk rules are **not modeled**. Higher leverage by itself does not multiply PnL when the **contract quantity stays fixed**. Never use the margin estimate to decide whether to place a trade.

## 7. Maker orders and spread note

Maker/taker types and hypothetical fill prices are **independent assumptions** in this learning tool. A limit order may not fill at all; a marketable limit order may be a taker. The model always assumes full entry and exit fills. Spread/slippage should be calibrated from order-book/fill data before realistic backtesting. Actual futures fee notional may reference exchange-defined index/spot price, rather than the synthetic modeled fill price; the project uses synthetic execution notional for a transparent approximation.

## 8. Test cases and limits

Tests cover fee calculation, GST, long/short directions, spread and slippage without double charging, positive/negative funding, boundary counts, leverage margin-vs-PnL, input rejection, gross-net reconciliation, CLI output and Project 6 trade-file structure.

**Not included:** exchange API connectivity, actual funding-history downloads, order book data, fill probability, partial fills, tax advice, liquidation, real-time rates/FX, market-impact models, strategy backtesting itself, or order execution. Everything is hypothetical.

## 9. Official source links

- [Delta Exchange India fee schedule](https://www.delta.exchange/fees)
- [Delta BTCUSD contract details](https://www.delta.exchange/en/contracts)
- [Funding settlement schedule (India)](https://www.delta.exchange/support/solutions?articleId=80001183756)
- [Notional-based fee explanation](https://www.delta.exchange/support/solutions?articleId=80001177864)

## 10. What comes next?

**Mini-Project 8 — Event-Driven Backtesting Engine**, a separate application with candle/order/fill events and position tracking. The future full backtester can reuse the transparent cost calculations developed here.
