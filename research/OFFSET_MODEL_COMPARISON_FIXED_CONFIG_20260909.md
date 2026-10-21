# Fair-value model comparison under fixed offset policy

All rows use the same policy:

- 0.15¢ minimum edge after maker fee
- `$500 / $500 / $1,000` contract/combo/fixture limits
- `$250` maximum gross ticket liability
- exact full-game moneyline offsetting
- $10,000 capital and zero marginal reserve

Only the archived fair-value model changes. Sharpe is settlement-day P&L divided by starting capital; it is descriptive for this short sample.

| Model | Sport | Candidates | Accepted | Peak committed | Ending P&L | Max drawdown | Daily Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|
| Kalshi | NFL | 2,122 | 51 | $684 | -$49 | -$141 | -0.097 |
| Polymarket | NFL | 3,948 | 74 | $844 | -$514 | -$523 | -0.983 |
| Equal blend | NFL | 2,245 | 74 | $842 | -$130 | -$230 | -0.254 |
| PM75 blend | NFL | 2,844 | 86 | $962 | -$596 | -$719 | -0.689 |
| Kalshi | MLB | 9,777 | 2,647 | $10,000 | **$6,766** | -$1,618 | **0.408** |
| Polymarket | MLB | 38,773 | 2,668 | $10,000 | -$1,023 | -$4,395 | -0.075 |
| Equal blend | MLB | 8,774 | 1,778 | $8,793 | $1,046 | -$2,113 | 0.084 |
| PM75 blend | MLB | 19,602 | 2,106 | $9,829 | $17 | -$3,359 | 0.001 |

## Learning

Under this fixed low edge charge and loose capacity policy, the **Kalshi-only model is clearly strongest in the saved MLB replay**. PM75 does not inherit that result: it admits a similar number of tickets but realizes essentially no P&L, while Polymarket-only loses materially. Equal blend is positive but below Kalshi-only.

The NFL sample is uniformly negative and small; it does not support selecting a model for NFL. The requested liquidity-weighted Kalshi/Polymarket/Pinnacle model is not actually represented in this historical comparison because the saved replay rows do not contain verified causal Pinnacle fair values. PM75 is only the archived 75% Polymarket / 25% Kalshi challenger.

This **refutes** the claim that PM preference plus a 0.15¢ hurdle is automatically better than Kalshi-only pricing. It supports retaining the loose offset-aware limits as a capacity candidate, but the fair-value model and edge charge remain the principal unresolved economic risks. No live promotion is enabled.

Machine-readable output: [`offset_models_fixed_config.csv`](../analysis/offsetting_allocation_v1/offset_models_fixed_config.csv). Executable: [`sweep_offset_models_fixed_config.py`](../analysis/sweep_offset_models_fixed_config.py).
