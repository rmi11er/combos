# July 9 spread and capacity review

July 9's all-priced cohort loses heavily, while a 0.3c/combo filter selects profitable unlimited subsets. Relaxing capacity remains model-dependent. Wider spreads associate with less-adverse settlement residuals on this date, but unadjusted slope signs depend on fixture omissions; no stable liquidity markup is established.

## Completion and denominator checks

Entry/risk batch and spread calibration are complete. Recorded input/code hashes match, and compensation +residual equals realized for every component mean and every regression coefficient. Proof and reproducible inspection script: `runs/morning_research_20260908/july9_spread_capacity_review/`.

The entry/risk common intersection is **35,643 prints**, with sell-all net **−$800,774.479900**. Common spread analysis has **30,329 moneyline prints**, $6,847,764.74 face and **−$897,265.182900** net. The narrower moneyline cohort can lose more than the broader common set; other market families contribute positively to their difference. Neither is the 275,489-print native universe.

There are 34,692 eligible moneyline feature candidates;116 uncovered timestamps,27 without covered history,10crossed pairs and 3 without prior Kalshi states leave 34,536 feature-covered prints. Common model coverage removes another 4,207. Kalshi-available and common comparisons must not be conflated. All common outcomes are known;27 overlapping fixtures and effective weighted count~1,563 do not imply independent outcomes.

## Compensation and residual

Quantity-weighted cents per payout contract: compensation=100×(price −fair −maker fee/quantity), residual=100×(fair −settlement), realized=their sum. The opposite-team widths are descriptive leg-price proxies, not executable combo spreads or measured order-book depth.

| Common model | Compensation c | Residual c | Realized c |
|---|---:|---:|---:|
| exchange_blend_equal | -0.281 | -12.822 | -13.103 |
| exchange_blend_pm75 | -0.241 | -12.862 | -13.103 |
| kalshi | -0.362 | -12.741 | -13.103 |
| polymarket | -0.201 | -12.902 | -13.103 |

| Width/specification | Model | Compensation slope | Residual slope | Net slope | Net fixture-deletion range |
|---|---|---:|---:|---:|---|
| raw/spread_only | exchange_blend_equal | +0.144 | +6.326 | +6.469 | -1.809 to +8.920 |
| raw/price_and_leg_count | exchange_blend_equal | +0.018 | +6.811 | +6.829 | +0.760 to +8.811 |
| fee_expanded/spread_only | exchange_blend_equal | +0.058 | +1.690 | +1.748 | -0.913 to +2.496 |
| fee_expanded/price_and_leg_count | exchange_blend_equal | +0.019 | +6.436 | +6.455 | +0.254 to +8.345 |
| raw/spread_only | exchange_blend_pm75 | +0.146 | +6.323 | +6.469 | -1.809 to +8.920 |
| raw/price_and_leg_count | exchange_blend_pm75 | +0.035 | +6.794 | +6.829 | +0.760 to +8.811 |
| fee_expanded/spread_only | exchange_blend_pm75 | +0.056 | +1.692 | +1.748 | -0.913 to +2.496 |
| fee_expanded/price_and_leg_count | exchange_blend_pm75 | +0.035 | +6.420 | +6.455 | +0.254 to +8.345 |
| raw/spread_only | kalshi | +0.139 | +6.330 | +6.469 | -1.809 to +8.920 |
| raw/price_and_leg_count | kalshi | -0.017 | +6.846 | +6.829 | +0.760 to +8.811 |
| fee_expanded/spread_only | kalshi | +0.060 | +1.688 | +1.748 | -0.913 to +2.496 |
| fee_expanded/price_and_leg_count | kalshi | -0.014 | +6.470 | +6.455 | +0.254 to +8.345 |
| raw/spread_only | polymarket | +0.148 | +6.321 | +6.469 | -1.809 to +8.920 |
| raw/price_and_leg_count | polymarket | +0.052 | +6.776 | +6.829 | +0.760 to +8.811 |
| fee_expanded/spread_only | polymarket | +0.055 | +1.693 | +1.748 | -0.913 to +2.496 |
| fee_expanded/price_and_leg_count | polymarket | +0.052 | +6.403 | +6.455 | +0.254 to +8.345 |

Slopes measure cents/contract per additional 1c summed leg width. Raw net slopes are +6.469 unadjusted and +6.829 adjusted; unadjusted deletion range crosses zero(−1.809,+8.920), adjusted stays positive(+0.760,+8.811). Fee-expanded net slopes are +1.748/+6.455; unadjusted again crosses zero(−0.913,+2.496), adjusted stays positive(+0.254,+8.345). Controls include traded price and categorical leg count, which can generate mechanical or selection relationships. Net slopes are dominated by residuals, not compensation; adjusted K compensation is negative in both measures. Full model-specific slopes/ranges are retained above and in verification.json.

The overall residual is sharply adverse despite positive within-cohort width slopes. Positive slopes do not imply wider prints are profitable. Deletion ranges are influence diagnostics, not confidence intervals; no IID p-values or causal toxicity claim is justified. Compare pooled exact sufficient statistics and date/fixture heterogeneity, not averaged daily slopes. July 5's negative raw slopes and July 7's positive slopes already show instability.

## Entry filters at observed prices

| Model | ≥0c unlimited net | ≥0.3c/combo net | ≥0.3c/leg net | Per-leg prints |
|---|---:|---:|---:|---:|
| kalshi | $-97,876.63 | $13,485.26 | $38.36 | 89 |
| exchange_blend_equal | $-84,032.25 | $11,057.52 | $9,469.39 | 98 |
| exchange_blend_pm75 | $-58,920.57 | $24,219.66 | $9,674.53 | 130 |
| polymarket | $-54,542.00 | $64,769.27 | $11,234.86 | 272 |

All zero-edge selections lose; all 0.3c/combo selections gain. K/equal 0.3c/combo remain positive after every single-fixture omission(minima +$3,911/+$397), but PM75/PM can flip(minima −$6,988/−$3,838). Every 0.3c/leg selection is positive overall but can flip after one fixture omission; K's +$38 is especially small. Common sell-all remains negative after every omission(range −$917,515 to −$33,252).

The hurdle is net of maker fees.0.3c/leg means 0.6–1.2 c per 2–4-leg combo contract. These are observed-price print selection tests, not repriced RFQs or demonstrated acceptance probabilities.

## Funded capacity at 0.3c/combo

Each scenario starts with $10k. Baseline underlying/combo/fixture limits:$100/$100/$250; balanced1000:$1,000/$1,000/$2,000; capital-only:$10k per bucket. Full print size is accepted or rejected; no ticket cap or partial resizing. Only actual settled gains finance later trades.

| Model | Baseline net / peak cash | Balanced 1000 net / peak cash | Capital-only net / peak cash |
|---|---:|---:|---:|
| kalshi | $68 / $740 | $-77 / $5,073 | $-2,124 / $9,999 |
| exchange_blend_equal | $-36 / $665 | $524 / $5,372 | $1,932 / $10,651 |
| exchange_blend_pm75 | $33 / $947 | $-162 / $6,216 | $-959 / $11,938 |
| polymarket | $35 / $992 | $-689 / $7,476 | $7,473 / $15,123 |

Balanced 1000 is profitable only for equal blend. Capital-only is positive for equal/PM, negative for K/PM75; greater deployed capital does not consistently improve outcomes. PM capital-only peak exceeds $15k because actual settled gains can be recycled: initial $10k is not a permanent hard cash-exposure ceiling. Scenario results are separate portfolios, not additive returns. Review continuous multi-date drawdowns and eventual-versus-settled P&L before choosing risk caps.

## Research implication

Retain the fixed grids rather than promote a day-specific winner. July 9 supports some separation between zero-edge and 0.3c/combo selection on this date, but fixture sensitivity and mixed capacity effects prevent claiming stable model superiority. Historical fee/source assumptions remain inherited unverified scenarios; no production policy is changed.

Sources: `dated_fee_primary/2026-07-09/{entry_sweep,risk_capacity}/{manifest,summary}.json` and `spread_v2/2026-07-09/{feature_manifest.json,calibration/manifest.json,calibration/results.json}`. All outputs were complete before inspection. No provider calls, August outcomes, plots, frozen-source edits or surviving jobs.
