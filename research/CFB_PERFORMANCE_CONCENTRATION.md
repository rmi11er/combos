# CFB performance concentration and the $50 premium filter

This audit uses the settlement-refreshed full-week point-price backtests and the separately replayed official `$50 YES-premium` runs. These are hypothetical executions against observed public trade prints. They are not an RFQ acceptance or fill-rate backtest.

The requested filter applies to **observed print quantity × YES price**, with the entire print accepted or rejected and no clipping. Public prints do not provide the parent RFQ ID or its total quantity, so this is not demonstrably a $50 cap on the original customer RFQ. Repeated small prints may belong to a larger order.

All P&L/edge comparisons below use the **same resolved-outcome cohort**. Unresolved fills and their expected edge are recorded separately. Eventual known P&L is attributed to trade time for these descriptive curves; that does not make settlement proceeds spendable earlier.

## What the cap changes

The unlimited portfolio's entry decisions are independent of capital, so its capped result equals filtering its frozen accepted prints. A constrained portfolio must be replayed: removing earlier prints changes later risk availability. Its official capped result can therefore differ materially from filtering the old fills.

| Model | Uncapped unlimited fills / P&L | Official capped unlimited fills / P&L | Official capped constrained fills / P&L |
|---|---:|---:|---:|
| Kalshi | 12,915 / −$484,947.17 | 10,184 / −$63,241.76 | 739 / −$574.81 |
| Pinnacle | 3,980 / −$34,107.11 | 3,401 / −$13,895.85 | 321 / −$614.97 |
| Blend | 1,880 / −$48,128.06 | 1,601 / −$7,143.97 | 248 / −$349.97 |
| Stronger Pinnacle | 2,702 / −$46,048.22 | 2,308 / −$9,779.65 | 274 / −$420.30 |

The cap removes substantial loss concentration but does not fix the negative result. Nor does `$50 YES premium` mean `$50 maker risk`: one accepted unlimited blend print bought 448 NO contracts at the equivalent YES price of 9.3¢. Its customer YES premium was **$41.664**, but the maker's eventual loss was **$407.6587**, including fees. The constrained run separately retains its capital and underlying risk controls.

## Why small prints can still lose overall

This dataset models the maker buying **NO**, economically equivalent to selling the customer's YES exposure. A YES settlement costs the maker its NO purchase price. Profitability depends on the dollar-weighted distribution of outcomes and prices, not just how often the combo fails.

Official capped, unconstrained runs:

| Model | Resolved prints | Profitable / losing prints | Mean profitable print | Mean losing print | Expected edge on resolved prints | Realized P&L |
|---|---:|---:|---:|---:|---:|---:|
| Kalshi | 9,899 | 5,361 / 4,538 | +$14.78 | −$31.40 | +$8,675.77 | −$63,241.76 |
| Pinnacle | 3,265 | 1,679 / 1,586 | +$14.14 | −$23.73 | +$1,573.11 | −$13,895.85 |
| Blend | 1,512 | 712 / 800 | +$12.85 | −$20.37 | +$405.83 | −$7,143.97 |
| Stronger Pinnacle | 2,192 | 1,015 / 1,177 | +$13.70 | −$20.12 | +$707.86 | −$9,779.65 |

Kalshi and Pinnacle actually have more profitable than losing prints here. Their losing prints are larger in dollars. Blend loses on both the frequency and dollar-size comparisons. The constrained blend has 111 profitable and 130 losing resolved prints, averaging +$7.40 and −$9.01 respectively.

Neither the smallest prints nor two-leg combinations escape the problem. Unlimited capped blend P&L is **−$1,971.03** on 956 prints with YES premium at most $10 and **−$5,172.95** on 645 prints between $10 and $50. Its two-, three-, and four-leg groups lose **$2,643.58**, **$2,467.04**, and **$2,033.36**. Pinnacle's corresponding leg-count groups also all lose.

## The forecast residual is economically large

For a resolved maker-NO print, the difference between realized P&L and expected point edge is exactly `quantity × (predicted YES probability − YES settlement)`. Deterministic fees cancel from this residual. This cleanly separates forecast/outcome error from fee accounting.

Official capped, unconstrained runs:

| Model | Print-weighted forecast YES / observed YES | Contract-weighted forecast YES / observed YES |
|---|---:|---:|
| Kalshi | 33.24% / 45.84% | 20.02% / 30.21% |
| Pinnacle | 34.77% / 48.58% | 24.77% / 33.30% |
| Blend | 38.45% / 52.91% | 26.84% / 37.14% |
| Stronger Pinnacle | 38.43% / 53.70% | 27.54% / 37.19% |

For constrained capped blend, these pairs are 46.12% / 53.94% and 36.26% / 43.45%. The accepted customer combinations win materially more often than their ex-ante fair forecasts predict in this particular cohort. These are conditional, repeated-print diagnostics, not estimates of unconditional venue calibration.

The blend's approximately 10.30 percentage-point contract-weighted shortfall is much larger than its roughly 0.55¢ expected net edge per resolved contract. Increasing fill count cannot by itself overcome a systematic forecast or selection error of that scale. The audit does not establish whether this is caused by stale/misaligned inputs, selection of informed customer flow, unfavorable shared game outcomes, or a combination; those mechanisms need separate checks.

Extended nonplayer markets worsen the broad Kalshi baseline but are not the sole explanation. With the cap, Kalshi's 3,014 prints containing an extended market lose **$31,935.11**; its 7,170 full-game-only prints lose **$31,306.64**. Pinnacle and blend coverage in these runs remains full-game-only, so broad Kalshi versus blended totals are not like-for-like model comparisons. The audit also exports the common-cohort runs for that comparison.

## Many fills share a small set of outcomes

For the capped unlimited portfolios:

| Model | Resolved prints | Distinct resolved combo tickers | Distinct underlying fixtures | Notional-concentration equivalent combo count |
|---|---:|---:|---:|---:|
| Kalshi | 9,899 | 8,110 | 155 | 590.2 |
| Pinnacle | 3,265 | 1,930 | 85 | 285.3 |
| Blend | 1,512 | 1,018 | 83 | 278.7 |

The final column is inverse notional HHI, `(sum quantity)^2 / sum(combo quantity^2)`. It measures concentration, **not statistical effective sample size**. Uncapped blend has 1,780 resolved prints and 1,143 combo tickers, yet a notional-concentration equivalent count of only **40.3**. The cap improves that concentration substantially.

Even different combo tickers share games. Baylor–Auburn appears in **471 of the capped blend's 1,601 prints**, representing $25,799 of payout notional. The capped Pinnacle portfolio includes that same fixture in **1,159 of 3,401 prints**, representing $68,158 of payout notional. Such incidence counts overlap across fixtures and must not be summed as independent capital or losses.

The blend's largest negative fixture allocations include Liberty–James Madison, Baylor–Auburn and Boston College–Cincinnati. Equal-leg allocations of its losses to those fixtures are approximately **$1,205**, **$931**, and **$921**. This is a transparent accounting allocation, not evidence that an individual fixture caused the loss. Full participation totals, canonical underlying buckets and combo-level losses are in `clusters.csv`.

At the trade-date level, **96.0% of capped blend prints**, **96.0% of capped Pinnacle prints**, and **97.1% of capped Kalshi prints** occur on September 5. The source archive contains a Saturday census and sampled windows on other days, so these figures describe the captured study rather than establishing the true week's daily market shares.

## What uncertainty can and cannot be inferred

For every examined portfolio, connecting fixtures that appear together in a combo produces one connected overlap component containing all resolved prints. That does **not** mean there was literally one independent sports outcome. It does mean that arbitrarily declaring combos, trades or calendar days independent produces a misleading standard error.

For illustration, capped blend's residual standard deviation would be $1,065 if every print were an independent Bernoulli trial, versus $1,795 after collapsing repeated combo tickers to a single Bernoulli outcome while still assuming different combos independent. Pinnacle's corresponding figures are $1,771 and $4,815. Both calculations omit cross-combo fixture dependence and neither is a calibrated confidence interval or significance test. No p-values or nominal Sharpe confidence intervals are supplied.

A defensible next uncertainty model should simulate one coherent result per game (including a joint score distribution when spreads/totals/period markets are involved), settle every overlapping combination from those same simulated results, and preserve the observed decision/size schedule. Its per-game probabilities must be frozen using available-at-the-time inputs. Independent slates or chronological holdouts are still needed to measure calibration and assess whether results generalize. Treating thousands of repeated prints as thousands of independent outcome tests is not a substitute.

## Reproduce and inspect

Run:

```sh
.venv/bin/python scripts/cfb_performance_concentration.py
```

Outputs are under `runs/cfb_performance_audit_20260907/concentration/`:

- `summary.csv`: resolved-cohort P&L/edge, win/loss distributions, forecast/outcome frequencies, cohort counts.
- `breakdowns.csv`: premium, leg count, full-game/extended scope, Chicago date and hour.
- `clusters.csv`: combo, fixture and canonical underlying participation and equal-leg allocations.
- `forecast_bins.csv`: predicted net-edge buckets and subsequent outcomes.
- `uncertainty_diagnostics.csv`: repetition, overlap and explicitly non-inferential dispersion comparisons.
- `manifest.json`: source hashes and interpretation constraints.

The audit verifies each resolved fill's maker-NO P&L against its quantity, price, outcome and fee, and checks that accepted decisions and fill IDs reconcile exactly. It changes no pricing, risk or reporting core code and makes no API requests.
