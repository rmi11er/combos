# July 19 spread and capacity review

Entry, risk and spread outputs pass source-hash and component-identity checks. Common priced cohort: 21,721 prints; sell-all net −$162,827.18. Moneyline feature candidates: 18,168; 17,964 have paired features before common-model restriction. No Pinnacle; historical fee scenario remains unverified.

| Model | 0c net | 0.3c/combo net | 0.3c/leg net |
|---|---:|---:|---:|
| kalshi | $-31,650.78 | $-9,921.09 | $-263.29 |
| exchange_blend_equal | $8,225.63 | $-7,621.04 | $-551.28 |
| exchange_blend_pm75 | $7,755.18 | $3,027.84 | $-366.39 |
| polymarket | $31,114.30 | $22,256.59 | $2,982.15 |

These thresholds select prints at their observed price; they do not reprice RFQs or measure acceptance elasticity. Lowering the hurdle improves PM/equal on this day but worsens Kalshi. A larger hurdle does not monotonically improve realized profit.

| Model | Risk scenario | Fills | Net P&L | Peak committed cash |
|---|---|---:|---:|---:|
| exchange_blend_equal | baseline | 40 | $-56.65 | $707.62 |
| exchange_blend_pm75 | baseline | 60 | $-24.58 | $754.44 |
| kalshi | baseline | 38 | $-4.05 | $670.45 |
| polymarket | baseline | 91 | $153.84 | $1,067.80 |
| exchange_blend_equal | balanced_1000 | 91 | $128.36 | $5,722.45 |
| exchange_blend_pm75 | balanced_1000 | 151 | $839.23 | $7,564.20 |
| kalshi | balanced_1000 | 84 | $48.19 | $5,581.83 |
| polymarket | balanced_1000 | 217 | $895.13 | $9,219.24 |
| exchange_blend_equal | capital_only | 92 | $-239.93 | $10,335.22 |
| exchange_blend_pm75 | capital_only | 121 | $2,396.31 | $11,512.64 |
| kalshi | capital_only | 97 | $-289.42 | $10,142.21 |
| polymarket | capital_only | 143 | $2,768.71 | $11,526.34 |

Baseline underlying/combo/fixture caps are $100/$100/$250; balanced1000 uses $1,000/$1,000/$2,000; capital-only sets each bucket cap to $10k. These are separate full-print accounts with $10k initial cash and actual-settlement recycling. Gains can raise peak cash above $10k. Balanced1000 profits across models on this day, while capital-only still loses for K/equal. Full multi-date funding remains necessary before risk selection.

| Width | Controls | Kalshi compensation slope | Residual slope | Net slope | Net fixture-deletion range |
|---|---|---:|---:|---:|---|
| raw | spread_only | +0.091 | -0.526 | -0.435 | -1.043 to +1.629 |
| raw | price_and_leg_count | -0.061 | -1.030 | -1.091 | -2.179 to +0.265 |
| fee_expanded | spread_only | +0.054 | -0.125 | -0.071 | -0.341 to +0.873 |
| fee_expanded | price_and_leg_count | -0.060 | -1.675 | -1.735 | -2.873 to -0.091 |

Slopes are cents per payout contract per extra cent of summed underlying width. Opposite-team widths proxy prices, not actual depth. Unadjusted compensation slopes are positive, adjusted slopes negative. Net slopes are negative; only the adjusted fee-expanded specification stays negative after every fixture omission. This is compatible with uncertainty costs but does not identify toxicity or prove a profitable surcharge. Price/leg-count controls can introduce mechanical relationships. Deletion ranges are overlapping influence checks, not confidence intervals. All four model regressions are retained in the evidence.

[Verification and all model regressions](../runs/morning_research_20260908/july19_spread_capacity_review/verification.json)
