# July 19 selected-ledger and source audit

All eight portfolios reconcile native prices, sizes, outcomes and fees; admission thresholds, decision/fill joins and selected plus rejected partitions pass. Funded risk checks reconcile retained decisions, rather than independently replaying the complete cash book.

Common cohort: **21,721 prints**, sell-all net **−$162,827.18**. Scope is 2–4-leg pregame distinct-fixture game markets with common source coverage. Entry requires **0.3c per combo contract**, net of maker fee, at observed price. No premium cap. Historical fee applicability remains an unverified scenario, Pinnacle is absent and fills are hypothetical.

| Regime | Model | Fills | Net P&L | Modeled edge | Peak committed cash | Minimum net after one fixture omission |
|---|---|---:|---:|---:|---:|---:|
| constrained | exchange_blend_equal | 40 | $-56.65 | $17.42 | $707.62 | $-83.44 |
| constrained | exchange_blend_pm75 | 60 | $-24.58 | $17.14 | $754.44 | $-70.92 |
| constrained | kalshi | 38 | $-4.05 | $16.31 | $670.45 | $-39.17 |
| constrained | polymarket | 91 | $153.84 | $19.07 | $1,067.80 | $95.96 |
| unconstrained | exchange_blend_equal | 112 | $-7,621.04 | $446.62 | $31,808.41 | $-9,363.08 |
| unconstrained | exchange_blend_pm75 | 354 | $3,027.84 | $825.58 | $73,838.65 | $-3,404.07 |
| unconstrained | kalshi | 101 | $-9,921.09 | $340.75 | $28,992.23 | $-11,403.42 |
| unconstrained | polymarket | 936 | $22,256.59 | $1,797.27 | $196,834.84 | $4,470.61 |

Matched PM-minus-Kalshi quantity-weighted Brier is -0.00029267; PM remains better across all 50 single-fixture omissions (range -0.00050751 to -0.00001293). This is stronger within-day evidence for PM than July 11/17, whose rankings can reverse. Omissions overlap and are influence diagnostics, not confidence intervals.

| Selection group | Prints | Net P&L |
|---|---:|---:|
| both | 86 | $-10,673.15 |
| kalshi_only | 15 | $752.06 |
| neither | 20,770 | $-185,835.84 |
| polymarket_only | 850 | $32,929.74 |

PM-only prints earned $32,929.74, while prints accepted by both models lost $10,673.15. The PM-selected unlimited portfolio remains positive after each single-fixture omission, with a minimum of $4,470.61. However its $22,256.59 realized profit exceeds $1,797.27 of modeled compensation: favorable outcome residuals still explain most profit. The funded PM portfolio earns $153.84 with 91 hypothetical fills; daily portfolios cannot be summed into a continuous $10k account.

The opposite ranking on July 17 argues for pooled, game-aware calibration and conditional source-disagreement tests, not promotion of a daily winner. No hyperparameters or live source weights are changed.

[Unconstrained plot](../runs/mlb_historical_20260907/dated_fee_primary/2026-07-19/common_model_report/unconstrained.png) · [Funded plot](../runs/mlb_historical_20260907/dated_fee_primary/2026-07-19/common_model_report/constrained.png) · [Independent audit](../runs/morning_research_20260908/july19_selected_audit/verification.json) · [Source disagreement](../runs/morning_research_20260908/july19_selected_audit/disagreement.json)
