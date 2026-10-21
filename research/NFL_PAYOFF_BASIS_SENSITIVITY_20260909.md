# Payoff basis sensitivity on saved Pinnacle prices

The review covers 253 active exact mappings in the saved September 8 snapshot:
221 completed-period binary markets and 32 full-game moneylines. Fourteen other
mapped outcomes were inactive; 187 lacked an exact selector. All 454 are accounted
for. Conditional fair uses proportional two-way de-vig for this diagnostic only.

For conditional fair q, tie probability t conditional on no exception, exception
probability e, and exchange payoff v in the exception state:

`exchange_fair = (1-e) * ((1-t)*q + 0.5*t) + e*v`.

For completed-period binary markets t=0. For moneylines the tie adjustment moves
fair toward 0.5. Unknown exception payout is bounded by [0,1]. Probability bounds
below are explicit sensitivity inputs, not empirical estimates or approved limits.

| Scenario | Sample | Median upper reserve, cents/leg | Maximum upper reserve, cents/leg |
|---|---:|---:|---:|
| Exception probability ≤0.1%, no tie adjustment | 221 binary mappings | 0.051 | 0.067 |
| Exception probability ≤0.5%, no tie adjustment | 221 binary mappings | 0.257 | 0.336 |
| Exception probability ≤1%, no tie adjustment | 221 binary mappings | 0.515 | 0.673 |
| Tie probability ≤1%, no exceptional settlement | 32 moneylines | 0.009 | 0.296 |

These are YES-side upper reserves before source weighting. A favorite's tie
adjustment is downward; the small median upper reserve in the last row does not
mean every tie adjustment is negligible. Maximum absolute adjustment there is
0.296 cents. For a selected NO leg, complement the entire interval.

The numbers can be comparable to the 0.3-cent **per combo** entry hurdle, but
leg reserves cannot simply be added and described as combo cost: source weights
and joint pricing intervene. No comparable reserve has been calibrated from these
results. The range reflects payoff assumptions only, not source-price uncertainty,
liquidity, delayed news, dependence or live fill probability.

Seven tests verify transformation, complement symmetry and input validation.
Every saved scenario row was independently recomputed using closed-form endpoints;
the full mapping census reconciles. No provider requests, live configuration changes
or historical result tuning occurred.

Reusable implementation: `src/combos/payoff_basis.py` and
`scripts/nfl_payoff_basis_sensitivity.py`. Outputs and verification:
`runs/nfl_payoff_basis_sensitivity_20260909`.

Next estimate or justify event-specific exception/tie bounds, retain their provenance,
and compare explicit shadow scenarios. Do not silently assume zero merely to clear
the current mapping gate. The three-source blending hypothesis remains untested by
this single-source sensitivity calculation.
