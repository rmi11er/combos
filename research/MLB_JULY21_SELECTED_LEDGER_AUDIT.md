# July 21 selected-ledger and source audit

All eight model portfolios pass native-price/size/outcome/fee joins, edge-threshold checks, decision/fill reconciliation and selected-plus-rejected accounting. Funded checks verify retained risk decisions; this audit is not an independent full cash replay.

Common priced cohort: **34,742 prints**, sell-all net **−$30,271.56**. This is the narrower 2–4-leg, distinct-fixture, pregame game-market cohort with common source coverage; broad native seller net is −$1.858m. The hurdle is **0.3c per combo contract**, after maker fees, with no premium cap. Historical .035 fee applicability remains unverified, Pinnacle is absent and executions are hypothetical at observed price/full quantity.

| Regime | Model | Fills | Net P&L | Modeled edge | Peak cash | Minimum net after game omission |
|---|---|---:|---:|---:|---:|---:|
| constrained | exchange_blend_equal | 42 | $62.92 | $6.49 | $478.78 | $17.35 |
| constrained | exchange_blend_pm75 | 59 | $-17.91 | $8.16 | $615.87 | $-85.78 |
| constrained | kalshi | 29 | $71.48 | $5.93 | $396.83 | $27.96 |
| constrained | polymarket | 93 | $88.24 | $11.32 | $1,009.80 | $29.65 |
| unconstrained | exchange_blend_equal | 91 | $23,170.97 | $1,040.48 | $126,063.63 | $6,433.30 |
| unconstrained | exchange_blend_pm75 | 260 | $24,680.54 | $1,437.17 | $181,825.76 | $4,256.30 |
| unconstrained | kalshi | 63 | $21,253.26 | $933.63 | $102,973.57 | $4,642.43 |
| unconstrained | polymarket | 1485 | $74,211.28 | $2,798.92 | $416,980.29 | $15,040.09 |

PM-minus-Kalshi matched quantity-weighted Brier is -0.00027267. PM is better in 36/38 fixture omissions, but the range [-0.00053794, +0.00027598] crosses zero. Unlike July 19, the paired score ranking is not invariant to omission.

| Selection | Prints | Net P&L |
|---|---:|---:|
| both | 51 | $14,467.08 |
| kalshi_only | 12 | $6,786.18 |
| neither | 33,245 | $-111,269.02 |
| polymarket_only | 1,434 | $59,744.20 |

All four unconstrained selections remain positive after every single-fixture omission; PM-only prints contribute $59,744.20. Nevertheless modeled compensation is only $934–$2,799 against $21,253–$74,211 eventual profit. Favorable settlement residuals dominate. Omission tests overlap, do not reallocate rejected trades, and are not confidence intervals.

Funded K/equal/PM also stay positive after every omission; PM75 loses overall. These are independent single-day $10k accounts, not additive contributions to the final continuous account. Most capital remains idle with current risk limits. No live source weight, pricing hurdle or cap is changed.

[Unconstrained plot](../runs/mlb_historical_20260907/dated_fee_primary/2026-07-21/common_model_report/unconstrained.png) · [Funded plot](../runs/mlb_historical_20260907/dated_fee_primary/2026-07-21/common_model_report/constrained.png) · [Audit evidence](../runs/morning_research_20260908/july21_selected_audit/verification.json) · [Paired source evidence](../runs/morning_research_20260908/july21_selected_audit/disagreement.json)
