# July 21 entry and risk review

Both stages completed and all certified output hashes reconcile. These are separate observed-price, full-print hypothetical portfolios; no RFQ price elasticity is measured. Historical fee scenario and source assumptions remain unverified. All models use the same 34,742-print common cohort.

| Model | 0c | 0.3c/combo | 0.3c/leg |
|---|---:|---:|---:|
| kalshi | $23,492.93 | $21,253.26 | $1,022.76 |
| exchange_blend_equal | $52,719.83 | $23,170.97 | $871.45 |
| exchange_blend_pm75 | $132,760.59 | $24,680.54 | $320.51 |
| polymarket | $184,351.72 | $74,211.28 | $-4,652.80 |

| Model | Scenario | Net P&L | Peak cash |
|---|---|---:|---:|
| exchange_blend_equal | baseline | $62.92 | $478.78 |
| exchange_blend_pm75 | baseline | $-17.91 | $615.87 |
| kalshi | baseline | $71.48 | $396.83 |
| polymarket | baseline | $88.24 | $1,009.80 |
| exchange_blend_equal | balanced_1000 | $-66.98 | $3,091.79 |
| exchange_blend_pm75 | balanced_1000 | $117.02 | $4,302.03 |
| kalshi | balanced_1000 | $80.69 | $2,588.59 |
| polymarket | balanced_1000 | $-581.20 | $6,391.22 |
| exchange_blend_equal | capital_only | $1,798.09 | $9,999.30 |
| exchange_blend_pm75 | capital_only | $1,965.19 | $11,127.22 |
| kalshi | capital_only | $1,212.04 | $7,304.22 |
| polymarket | capital_only | $4,797.97 | $12,299.37 |

Baseline underlying/combo/fixture limits are $100/$100/$250; balanced1000 uses $1,000/$1,000/$2,000; capital-only uses $10k per bucket. Each scenario starts with $10k; only actual settled gains finance later trades. Daily accounts are not added to make a continuous account. Spread follow-through and pooled risk selection remain pending. No live parameters changed.

On this date, every zero-edge selection earns more than its 0.3c/combo counterpart; PM turns negative at 0.3c/leg. This contrasts with losing zero-edge variants on July7/9. Balanced1000 also worsens PM relative to baseline despite greater cash use. Neither a universally wider hurdle nor a uniformly larger risk cap is supported by these daily results; evaluate pooled chronology and game concentration.
