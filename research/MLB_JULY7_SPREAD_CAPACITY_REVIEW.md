# July 7 spread and capacity review

Wider raw underlying spreads associate with better settlement residuals on July 7, but risk expansion generally worsens funded performance. This reverses July 5's width relationship and provides no stable daily-derived surcharge or capital-deployment rule.

## Completion and coverage

July 7 batch is complete and calibration declares output_complete. Reviewed input/code hashes match; all compensation/residual means and regression coefficients sum to realized values. Entry/capacity use 20,386 common prints, whose sell-all result is −$313,202.349700. Common spread analysis is narrower: 15,586 moneyline prints, $3,229,788.84 face and −$232,838.0725 net, all outcomes known.

Kalshi's available spread cohort has 19,812 prints; comparing it directly with PM would change observations. Of 19,979 moneyline feature candidates, 150 have uncovered timestamps, three no prior Kalshi state, four no covered history, ten crossed raw pairs. Common model availability removes a further 4,226 feature-covered prints.

## Compensation versus residual

Quantity-weighted cents per payout contract: compensation =100×(price−fair−maker fee/quantity); residual =100×(fair−settlement); their sum is realized net. Opposite-team widths are descriptive proxies, not executable combo spreads or depth measures.

| Common model | Compensation c | Residual c | Realized c |
|---|---:|---:|---:|
| exchange_blend_equal | -0.296 | -6.913 | -7.209 |
| exchange_blend_pm75 | -0.263 | -6.946 | -7.209 |
| kalshi | -0.361 | -6.848 | -7.209 |
| polymarket | -0.230 | -6.979 | -7.209 |

| Width/specification | Model | Compensation slope | Residual slope | Net slope | Net fixture-deletion range |
|---|---|---:|---:|---:|---|
| raw/spread_only | exchange_blend_equal | +0.133 | +5.948 | +6.080 | +3.110 to +8.870 |
| raw/price_and_leg_count | exchange_blend_equal | +0.017 | +9.310 | +9.327 | +3.767 to +11.408 |
| fee_expanded/spread_only | exchange_blend_equal | +0.050 | +1.016 | +1.065 | +0.091 to +2.463 |
| fee_expanded/price_and_leg_count | exchange_blend_equal | +0.035 | +1.099 | +1.134 | -0.819 to +2.857 |
| raw/spread_only | exchange_blend_pm75 | +0.136 | +5.945 | +6.080 | +3.110 to +8.870 |
| raw/price_and_leg_count | exchange_blend_pm75 | +0.042 | +9.285 | +9.327 | +3.767 to +11.408 |
| fee_expanded/spread_only | exchange_blend_pm75 | +0.049 | +1.017 | +1.065 | +0.091 to +2.463 |
| fee_expanded/price_and_leg_count | exchange_blend_pm75 | +0.062 | +1.071 | +1.134 | -0.819 to +2.857 |
| raw/spread_only | kalshi | +0.127 | +5.954 | +6.080 | +3.110 to +8.870 |
| raw/price_and_leg_count | kalshi | -0.034 | +9.361 | +9.327 | +3.767 to +11.408 |
| fee_expanded/spread_only | kalshi | +0.052 | +1.013 | +1.065 | +0.091 to +2.463 |
| fee_expanded/price_and_leg_count | kalshi | -0.022 | +1.155 | +1.134 | -0.819 to +2.857 |
| raw/spread_only | polymarket | +0.139 | +5.942 | +6.080 | +3.110 to +8.870 |
| raw/price_and_leg_count | polymarket | +0.067 | +9.260 | +9.327 | +3.767 to +11.408 |
| fee_expanded/spread_only | polymarket | +0.047 | +1.018 | +1.065 | +0.091 to +2.463 |
| fee_expanded/price_and_leg_count | polymarket | +0.090 | +1.043 | +1.134 | -0.819 to +2.857 |

Slopes are cents per payout contract per additional 1c summed underlying width. Adjusted models control traded YES price and categorical leg count. Raw net slopes +6.080/+9.327 remain positive through all 31 overlapping fixture deletions. Fee-expanded slopes +1.065/+1.134 are smaller; the adjusted deletion range crosses zero. Compensation slopes are much smaller than residual slopes; adjusted K compensation is negative while PM/blends are positive. Effective weighted count ~823 is not 823 independent outcomes.

July 5 raw slopes were −3.150/−4.381 and July 3 +5.190/+3.198. Negative overall P&L and positive within-day width slopes can coexist. These are not causal toxicity estimates or quoting markups; traded-price controls create mechanical associations and deletion ranges are influence diagnostics, not confidence intervals. Pool exact weighted sufficient statistics rather than averaging daily slopes.

## Observed-price entry filters

| Model | Unlimited ≥0c net | ≥0.3c/combo net | ≥0.3c/leg net | Per-leg prints |
|---|---:|---:|---:|---:|
| kalshi | $-2,255.20 | $2,535.18 | $-1,136.24 | 16 |
| exchange_blend_equal | $-44,962.36 | $1,304.94 | $-1,162.60 | 18 |
| exchange_blend_pm75 | $-72,177.75 | $-2,958.69 | $-1,671.89 | 25 |
| polymarket | $-186,917.38 | $-16,907.64 | $-2,415.55 | 47 |

At 0.3c/combo, K remains positive after every fixture omission (minimum +$243); equal can reverse (minimum −$765); PM75's range stays negative. All per-leg selections lose, with PM/PM75 remaining negative after any one-fixture omission. Zero-edge selections also all lose. Neither tightening nor lowering the threshold monotonically improves performance. Common sell-all stays negative after every one-fixture omission (−$477,811 to −$45,534).

The per-leg hurdle means 0.6–1.2c per 2–4-leg combo contract, already net of maker fees. These filters select observed prints; they do not establish RFQ win probabilities or revenue at different quote prices.

## Capacity at 0.3c/combo

Every model/scenario starts with $10k. Baseline contract/combo/fixture caps are $100/$100/$250; balanced1000 uses $1,000/$1,000/$2,000; capital-only $10k per bucket. No ticket cap or partial resizing. Only actual settled gains finance later fills.

| Model | Baseline net / peak cash | Balanced1000 net / peak cash | Capital-only net / peak cash |
|---|---:|---:|---:|
| kalshi | $69 / $589 | $59 / $3,434 | $-288 / $9,802 |
| exchange_blend_equal | $-242 / $549 | $-898 / $3,689 | $-1,302 / $8,493 |
| exchange_blend_pm75 | $-234 / $745 | $-889 / $4,867 | $-2,812 / $9,997 |
| polymarket | $-200 / $828 | $-1,208 / $7,298 | $-5,611 / $10,000 |

Combo-only expansion changes no baseline result. Balanced1000 deploys more and worsens P&L for the three PM-containing models; K stays slightly positive. Capital-only loses for all four models. The manifest's 43 fixtures give a loose baseline fixture-cap ceiling of $5,375, further tightened by underlying caps and full-print granularity. These runs do not test the separate partial-sizing workflow. Peak cash can exceed initial capital when actual gains settle; the starting $10k is not a permanent fixed exposure cap.

## Research implication and evidence

Keep fixed hurdle/capacity scenarios across the expanded development sample, then assess held-out results with coverage and fixture dependence explicit. July 7 weakens both automatic risk expansion and a universally beneficial per-leg filter. No production policy is promoted.

Sources: `dated_fee_primary/2026-07-07/entry_sweep/{manifest,summary}.json`, `risk_capacity/{manifest,summary}.json`; `spread_v2/2026-07-07/{feature_manifest.json,calibration/manifest.json,calibration/results.json}`. Separate proof: `runs/morning_research_20260908/july7_spread_capacity_review/verification.json`. Historical fee/source assumptions are inherited, not certified anew. No provider calls, August data, plots or frozen-source edits.
