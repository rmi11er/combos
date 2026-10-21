# July25 underlying-spread decomposition

The completed workflow retains43,605paired opposite-moneyline features from43,800eligible moneyline prints. Its common model/calibration cohort contains43,603prints and11,534,326.35payout contracts. Net seller P&L is−$696,266.46. This differs from the58,458print model cohort because spreads/totals are excluded and opposite-market coverage is required.

For Kalshi fair, average compensation is−0.4321c/contract, fair-minus-outcome residual−5.6044c, and realized net−6.0365c. The decomposition reconciles both overall and coefficient-by-coefficient in the regressions. Source/input hashes and completion markers were checked by the retained review script.

| Spread measure / regression | Compensation slope | Residual slope | Net slope | Net slope after single-fixture omission |
|---|---:|---:|---:|---:|
| Raw / spread only | +0.1113 | +4.3801 | +4.4913 | [+1.8418,+7.1148] |
| Raw / price and leg count adjusted | −0.0510 | +5.3137 | +5.2626 | [+1.6857,+8.7202] |
| Fee-expanded / spread only | +0.0542 | +1.3634 | +1.4176 | [+0.6997,+2.0852] |
| Fee-expanded / price and leg count adjusted | −0.0529 | +5.7615 | +5.7086 | [+2.3683,+8.1013] |

Slopes are cents of component P&L per contract per one-cent increase in the corresponding spread feature; regressions are quantity-weighted. There are36fixture-omission refits and no refit failures. These overlapping deletions are influence diagnostics, not confidence intervals; no IID p-values or standard errors are reported.

All four net slopes stay positive under fixture omission. Yet adjusted compensation slopes stay negative under every omission: raw[−0.0729,−0.0307], fee-expanded[−0.0755,−0.0309]. Thus better realized outcomes at wider spreads do not establish that wider spreads earn more ex-ante compensation after controlling for price and leg count. Outcome residuals dominate the relationship. Positive slope also does not imply a profitable overall cohort: the average result is strongly negative.

This date differs from prior dates with unstable or negative spread slopes. Retain all dates in the pooled and held-out analysis. The feature is a historical opposite-moneyline spread proxy, not observed depth or actual executable joint liquidity. It cannot alone calibrate a live liquidity surcharge. No filter, source weight or live edge charge changed.

[Verified components and regressions](../runs/morning_research_20260908/july25_spread_capacity_review/verification.json) · [Complete calibration results](../runs/morning_research_20260908/spread_v2/2026-07-25/calibration/results.json)
