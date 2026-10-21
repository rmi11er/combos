# July 23 spread, entry and capacity review

All source/output hashes and compensation-plus-residual identities verify. The spread cohort has 15,794 common moneyline prints, $3,262,231.97 face and +$114,890.99 net. It differs from the 21,125-print common game-market cohort (+$221,465.16). 24,742 eligible moneyline candidates yield 24,534 feature-covered prints before common-model restriction.

Kalshi compensation averages −0.595c/contract, residual +4.117c, realized +3.522c. Positive realized profit mainly reflects outcomes rather than modeled compensation.

| Width | Controls | K compensation slope | Residual slope | Net slope | Net fixture-deletion range |
|---|---|---:|---:|---:|---|
| raw | spread_only | +0.115 | +1.183 | +1.298 | -2.974 to +3.155 |
| raw | price_and_leg_count | -0.034 | -0.483 | -0.517 | -2.334 to +1.316 |
| fee_expanded | spread_only | +0.065 | +0.703 | +0.768 | -1.581 to +1.528 |
| fee_expanded | price_and_leg_count | -0.036 | -0.637 | -0.673 | -1.788 to +0.194 |

Slopes are cents per payout contract per additional cent of summed opposite-team width. Every net slope changes sign under fixture omission. Unadjusted compensation slopes are positive, adjusted negative. Price/leg-count controls can create mechanical relationships; no causal toxicity or stable surcharge is established. Width is a historical price proxy, not live depth. All four models are retained in the evidence.

| Model | 0c net | 0.3c/combo net | 0.3c/leg net |
|---|---:|---:|---:|
| kalshi | $17,526.29 | $5,701.92 | $1,326.73 |
| exchange_blend_equal | $10,091.00 | $8,715.81 | $3,205.74 |
| exchange_blend_pm75 | $30,919.79 | $7,276.00 | $2,371.13 |
| polymarket | $54,143.43 | $-985.56 | $2,232.03 |

All zero-edge variants exceed their 0.3c/combo counterparts on this date. PM is positive at both 0c and 0.3c/leg but negative at 0.3c/combo. This nonmonotonic outcome is not an acceptance curve: each hurdle selects prints at fixed observed prices.

| Model | Scenario | Net P&L | Peak cash |
|---|---|---:|---:|
| exchange_blend_equal | baseline | $160.74 | $974.44 |
| exchange_blend_pm75 | baseline | $95.13 | $995.60 |
| kalshi | baseline | $-97.93 | $822.52 |
| polymarket | baseline | $29.06 | $1,112.35 |
| exchange_blend_equal | balanced_1000 | $644.96 | $5,826.26 |
| exchange_blend_pm75 | balanced_1000 | $-178.52 | $6,714.02 |
| kalshi | balanced_1000 | $312.17 | $5,381.63 |
| polymarket | balanced_1000 | $179.55 | $7,538.84 |
| exchange_blend_equal | capital_only | $2,953.02 | $11,676.32 |
| exchange_blend_pm75 | capital_only | $1,939.57 | $11,954.12 |
| kalshi | capital_only | $-129.30 | $10,092.07 |
| polymarket | capital_only | $1,355.97 | $12,234.03 |

Each scenario starts with $10k; underlying/combo/fixture caps are baseline $100/$100/$250, balanced1000 $1k/$1k/$2k, capital-only $10k each. Actual settled gains can finance subsequent trades; eventual trade-time attribution cannot. Full observed quantities are accepted/rejected; no partial sizing. These separate daily accounts are not cumulative multi-date performance. Historical .035 fee applicability and Pinnacle absence remain limitations. No live policy changed.

[Verified all-model details](../runs/morning_research_20260908/july23_spread_capacity_review/verification.json)
