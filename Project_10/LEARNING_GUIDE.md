# Learning Guide — Walk-Forward Testing (Mini-Project 10)

## What problem does this solve?

A strategy can appear excellent on the market data used to tune it, yet fail later. Walk-forward testing simulates a time-ordered loop: fit on old observations, optionally choose parameters using slightly newer data, then evaluate those frozen parameters on data that was not used in either choice.

## Basic example

Imagine 900 consecutive 5m candles:

- 500 training bars: compare EMA(5/21) and EMA(9/34), both with RSI rules.
- 200 validation bars: choose the training shortlist winner using newer but still pre-test data.
- 200 test bars: freeze parameters and compute actual simulated results.

The next fold moves the boundaries forward. Each fold gives a newly unseen test segment. The code uses test segments without overlap.

## Parameters optimized

Fast EMA ∈ {5,9}, slow EMA ∈ {21,34}, RSI threshold ∈ {50,55}: 8 distinct parameter combinations.

EMA fast > EMA slow AND RSI > threshold ⇒ target LONG. EMA fast < EMA slow AND RSI < (100-threshold) ⇒ target SHORT; otherwise target FLAT. Strict inequalities are implemented using >= and <= for RSI. These values update at candle CLOSE. Every desired exposure changes at the following candle OPEN (never at the same close). This is a trend-confirmation system.

## Why the test set must be untouched

If you examine a losing test result and adjust the EMA or RSI grid specifically to make that same test period profitable, you have fitted the test data. Subsequent good results from that period are not independent evidence. Use one final never-seen period for a serious study.

## Example train vs test interpretation

| Fold | Training return | Validation return | Test return | Meaning |
|---|---:|---:|---:|---|
| A | +8% | +3% | −4% | Likely poor generalization |
| B | +2% | +1% | +0.5% | Small, uncertain positive result |
| C | +10% | −2% | −7% | Sensitivity to market regime |

These numbers are imaginary and do not represent an actual result from the application.

## Metrics explained

- Net return: ending capital / starting capital − 1, after modeled fees and estimated spreads/slippage.
- Maximum drawdown: worst percentage decline from an earlier equity peak.
- Win rate: fraction of completed positions with positive net trade PnL.
- Generalization gap: training net return − test net return, both measured on different-length periods. Because window lengths differ, this comparison is only a rough diagnostic, not a formal statistical test.
- Stitched test equity: compounds sequential unseen test segments, excluding train and validation returns.

## One significant caveat

The project uses a simplified single-asset 1× equity model, with fixed transaction costs. It does not include futures margin, actual Delta contract multipliers, historical funding, liquidation, order rejections, partial fills or exchange-specific settlement. Do not turn its backtested signals into live trading orders.

## Practice exercises

1. Compare the same parameters over 1h and 4h candle series.
2. Set `--fee-bps 10` then see if the selected strategy changes.
3. Turn on `--mode long_only` and study positive/negative folds.
4. Compare `--min-trades 1` against `--min-trades 3`; note skipped folds.
5. Analyze a cleaned, independently downloaded BTC dataset (not the bundled synthetic one).
