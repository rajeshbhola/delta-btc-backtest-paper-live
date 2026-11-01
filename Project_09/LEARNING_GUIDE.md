# Project 9 — Beginner Learning Guide

## Why build this project?

Project 8 produced a log of simulated trades. That alone cannot tell you whether the strategy is good. A profit may hide a huge drawdown; a high win rate may hide large losing trades. Project 9 measures both **return** and **risk** using the *equity curve* and the *closed trade log*.

## Step 1: Total return

If equity starts at $10,000 and ends at $10,500:

`(10,500 / 10,000 - 1) × 100 = +5%`.

This is a period return, *not* an annual return.

## Step 2: Drawdown

Imagine equity goes $10,000 → $11,000 → $9,900 → $10,400.

At the third observation the decline from the $11,000 peak is:

`(9,900 / 11,000 - 1) × 100 = -10%`.

Maximum drawdown is at least 10%; a strategy's average return does not reveal this risk.

## Step 3: Win rate, profit factor and expectancy

Suppose 5 closed trades have net PnL: `+$30, +$20, -$10, -$15, -$5`.

- Win rate: `2 / 5 = 40%`.
- Gross winning PnL: `$50`.
- Absolute losing PnL: `$30`.
- Profit factor: `50 / 30 = 1.67`.
- Expectancy: `(30 + 20 - 10 - 15 - 5) / 5 = +$4 per trade`.

A **40% win rate** could still produce positive expectancy. Conversely, a 70% win rate can lose money if average losses are much larger than average wins.

## Step 4: Sharpe and Sortino

Both use **returns of the portfolio**, not profits from individual trades.

- Sharpe measures mean return above an assumed risk-free return divided by *total* return volatility.
- Sortino focuses only on volatility **below** the risk-free target.

This app uses candle-to-candle portfolio equity values, skips returns spanning missing time intervals, and annualizes based on timeframe under a 24/7 crypto-year assumption. Such statistics are unstable with a few trades, extremely short histories, or strongly autocorrelated returns. If the denominator is zero, the metric is N/A.

## Step 5: Equity curve versus trade log

A position can have a floating loss even while no trade has closed. Therefore:

- **Equity metrics** come from `equity.json`, including open unrealized value.
- **Trade metrics** come from `trades.json`, containing closed trades only.
- If these disagree, investigate rather than editing one to match the other.

## Step 6: What to study in the dashboard

1. **Equity & drawdown:** Is the curve smooth? Is the worst drawdown survivable?
2. **Trade analysis:** Are results driven by one exceptional trade? Does the loss tail dominate?
3. **Monthly returns:** Are gains concentrated in a single month, or persistent across regimes?
4. **Compare timeframes:** Use identical dates and assumptions or the comparison is unfair.
5. **Learning guide:** Read assumptions; performance is only as trustworthy as the original simulation.

## Completion exercises

- Run the 5m demo and explain why closed trade net PnL can equal or differ from equity change.
- Analyze every timeframe. Examine how annualization changes Sharpe on different timeframes.
- Remove all negative trade records in a *copy* of `trades.json`: confirm profit factor becomes N/A, not infinity disguised as a good score.
- Change `--risk-free-annual` from `0` to `0.05` and see how risk-adjusted ratios change.
- Import your own Project 8 results, inspect gap warnings, and explain every surprising statistic.

**Ready for Project 10?** You should be able to explain *how* each metric was calculated, which input JSON generated it, and why good in-sample statistics alone do not justify live trades.
