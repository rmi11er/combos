# July 21 spread compensation and residual review

Complete entry/risk/spread outputs and source hashes verify. Compensation + settlement residual = realized P&L holds for all component means and every regression coefficient.

The common moneyline spread cohort has **27,848 prints**, **$7,197,021.35 payout face** and **+$71,981.41** net seller P&L. It is narrower than the 34,742-print common game-market cohort, which loses $30,271.56. Feature availability and market-family restrictions change the denominator; neither result describes the 346,450-print broad native universe. Of 40,508 eligible moneyline feature candidates, 40,334 have covered pairs; further common-model intersection leaves 27,848.

Kalshi-based compensation averages **−0.455c/contract**, outcome residual **+1.455c**, realized **+1.000c**. Positive realized outcome does not establish positive ex-ante compensation.

| Model | Width | Controls | Compensation slope | Residual slope | Net slope | Net fixture-deletion range |
|---|---|---|---:|---:|---:|---|
| exchange_blend_equal | raw | spread_only | +0.166 | +2.159 | +2.325 | -0.120 to +5.709 |
| exchange_blend_equal | raw | price_and_leg_count | -0.038 | +0.889 | +0.851 | -1.498 to +3.459 |
| exchange_blend_equal | fee_expanded | spread_only | +0.072 | +0.778 | +0.849 | +0.049 to +1.940 |
| exchange_blend_equal | fee_expanded | price_and_leg_count | -0.034 | +0.587 | +0.554 | -1.713 to +3.255 |
| exchange_blend_pm75 | raw | spread_only | +0.160 | +2.165 | +2.325 | -0.120 to +5.709 |
| exchange_blend_pm75 | raw | price_and_leg_count | -0.019 | +0.870 | +0.851 | -1.498 to +3.459 |
| exchange_blend_pm75 | fee_expanded | spread_only | +0.067 | +0.782 | +0.849 | +0.049 to +1.940 |
| exchange_blend_pm75 | fee_expanded | price_and_leg_count | -0.016 | +0.569 | +0.554 | -1.713 to +3.255 |
| kalshi | raw | spread_only | +0.179 | +2.146 | +2.325 | -0.120 to +5.709 |
| kalshi | raw | price_and_leg_count | -0.076 | +0.927 | +0.851 | -1.498 to +3.459 |
| kalshi | fee_expanded | spread_only | +0.081 | +0.769 | +0.849 | +0.049 to +1.940 |
| kalshi | fee_expanded | price_and_leg_count | -0.070 | +0.624 | +0.554 | -1.713 to +3.255 |
| polymarket | raw | spread_only | +0.154 | +2.172 | +2.325 | -0.120 to +5.709 |
| polymarket | raw | price_and_leg_count | -0.000 | +0.851 | +0.851 | -1.498 to +3.459 |
| polymarket | fee_expanded | spread_only | +0.062 | +0.787 | +0.849 | +0.049 to +1.940 |
| polymarket | fee_expanded | price_and_leg_count | +0.002 | +0.551 | +0.554 | -1.713 to +3.255 |

Slopes are cents per payout contract per additional cent of summed leg width. Width is inferred from opposite-team prices, not measured executable depth. Unadjusted Kalshi compensation slopes are positive; after traded-price and leg-count controls they are negative across all fixture omissions. Raw net slopes and adjusted fee-expanded net slopes change sign with omission; only unadjusted fee-expanded net stays positive across those omissions.

These correlations do not identify causal toxicity or a profitable quoting surcharge. Price controls can introduce mechanical relationships, and overlapping fixture deletions are influence diagnostics rather than confidence intervals. The alternating signs across July dates still require pooled sufficient-statistic estimation and day/game-aware validation. No new filter or live parameter is selected. Historical fee applicability and missing Pinnacle limitations persist.

[All-model evidence and entry/risk values](../runs/morning_research_20260908/july21_spread_capacity_review/verification.json) · [Entry/risk interpretation](MLB_JULY21_ENTRY_RISK_REVIEW.md)
