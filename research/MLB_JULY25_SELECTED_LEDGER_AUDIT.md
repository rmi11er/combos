# July25 matched model selections

Independent native-ledger checks pass all eight funded/unlimited model portfolios. Each model sees the same58,458prints; selling all of this matched cohort loses$895,679.84. Prices, quantities, native settlements, single fee deductions, 0.3c/combo point-edge hurdle, accepted/fill identities and selected-plus-rejected accounting reconcile. Root rechecked input hashes and visually reviewed both equity plots. The funded audit checks recorded risk arithmetic, not an independent full portfolio replay.

| Model | Unlimited fills | Unlimited net | Modeled compensation | Funded fills | Funded net | Funded peak cash |
|---|---:|---:|---:|---:|---:|---:|
| Kalshi | 105 | +$5,047.98 | $299.33 | 50 | −$7.84 | $678.71 |
| Equal blend | 190 | −$6,096.82 | $545.88 | 56 | −$282.07 | $613.44 |
| PM75 | 969 | −$13,500.13 | $2,090.41 | 81 | −$244.14 | $877.78 |
| Polymarket | 3,662 | +$26,399.66 | $7,055.40 | 125 | −$285.85 | $1,245.83 |

Kalshi's unlimited result remains at least+$591.27 after any single-fixture omission. Polymarket's falls as low as−$57,603.73. Omission does not reallocate to other trades and is an influence diagnostic, not a confidence interval. Unlimited peak cash is$23,391.79/$32,260.65/$249,642.86/$842,850.29 for K/equal/PM75/PM; none is a realizable$10k account result.

On the common cohort, quantity-weighted Brier is0.14501639(K),0.14495737(equal),0.14493212(PM75),0.14490966(PM). PM's−0.00010673 paired difference is descriptive pending fixture-omission calibration analysis. Better full-cohort forecasting score does not ensure better selected or funded P&L. The fixed blends' losing portfolios alongside winning single-source portfolios make the acceptance boundary and sizing mix important pooled research questions; no source weight or risk setting is promoted from this date.

Scope is the completed2–4leg, distinct-fixture pregame matched exchange cohort. Pinnacle is absent. Historical maker-fee applicability remains an unverified scenario. These are hypothetical sales at public traded prices/full sizes, not our RFQ acceptance history. Eventual P&L is plotted at trade time; capital releases at actual settlement. One date cannot supply daily Sharpe/variance. August remains held out.

[Constrained curve](../runs/mlb_historical_20260907/dated_fee_primary/2026-07-25/common_model_report/constrained.png) · [Unconstrained curve](../runs/mlb_historical_20260907/dated_fee_primary/2026-07-25/common_model_report/unconstrained.png) · [Independent audit](../runs/morning_research_20260908/july25_selected_audit/verification.json) · [Four-model calibration](../runs/morning_research_20260908/july25_selected_audit/four_model_calibration.json)

## Independent fair arithmetic

The new reusable `scripts/audit_exchange_fair_points.py` verifies all233832common-cohort decisions against62356retained pricing-context rows. It independently reconstructs Kalshi midpoint/fee-expanded intervals, the historical PM spread proxy and fee-expanded interval, fixed leg blends, YES/NO orientation and products of selected leg probabilities. It checks both sources'60second modeled availability delay and no source availability after the decision. All checks passed. Five mutation-based tests verify that orientation, future availability, interval and decision-time errors fail the audit.

This closes a gap between native accounting checks and the actual recorded point-pricing calculation. It does not independently reconstruct raw provider responses, certify PM historical point semantics, certify payoff matching or historical fee applicability, or validate independence/correlation assumptions. Three-source liquidity weighting and the stressed joint bound remain separate tests. [Fair audit evidence](../runs/morning_research_20260908/july25_selected_audit/fair_point_audit.json).

The completed [paired disagreement diagnostic](../runs/morning_research_20260908/july25_selected_audit/disagreement.json) finds PM's aggregate calibration advantage changes sign after fixture omission. It therefore does not establish stable PM dominance on this date.

## Raw exchange capture checks

The separate `audit_recorded_exchange_sources.py` passes183184Kalshi native-state matches and176468Polymarket as-of-state matches across62356context rows and880raw capture files. Kalshi recorded bid/ask values and timestamps match the cited native candle; PM's point is the latest archived active observation at the decision's modeled60second cutoff, within the captured request interval. Root independently rechecked all882raw/input/auditor hashes. Four tests reject incorrect Kalshi prices, stale PM selections and incorrect PM points.

This verifies the link from captured values to recorded context. It does not independently resolve all overlapping Kalshi capture intervals, establish that a PM price-history point is an executable book midpoint, certify real publication latency, or certify payoff equivalence. It also cannot test the absent Pinnacle source. [Raw-source evidence](../runs/morning_research_20260908/july25_selected_audit/raw_source_audit.json) · [Root hash check](../runs/morning_research_20260908/july25_selected_audit/raw_source_root_verification.json).
