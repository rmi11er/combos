# PM75 loose offset configuration replay

## Configuration replayed

| Parameter | Value |
|---|---|
| Starting capital | $10,000 |
| Per-ticket maximum gross liability | $250 |
| Contract / combo / fixture caps | $500 / $500 / $1,000 |
| Moneyline offset | Enabled for exact full-game moneyline fixture/team matches |
| Offset ticket-cap floor | $50 research floor; actual loose cap is $250 |
| Edge charge | 0.15¢ per contract after maker fee |
| Fair-value replay | Archived `exchange_blend_pm75` challenger |
| Marginal reserve | 0 |
| Execution assumption | Hypothetical full fills at saved public prints |

The named shadow configuration is [`offset_pm75_loose_shadow_20260909.json`](../config/offset_pm75_loose_shadow_20260909.json). The executable replay is [`run_offset_pm75_loose_config.py`](../analysis/run_offset_pm75_loose_config.py), with complete output in [`offset_pm75_loose_config_results.json`](../analysis/offsetting_allocation_v1/offset_pm75_loose_config_results.json).

## Results

Sharpe is settlement-day P&L divided by the $10,000 starting capital. It is descriptive only: five NFL and 23 MLB active settlement days are available.

| Sport | Rows after model/edge filter | Accepted | Peak committed cash | Peak offset credit | Accepted edge | Retrospective P&L | Daily Sharpe | Max drawdown |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| NFL | 2,844 | 86 | $962 | $0 | $10 | -$596 | -0.689 | -$719 |
| MLB | 19,602 | 2,106 | $9,829 | $381 | $802 | $17 | 0.001 | -$3,359 |

## Read-through

- The loose caps do what intended operationally: MLB uses almost the full $10,000 capital pool and admits 2,106 tickets.
- The observed PM75/0.15¢ configuration does **not** validate economically in this replay. MLB retrospective P&L is approximately flat despite $802 of recorded ex-ante edge, with a roughly $3.4k settlement drawdown. NFL is negative.
- This is a useful refutation of the claim that lowering the hurdle to 0.15¢ and using PM75 automatically improves realized performance. It suggests the edge charge is below the current model/selection error or that the public-print fill assumption is too optimistic.
- The saved historical PM75 rows are a 75% Polymarket / 25% Kalshi challenger. They do not implement the desired liquidity-weighted Kalshi/Polymarket/Pinnacle model because verified historical Pinnacle fair values were not present in these replay rows. The three-source model remains the forward implementation target.

Therefore this configuration is locked as a **shadow research default**, not promoted as a live economic limit. Keep the $500/$500/$1,000 capacity and $250 ticket structure for further testing, but retain a promotion gate on the 0.15¢ edge charge and PM75 model until a causal three-source replay and forward markout study pass.
