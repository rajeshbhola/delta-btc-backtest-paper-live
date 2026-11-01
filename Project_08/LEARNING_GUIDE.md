# Beginner Walkthrough: How an Event-Driven Backtest Works

## A four-candle example

Imagine 5-minute BTCUSD candles and an already-calculated BUY signal:

| Candle opens (UTC) | Open | Close | Signal at candle close |
|---|---:|---:|---|
| 10:00 | $100,000 | $100,050 | BUY at 10:05 |
| 10:05 | $100,060 | $100,100 | HOLD at 10:10 |
| 10:10 | $100,110 | $100,140 | SELL at 10:15 |
| 10:15 | $100,130 | $100,090 | HOLD at 10:20 |

Assume 5 BTCUSD contracts, each representing 0.001 BTC, no transaction costs for teaching.

**At 10:05:** The BUY order created from the previous candle is filled at **$100,060**, not $100,050 (which was the signal candle close) or $100,000 (which happened before the signal was known).

**At 10:15:** The SELL signal generated after the 10:10 candle closes is executed as a **long-position exit** at the 10:15 candle's opening price **$100,130**.

```text
Position exposure = 5 contracts × 0.001 BTC = 0.005 BTC
Gross PnL = (100130 − 100060) × 0.005 = $0.35
```

In the actual demo, fees and price impact reduce net PnL; those are separately configurable. For this reason, the dashboard shows the **actual simulated fill price**, not just the signal's reference candle price.

## Event log

Look for these records in `results/BTCUSD/5m/events.json`:

```text
MARKET_CLOSE (10:05) → SIGNAL BUY (10:05) → ORDER OPEN_LONG (10:05)
MARKET_OPEN (10:05) → FILL OPEN_LONG (10:05) → ...
MARKET_CLOSE (10:15) → SIGNAL SELL (10:15) → ORDER CLOSE_LONG (10:15)
MARKET_OPEN (10:15) → FILL CLOSE_LONG (10:15) → ...
```

The 10:05 close event and 10:05 next-open event share a UTC timestamp but **occur in the correct logical order**, as the previous candle must finish before the new one opens. In the exported events, the previous bar's `MARKET_CLOSE` precedes the following bar's `MARKET_OPEN`.

## Why Project 8 differs from Project 6

- **Project 6, vectorized:** many operations are applied to entire pandas arrays. Simple and fast, but certain order-level behaviors are difficult to represent precisely.
- **Project 8, event-driven:** a loop processes one historical candle at a time and emits `SIGNAL`, `ORDER`, `FILL`, and portfolio events. You can inspect why an order filled, partially filled, was rejected, or was cancelled.

**It is a historical simulator, not live execution.** There are no API credentials or Delta private endpoints in this project.

## Notes on the simulation's limitations

There is no intrabar stop/limit fill simulation, real order-book queue modeling, liquidation, funding payments, Delta INR ledger, or broker execution. The maximum leverage parameter is a simple gate rather than a margin engine. Never use Project 8 alone to justify live trading.
