# July 23 selected-ledger and source audit

Eight portfolios pass native price/quantity/outcome/fee joins, edge thresholds, admission/fill reconciliation and selected-plus-rejected identities. Funded checks audit recorded risk decisions, not a separate full cash replay.

The **21,125-print common priced cohort earns $221,465.16 selling every print**, versus $2.603m in the broader native universe. Selection is 2–4-leg pregame distinct-fixture game markets, with common source availability and a **0.3c/combo-contract** hurdle after maker fees. No premium cap. Historical .035 maker-fee applicability remains unverified; Pinnacle is absent. Public prints are hypothetical full executions at observed prices.

| Regime | Model | Fills | Net P&L | Modeled edge | Peak cash | Minimum net after game omission |
|---|---|---:|---:|---:|---:|---:|
| constrained | exchange_blend_equal | 89 | $160.74 | $14.29 | $974.44 | $89.32 |
| constrained | exchange_blend_pm75 | 101 | $95.13 | $15.74 | $995.60 | $39.55 |
| constrained | kalshi | 80 | $-97.93 | $10.74 | $822.52 | $-148.58 |
| constrained | polymarket | 104 | $29.06 | $17.56 | $1,112.35 | $-29.10 |
| unconstrained | exchange_blend_equal | 473 | $8,715.81 | $507.14 | $38,752.34 | $2,407.97 |
| unconstrained | exchange_blend_pm75 | 689 | $7,276.00 | $1,035.56 | $82,434.87 | $-7,680.25 |
| unconstrained | kalshi | 275 | $5,701.92 | $480.16 | $65,554.61 | $-1,836.98 |
| unconstrained | polymarket | 1330 | $-985.56 | $2,205.47 | $150,577.01 | $-32,135.91 |

PM-minus-Kalshi matched quantity-weighted Brier is -0.00023239; PM is better overall, but omission range [-0.00073327, +0.00019476] crosses zero. PM's better aggregate forecast score does not translate to better selected-trade P&L on this day.

| Selection | Prints | Net P&L |
|---|---:|---:|
| both | 242 | $2,451.25 |
| kalshi_only | 33 | $3,250.66 |
| neither | 19,762 | $219,200.06 |
| polymarket_only | 1,088 | $-3,436.81 |

Equal-blend unlimited selection remains positive after every game omission. K/PM75 positive totals can reverse; PM loses overall. Funded equal/PM75 remain positive after every omission, while funded PM can reverse and K loses. These are separate daily accounts, not additive continuous-capital returns.

Most common-cohort profit lies among prints neither K nor PM selects ($219,200). This is descriptive rejection opportunity at historical prices, not evidence that every rejected RFQ would be profitable to quote or that we could fill the whole tape. The opposing results across July dates require pooled source calibration, compensation/residual and policy stability analysis. No source weight or risk setting is promoted.

[Unconstrained plot](../runs/mlb_historical_20260907/dated_fee_primary/2026-07-23/common_model_report/unconstrained.png) · [Funded plot](../runs/mlb_historical_20260907/dated_fee_primary/2026-07-23/common_model_report/constrained.png) · [Audit evidence](../runs/morning_research_20260908/july23_selected_audit/verification.json)
