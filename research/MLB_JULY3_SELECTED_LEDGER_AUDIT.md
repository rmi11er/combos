# July 3 common-model selected-ledger audit

All four funded and four unlimited portfolios pass the independent selected-ledger audit. Losses in the unlimited portfolios are reproduced from native outcomes and prices; **fees are charged once**, not twice. The funded portfolios are near flat and much smaller.

The common intersection contains 26,176 distinct public prints per model; all have known native outcomes and are 2–4-leg, scheduled-pregame YES-taker prints. These are hypothetical sales at observed full quantities, without an RFQ acceptance model. July 3 is the trade date: some included games occur on July 4/5. All fees and settlements join exactly back to the separately audited native cohort. Pinnacle is unavailable, so these are four exchange-only models, not the proposed three-source live fair.

## Exact selection and P&L

The hurdle is **0.003 dollars per combo contract (0.3 cents), not per leg**: `quantity × (observed YES price − combo fair) − maker_fee >= quantity × .003`. All 209,408 decisions across both regimes were checked. Every unlimited accept/reject follows this hurdle and quote guard. Every accepted fill matches one decision with the same size, price, fee and settlement, and eventual P&L is attributed at trade time. No rejected decision has a fill. All funded accepted risk checks respect the retained limits. This is a validation of recorded funded checks, not a second complete chronological cash/risk replay.

| Model | Funded fills | Funded net | Unlimited fills | Unlimited net | Unlimited model edge |
|---|---:|---:|---:|---:|---:|
| kalshi | 60 | $-24.13 | 228 | $-30,638.35 | $390.38 |
| polymarket | 80 | $53.36 | 2,295 | $-129,950.09 | $2,987.68 |
| exchange_blend_equal | 60 | $45.72 | 299 | $-22,867.89 | $602.86 |
| exchange_blend_pm75 | 66 | $-15.25 | 756 | $-50,843.02 | $1,264.79 |

Selling every print in this same common intersection loses $1,198,875.690700. Selected plus rejected P&L, premiums, fees, face and point edge reconcile exactly for each portfolio. Positive model edge is an ex-ante expectation, not guaranteed realized earnings; all four full common-cohort models underpredict the observed size-weighted settlement frequency on this date.

One small cash-precision issue surfaced: binary float construction of NO cost before RiskLedger ceilings can reserve an extra $0.0001. This occurs on 61 of 266 funded accepted rows (sum $0.0061 across the four separate portfolios). It is conservative risk reservation noise, not duplicated maker fees or an explanation for losses. Exact Decimal cash inputs would avoid it in a later reviewed change; frozen code was not edited.

## Selected concentration

These exclusions omit the already accepted fills involving a fixture; they do not rerun allocation or admit replacements. Membership overlaps, so fixture contributions must not be added together.

| Regime/model | Worst fixture membership | Fixture net | Net after omission | Worst single-print net | Net omitting worst print |
|---|---|---:|---:|---:|---:|
| constrained/exchange_blend_equal | mlb:26JUL032010SFCOL | $-28.21 | $73.93 | $-39.58 | $85.31 |
| constrained/exchange_blend_pm75 | mlb:26JUL032138BOSLAA | $-70.80 | $55.55 | $-39.57 | $24.33 |
| constrained/kalshi | mlb:26JUL032015TBHOU | $-65.81 | $41.68 | $-70.67 | $46.55 |
| constrained/polymarket | mlb:26JUL032138BOSLAA | $-70.93 | $124.28 | $-42.97 | $96.33 |
| unconstrained/exchange_blend_equal | mlb:26JUL032210SDLAD | $-20,941.84 | $-1,926.05 | $-20,731.60 | $-2,136.29 |
| unconstrained/exchange_blend_pm75 | mlb:26JUL032210SDLAD | $-37,294.58 | $-13,548.44 | $-20,731.60 | $-30,111.41 |
| unconstrained/kalshi | mlb:26JUL031605STLCHC | $-26,118.15 | $-4,520.20 | $-15,414.36 | $-15,223.99 |
| unconstrained/polymarket | mlb:26JUL032145MILAZ | $-81,448.32 | $-48,501.77 | $-20,731.60 | $-109,218.48 |

The largest selected unlimited print for PM and both blends has 29,850 contracts, $9,343.05 YES premium and a $20,731.6037 loss. It spans July 3 SD–LAD, July 4 NYM–ATL and July 4 SD–LAD, with a realized YES settlement of one. The largest K-only portfolio print has 17,215.6 contracts, $1,859.2848 premium and a $15,414.3621 loss. All funded models' largest quantity is only 95.96 contracts ($9.40408 premium). Full IDs and memberships are retained in verification.json. Even removing the single worst print leaves each unlimited model negative.

## Paired fair calibration

Same exact 26,176 prints/outcomes for every model; lower Brier is better. These dependent-print descriptive scores are not significance tests or out-of-sample validation.

| Model | Equal-print Brier | Quantity-weighted Brier | Quantity-weighted fair minus outcome |
|---|---:|---:|---:|
| exchange_blend_equal | 0.25330952 | 0.22177798 | -0.17106328 |
| exchange_blend_pm75 | 0.25361302 | 0.22197822 | -0.17155160 |
| kalshi | 0.25270913 | 0.22138289 | -0.17008381 |
| polymarket | 0.25391870 | 0.22218024 | -0.17203898 |

PM minus K quantity-weighted Brier is +0.00079734: K is better on July 3. That direction remains after each of the 44 overlapping single-fixture omissions. Where PM prices more than 0.5 cents above K, PM is better (Brier difference −0.004306); where it prices more than 0.5 cents below K, PM is worse (+0.003287). This is consistent with the need to condition disagreement research on direction, rather than treating PM preference as universally beneficial.

| Selection | Prints | Net seller P&L |
|---|---:|---:|
| both | 141 | $-2,418.73 |
| kalshi_only | 87 | $-28,219.62 |
| neither | 23,794 | $-1,040,705.99 |
| polymarket_only | 2,154 | $-127,531.35 |

The result weakens a universal PM-sharper heuristic for this dataset/date. It does not test Pinnacle–PM agreement against K because Pinnacle history is missing, and one day of shared-game outcomes cannot establish persistent calibration. Both sources badly underpredict the day's size-weighted realized combo settlement frequency. Extend the fixed analyses across certified July dates before altering weights or risk limits; preserve native-universe/common-cohort coverage and fixture dependence.

## Evidence and reproducibility

`runs/morning_research_20260908/july3_selected_audit/verify.py` imports no production pricing or fee logic and records exact arithmetic, source hashes, reasons, all fixture omissions and largest/worst print IDs in `verification.json`. Existing `scripts/model_disagreement_report.py` generated `disagreement.json` from the unconstrained ledger without changes. `four_model_calibration.json` retains Decimal paired calibration totals. P&L/edge float fields are compared within $0.000001; source quantities, fees, settlements and fill identities match exactly. Historical .035 fee effective-date applicability remains unverified. No provider calls, August data, frozen-code edits or background jobs were used.
