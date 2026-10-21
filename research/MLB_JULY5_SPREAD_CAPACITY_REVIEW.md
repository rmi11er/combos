# July 5 MLB spread and capacity review

July 5 reverses July 3's outcome direction: wider raw spreads associate with worse settlement residuals, and relaxed risk limits are profitable on this date. The disagreement between days is evidence against setting a liquidity surcharge or risk budget from either daily result. It warrants the prespecified larger development and held-out comparisons, not averaging the two daily slopes.

## Completion and evidence

The batch marks July 5 complete, with entry and risk stages complete/exit 0; spread calibration records `output_complete: true`. Independently verified all 12 recorded hashes for entry/risk completion outputs and calibration input/code files. No frozen code, provider data or August outcomes were touched.

Entry/risk share 22,487 priced prints across all four models. Selling every print in that cohort makes **$396,446.09**, versus July 3's −$1,198,875.69. Spread analysis is the narrower moneyline subset: **18,372 prints, $4,321,968.41 payout quantity and $304,654.91 net P&L**, all known outcomes. Of 18,610 moneyline feature candidates, 205 have uncovered timestamps, 25 lack prior Kalshi states and eight lack covered history. Neither cohort is the entire native MLB combos universe.

## Compensation and calibration

All figures below are quantity-weighted cents per payout contract. Compensation is `(traded YES price − fair − maker fee/quantity)×100`; residual is `(fair − settlement)×100`. Their sum is realized net P&L per contract.

| Model | Compensation | Residual | Realized net |
|---|---:|---:|---:|
| Kalshi | −0.191 | +7.240 | +7.049 |
| Equal blend | +0.002 | +7.047 | +7.049 |
| PM75 | +0.098 | +6.951 | +7.049 |
| Polymarket | +0.193 | +6.856 | +7.049 |

Settlement residuals again dominate total results, but are favorable on July 5. Changing fair model reallocates compensation/residual; equal total P&L is an accounting identity on this common cohort, not independent model corroboration.

Raw-width net slope is **−3.150c per additional 1c summed underlying width**, with fixture-deletion range [−4.876,−0.623]. Compensation slopes are only +0.034 to +0.057c; residual slopes are approximately −3.18 to −3.21c. After controlling for traded price and categorical leg count, net slope is **−4.381c**, range [−9.064,−0.363]. Adjusted compensation slopes are −0.098c Kalshi, −0.013c equal, +0.029c PM75 and +0.071c PM. Thus the weaker compensation relationship remains model-dependent after controls.

Fee-expanded width gives −0.742c unadjusted net slope, range [−1.598,+0.379], and −3.870c adjusted, range [−8.867,−0.027]. Raw and fee-expanded widths are different predictors; slopes cannot be substituted directly into a quoting charge.

July 3's raw net slopes were +5.190 unadjusted and +3.198 adjusted, opposite to July 5. July 3's fee-expanded slopes were also positive. Neither day establishes causal toxicity: both depend on shared settlement outcomes, market composition, quantity concentration and controls that include traded price. July 5 has 28 overlapping fixtures and effective quantity-weighted count ~828, which is not 828 independent outcomes. Deletion ranges are influence diagnostics, not confidence intervals. Pool observations through exact weighted sufficient statistics and inspect date/fixture heterogeneity; do not average these daily slopes.

## Entry hurdle

These are acceptance filters at observed public prices, not evidence that our RFQs could charge or fill at those prices. The 0.3c/combo threshold requires quantity×$0.003 net edge. The 0.3c/leg threshold multiplies by 2–4 legs (0.6–1.2c per combo contract). Fees are already deducted when comparing edge.

Unlimited selected P&L (USD):

| Model | ≥0c | ≥0.3c/combo | ≥0.3c/leg | Per-leg prints |
|---|---:|---:|---:|---:|
| Kalshi | 144,286.39 | 69,809.36 | 22,153.31 | 112 |
| Equal blend | 256,584.88 | 158,971.65 | 94,947.27 | 651 |
| PM75 | 199,415.18 | 211,519.49 | 124,891.17 | 1,200 |
| Polymarket | 253,095.20 | 190,862.75 | 157,779.81 | 1,783 |

All per-leg selections remain positive after any single-fixture omission; lower endpoints are $8,319 Kalshi, $16,691 equal, $16,145 PM75 and $17,656 PM. The entire common cohort also remains positive (minimum $90,918). At 0.3c/combo, PM can become slightly negative after omission (−$4,158); the other three remain positive. These diagnostics are stronger than July 3's tiny favorable per-leg selections, but do not resolve across-day instability. Increasing participation is not monotonically better even on this profitable day: PM75's 0.3c/combo selection outperforms its 0c selection.

## Capacity scenarios

Capacity fixes the hurdle at **0.3c/combo**, not per leg. Baseline starting capital is $10k, contract/combo limits $100/$100 and fixture limit $250; no ticket cap. Balanced500 uses $500/$500/$1,000 limits; balanced1000 uses $1,000/$1,000/$2,000.

| Model | Baseline P&L / peak cash | Balanced500 P&L / peak cash | Balanced1000 P&L / peak cash | Capital-only P&L / peak cash |
|---|---:|---:|---:|---:|
| Kalshi | +38 / 908 | +919 / 4,144 | +1,116 / 8,457 | +2,904 / 11,062 |
| Equal blend | +49 / 971 | +1,045 / 3,991 | +1,392 / 8,091 | +4,161 / 11,438 |
| PM75 | −61 / 941 | +1,017 / 4,670 | +1,927 / 8,971 | +5,437 / 11,779 |
| Polymarket | −7 / 1,050 | +1,223 / 5,215 | +1,890 / 9,985 | +6,174 / 12,235 |

Only increasing combo limits changes none of the baseline results, as on July 3. Increasing underlying limits alone produces positive P&L for every model ($87–192); fixture-only changes are mixed. All balanced scenarios are positive here, unlike July 3. Capital-only loses $2.6k–7.5k on July 3 and gains $2.9k–6.2k on July 5: maximizing deployment magnifies date dependence. Peak cash exceeding $10k can reflect recycled actual settlement gains; the starting budget is not a permanent maximum committed-cash cap. These full-print acceptance tests do not model optimal partial RFQ sizing.

## Research implication

Retain the hurdle and risk scenario grid for larger-sample evaluation. Assess capacity together with drawdowns, fixture dependence, actual settlement cash timing and held-out stability. Separate liquidity-based compensation from settlement calibration; compare signals across dates and source disagreement before using them for live quote charges. No production model or risk limit is promoted from these two development days.

Sources: `runs/mlb_historical_20260907/dated_fee_primary/2026-07-05/{entry_sweep,risk_capacity}/{manifest,summary}.json`; `runs/morning_research_20260908/spread_v2/2026-07-05/{feature_manifest.json,calibration/manifest.json,calibration/results.json,calibration/REPORT.md}`. These retain the replay's fee and historical source assumptions. Comparison: [July 3 review](MLB_JULY3_SPREAD_CAPACITY_REVIEW.md).
