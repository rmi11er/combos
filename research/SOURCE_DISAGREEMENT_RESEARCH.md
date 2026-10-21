# Source disagreement research log — September 7, 2026

## Hypothesis and status

The user's observation from the MLB unlimited equity plot motivates testing whether Polymarket provides incremental information when it disagrees with Kalshi. Lower transaction costs and differences in participant access are proposed explanations, not established causes of sharper forecasts or deeper liquidity. Actual spread, depth, fees and timestamps must be measured by market. Historical missing-depth assumptions cannot establish superior liquidity.

Status: **exploratory, mixed evidence on one complete day; no production weighting change**. September 5 outcomes and the present report have already been inspected. They cannot serve as an untouched validation set. This audit uses exchange-only combo probabilities; Pinnacle MLB history remains unavailable under the current API access response. It neither validates a three-source fair nor attributes losses to the 30-second Pinnacle delay.

## First paired historical check

The common September 5 cohort has 21,880 public YES-taker prints, 7,105 distinct combos and 46 underlying fixture identities, including future fixtures. Outcomes are known for 21,774 prints. All are 2–4-leg, distinct-game, full-game pregame candidates under the existing schedule and publication conventions. Unknown outcomes are excluded from realized P&L and scoring, with loose final P&L bounds retained in the machine-readable report.

| Unlimited price selection | Prints | Known net seller P&L | P&L / known cumulative NO cash including fees |
|---|---:|---:|---:|
| Both models | 360 | $22,311.38 | 16.17% |
| Kalshi only | 395 | $17,369.34 | 17.74% |
| Polymarket only | 1,823 | $13,391.67 | 3.87% |
| Neither | 19,302 | $366,456.55 | 9.09% |

The exposure ratio uses only resolved trades in both numerator and denominator. It is a cumulative exposure diagnostic, not a $10,000 portfolio return or an independent estimate of repeatable edge. Selection groups differ in prices, fixtures, sizes and probabilities. Larger aggregate profits from rejected prints do not establish better selection efficiency.

Both forecasts are scored against exactly the same known combo outcomes using Brier score, mean squared probability error; smaller is better:

| Weighting | Kalshi | Polymarket |
|---|---:|---:|
| Equal print | 0.118358 | 0.118524 |
| Contract quantity | 0.098515 | 0.098410 |

The quantity-weighted PM-minus-Kalshi score difference is −0.0001046, slightly favoring PM. Removing all combos containing each individual fixture produces differences ranging from −0.0002276 to +0.0000816; PM is better in 44 of 46 overlapping removals. These removals are sensitivity checks, not independent trials or confidence intervals. Repeated prints and shared outcomes remain heavily dependent.

When PM's combo YES probability is more than 0.5 cents lower, the 2,127 prints have $36,707.88 known seller P&L and PM's quantity-weighted Brier score is better by 0.001537. When PM is more than 0.5 cents higher, the 1,163 prints have $1,501.80 known seller P&L and PM's score is worse by 0.000495. This directional asymmetry may reflect the day's realized outcomes rather than transferable source sharpness. The 18,590 prints within 0.5 cents produce most overall seller P&L. Direction bands describe combo fair differences, not the differences of individual legs.

## What the rejection rule means

For observed YES price p, modeled combo YES probability f, quantity q and dollar maker fee F, this report selects a hypothetical seller execution when:

`q * (p - f) - F >= 0.003 * q`

The Kalshi point fair is the product of selected-side historical leg midpoint probabilities. This diagnostic uses point entry, not the stressed upper reserve, and has no premium cap. Of 21,880 common prints, 21,125 fail this price test and 755 pass. With existing funding and concentration limits, 645 then fail underlying-contract risk, eight fixture risk and six ticket capital, leaving 96 accepted. The replay tests the full printed quantity; it does not resize to remaining risk capacity.

A rejected observed execution can still correspond to an eligible RFQ we would quote at a higher YES ask. Broad quoting should compute fair, exact execution fees, uncertainty/dependence reserves, inventory adjustment and commercial markup, then enforce source health, mapping and risk constraints. The public tape reveals transactions at other participants' prices; it does not establish demand or our fill probability at a wider ask. Unknown joint payoffs or unhealthy inputs can still require abstention.

Known settlement P&L is attributed back to trade time as requested, while cash is released at settlement. Many earlier prints therefore inherit the same later game outcome, creating a smooth upward curve without independent intraday profit observations. More independent slates are needed to assess robustness.

## Historical validation and implementation plan

1. Freeze the current 0.3-cent rule and exchange models as baselines. Extend complete, outcome-blind July/August dates using the saved acquisition plan; add all eligible leg histories and report common-source versus incremental coverage. Current collection is one full September day plus incomplete retained dates. Older full-day collection has not run in this update.
2. Use an earlier development block and later untouched validation block, grouped by underlying fixture so combos sharing games cannot leak between folds. Purge shared fixtures across time boundaries. Acquire enough independent slates before reporting day-level Sharpe or resampled uncertainty. Verify fee schedules effective on each historical date, rather than carrying September fees backward.
3. On identical decisions, compare Kalshi, PM, fixed blends and available Pinnacle blends. Test signed and absolute disagreement, leg count, market family, premium, time to first pitch/kickoff and feed age. Compare forecast calibration, Brier/log loss, net seller P&L, P&L per resolved exposure, drawdown and concentration. Include equal-print, quantity and per-fixture/day summaries; do not treat print count as independent sample size. Use matched exposures and common risk budgets for strategy comparisons.
4. Distinguish marginal source quality from the combo joint model. Test individual-leg forecasts against their outcomes before crediting combo performance to sharper legs. Inspect correlated forecast errors and retain separate same-game modeling. Audit asynchronous timestamps, stale trades versus true midpoints, settlement basis and historical spread/depth imputation. Repeat with plausible timestamp and depth assumptions; forward trading must record actual depth.
5. Test fixed broad-quote policies in shadow alongside selection diagnostics. Log every eligible RFQ, source state, timestamps, canonical leg mappings, individual and combo fair, disagreement, reserves, candidate prices, available risk, final decision and subsequent marks. Shadow candidate prices are not observed accepted/rejected quotes. Estimate response/acceptance behavior only from quote lifecycle evidence that can support it.

Keep one shared ingestion, market-mapping, fee, risk, quoting and evaluation framework. Give MLB and NFL separate versioned model configurations for source reliability weights, innovation response to delayed Pinnacle, uncertainty reserves and joint pricing parameters. MLB starting-pitcher/lineup and baseball payoff effects warrant different features from NFL injury, weather, tie and football scoring effects. Initially use explicit conservative defaults and record parameter provenance; promote sport-specific fits only with validation. NFL/CFB/MLB results must remain separately labeled. A source prior can be tested without assuming it holds universally.

## Reproduction

`scripts/model_disagreement_report.py` pairs exact common evaluations, rejects duplicate/mismatched records and inventory-contaminated decisions, and writes selection overlap, directional/magnitude bands, leg/premium/family cuts, paired probability scores, exposure-normalized P&L, unknown-outcome bounds and leave-one-fixture-out diagnostics. The current CLI explicitly supports MLB only; NFL inputs need sport-aware family validation before reuse.

```sh
.venv/bin/python scripts/model_disagreement_report.py \
  --input runs/mlb_historical_20260907/common_model_report/unconstrained_decisions.jsonl.gz \
  --sport mlb \
  --out runs/mlb_historical_20260907/common_model_report/disagreement.json
.venv/bin/python -m pytest -q tests/test_model_disagreement_report.py tests/test_mlb_model_research.py
```

The JSON records input/code hashes and timestamp coverage. Fourteen focused checks passed, including pairing integrity, direction/scoring, unknown outcomes and the existing historical replay tests. No new historical API calls, live orders, production weight changes or risk-limit changes were made for this audit.
