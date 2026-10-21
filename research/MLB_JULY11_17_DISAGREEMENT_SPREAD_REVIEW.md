# July 11 and 17 disagreement and spread diagnostics

Exploratory July development evidence; observed-price seller counterfactuals, unverified historical maker-fee scenario, no Pinnacle. August outcomes remain unread.

## July 11

Common prints: 24,774. PM-minus-Kalshi quantity-weighted Brier: -0.00064258 (negative favors PM). PM scores better in 30/31 fixture omissions. Range [-0.00096704, +0.00015210], removing mlb:26JUL111410LAAMIN and mlb:26JUL112110AZLAD respectively.

| Selection | Prints | Net seller P&L |
|---|---:|---:|
| both | 157 | $1,652.98 |
| kalshi_only | 78 | $-4,552.05 |
| neither | 23,375 | $284,911.00 |
| polymarket_only | 1,164 | $11,597.37 |

All spread component means and regression coefficients reconcile compensation + residual = realized. Slopes below are cents per payout contract per extra cent of summed leg width. Widths proxy opposite-team prices, not depth.

| Model | Width | Controls | Compensation | Residual | Net | Net fixture-omission range |
|---|---|---|---:|---:|---:|---|
| exchange_blend_equal | raw | spread_only | +0.083 | -0.303 | -0.220 | -1.736 to +1.838 |
| exchange_blend_equal | raw | price_and_leg_count | -0.031 | +0.472 | +0.441 | -1.180 to +1.446 |
| exchange_blend_equal | fee_expanded | spread_only | +0.047 | -0.673 | -0.626 | -1.532 to +0.976 |
| exchange_blend_equal | fee_expanded | price_and_leg_count | -0.030 | -1.050 | -1.080 | -3.574 to -0.014 |
| exchange_blend_pm75 | raw | spread_only | +0.098 | -0.318 | -0.220 | -1.736 to +1.838 |
| exchange_blend_pm75 | raw | price_and_leg_count | +0.015 | +0.427 | +0.441 | -1.180 to +1.446 |
| exchange_blend_pm75 | fee_expanded | spread_only | +0.046 | -0.672 | -0.626 | -1.532 to +0.976 |
| exchange_blend_pm75 | fee_expanded | price_and_leg_count | +0.013 | -1.092 | -1.080 | -3.574 to -0.014 |
| kalshi | raw | spread_only | +0.052 | -0.272 | -0.220 | -1.736 to +1.838 |
| kalshi | raw | price_and_leg_count | -0.123 | +0.564 | +0.441 | -1.180 to +1.446 |
| kalshi | fee_expanded | spread_only | +0.050 | -0.676 | -0.626 | -1.532 to +0.976 |
| kalshi | fee_expanded | price_and_leg_count | -0.116 | -0.964 | -1.080 | -3.574 to -0.014 |
| polymarket | raw | spread_only | +0.114 | -0.333 | -0.220 | -1.736 to +1.838 |
| polymarket | raw | price_and_leg_count | +0.060 | +0.381 | +0.441 | -1.180 to +1.446 |
| polymarket | fee_expanded | spread_only | +0.044 | -0.670 | -0.626 | -1.532 to +0.976 |
| polymarket | fee_expanded | price_and_leg_count | +0.055 | -1.135 | -1.080 | -3.574 to -0.014 |

[Disagreement evidence](../runs/morning_research_20260908/july11_selected_audit/disagreement.json) · [Spread and capacity verification](../runs/morning_research_20260908/july11_spread_capacity_review/verification.json)

## July 17

Common prints: 32,812. PM-minus-Kalshi quantity-weighted Brier: +0.00036590 (negative favors PM). PM scores better in 1/45 fixture omissions. Range [-0.00018131, +0.00065339], removing mlb:26JUL172138DETLAA and mlb:26JUL172005MINCHC respectively.

| Selection | Prints | Net seller P&L |
|---|---:|---:|
| both | 179 | $2,311.82 |
| kalshi_only | 12 | $-1,600.56 |
| neither | 32,279 | $-333,651.24 |
| polymarket_only | 342 | $-18,379.83 |

All spread component means and regression coefficients reconcile compensation + residual = realized. Slopes below are cents per payout contract per extra cent of summed leg width. Widths proxy opposite-team prices, not depth.

| Model | Width | Controls | Compensation | Residual | Net | Net fixture-omission range |
|---|---|---|---:|---:|---:|---|
| exchange_blend_equal | raw | spread_only | +0.087 | +1.902 | +1.989 | +0.960 to +3.314 |
| exchange_blend_equal | raw | price_and_leg_count | -0.001 | -0.422 | -0.423 | -1.715 to +1.348 |
| exchange_blend_equal | fee_expanded | spread_only | +0.047 | +1.016 | +1.063 | +0.166 to +1.555 |
| exchange_blend_equal | fee_expanded | price_and_leg_count | +0.001 | -0.366 | -0.365 | -1.793 to +1.212 |
| exchange_blend_pm75 | raw | spread_only | +0.102 | +1.887 | +1.989 | +0.960 to +3.314 |
| exchange_blend_pm75 | raw | price_and_leg_count | +0.036 | -0.458 | -0.423 | -1.715 to +1.348 |
| exchange_blend_pm75 | fee_expanded | spread_only | +0.048 | +1.015 | +1.063 | +0.166 to +1.555 |
| exchange_blend_pm75 | fee_expanded | price_and_leg_count | +0.037 | -0.402 | -0.365 | -1.793 to +1.212 |
| kalshi | raw | spread_only | +0.057 | +1.932 | +1.989 | +0.960 to +3.314 |
| kalshi | raw | price_and_leg_count | -0.074 | -0.348 | -0.423 | -1.715 to +1.348 |
| kalshi | fee_expanded | spread_only | +0.046 | +1.017 | +1.063 | +0.166 to +1.555 |
| kalshi | fee_expanded | price_and_leg_count | -0.071 | -0.294 | -0.365 | -1.793 to +1.212 |
| polymarket | raw | spread_only | +0.117 | +1.872 | +1.989 | +0.960 to +3.314 |
| polymarket | raw | price_and_leg_count | +0.072 | -0.495 | -0.423 | -1.715 to +1.348 |
| polymarket | fee_expanded | spread_only | +0.049 | +1.014 | +1.063 | +0.166 to +1.555 |
| polymarket | fee_expanded | price_and_leg_count | +0.072 | -0.438 | -0.365 | -1.793 to +1.212 |

[Disagreement evidence](../runs/morning_research_20260908/july17_selected_audit/disagreement.json) · [Spread and capacity verification](../runs/morning_research_20260908/july17_spread_capacity_review/verification.json)

## Interpretation

Source rankings reverse by date and with at least one fixture omission on each date. July 17 unadjusted width/net slopes are positive but adjusted slopes are negative with omission ranges crossing zero. Both dates have negative adjusted Kalshi compensation slopes. Wider legs do not consistently imply more compensation after these controls. Price controls can create mechanical relationships; neither specification identifies causal toxicity. Fixture omissions overlap and are influence diagnostics, not confidence intervals. Retain the predeclared pooled analysis and consensus tests before selecting liquidity surcharges.
