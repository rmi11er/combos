# Three-source shadow configuration and Kalshi-only OOS control

## Shadow configuration

The current-week MLB/NFL shadow profile is [`shadow_three_source_loose_slate_20260909.json`](../config/shadow_three_source_loose_slate_20260909.json). It specifies:

- liquidity-weighted Kalshi/Polymarket/Pinnacle fair value;
- a Kalshi-skew prior reflecting potentially stronger Kalshi taker fees;
- 30-second Pinnacle delay and 90-second maximum age;
- `$500 / $500 / $1,000` contract/combo/fixture limits;
- `$250` maximum gross ticket liability;
- exact moneyline offsetting, with a $50 policy floor;
- 0.30¢ after-fee edge hurdle and zero marginal reserve;
- pregame-only, 60-second cutoff, 2–4 legs, distinct fixtures, no props;
- creator blacklist and stale/disagreement/mapping guards before admission.

The file is shadow-only and does not authorize orders. The current NFL three-source capture has 454 observed keys, but zero active three-venue intersections; all 454 Pinnacle keys are still blocked by payoff/selector review. The configuration is therefore installed as the intended policy, while the runtime should continue to fail closed until those mappings are reviewed.

## Kalshi-only August OOS control

To isolate the Kalshi model, I replayed the 15 held-out August MLB dates (Aug 2–30) under the same loose limits, $250 ticket cap, exact offset accounting, and 0.30¢ after-fee hurdle.

| Metric | Result |
|---|---:|
| Candidate rows | 4,729 |
| Accepted tickets | 1,958 |
| Peak gross committed cash | $9,999.52 |
| Peak internal offset credit | $2,700.57 |
| Accepted recorded edge | $1,681.88 |
| Retrospective P&L | **$7,674.90** |
| Active settlement days | 33 |
| Settlement-day Sharpe | 0.230 |
| Maximum drawdown | -$3,641.13 |

Complete output is [`kalshi_august_oos_loose.json`](../analysis/offsetting_allocation_v1/kalshi_august_oos_loose.json), and the replay is [`run_kalshi_august_oos_loose.py`](../analysis/run_kalshi_august_oos_loose.py).

This is out-of-time relative to the July development tape, but it does not reproduce the frozen validation implementation's separate fixture-exclusion certificate. It remains a historical control, not live performance evidence. Public prints are treated as hypothetical full fills, and the result does not test the three-source fair value itself.
