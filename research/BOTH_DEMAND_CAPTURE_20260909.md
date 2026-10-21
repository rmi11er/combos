# Both exchanges prioritize RFQ demand

The full 120-second combined capture completed with runtime and Pinnacle exit zero,
no global reconnects beyond lifecycle startup/shutdown, and successful drains,
archive and export. It saved 47,937 RFQs and four Pinnacle snapshots. Of 864 mapped
candidates, 694 (80.3%) were three-source scenario-priced: 303 two-leg, 209 three-leg,
182 four-leg. Other first failures: exchange candidate missing132, exact Pinnacle
selector missing30, Kalshi age6, Pinnacle inactive/changed1, Pinnacle not yet available1.
These reconcile to 864. Previous capture priced435/827 (52.6%) with241 Kalshi-age
failures. The differing flow and market state prohibit causal effect estimates.

Median local receipt-to-decision was119.6ms, p99 200.6ms, maximum254.4ms, with no
processing-backlog skips. Timing remains blocked-path latency, not full pricing
latency. PM recorded2,335 verified comparisons;24 quarantine episodes recovered,
11 remained unresolved. Median recovered duration20.14s, maximum45.50s. Quarantine
remains a significant per-market downtime source despite healthy feed continuity.

All694 priced RFQs match zero-maker-fee series metadata and clear published creator
state. At point+0.3c/combo, capacity scenarios:

| Limits | No-fill3s expiry: admissions / peak holds | All-admitted-fill retained: admissions / peak holds |
|---|---:|---:|
| Original100/100/250 | 277 / $338 | 35 / $719 |
| $1k each | 576 / $1,885 | 106 / $4,673 |
| $2k each | 641 / $4,535 | 140 / $8,718 |

Neither scenario estimates acceptance or P&L. All research payoff, Pinnacle stake
units, sampled grid and account precision assumptions remain. These runs need the
independent full-row accounting audit previously applied to the smaller capture.

Two budget-accounted GET odds fixture probes did not recover the absent LAC6.5 or
JAC4.5 lines. The docs do not specify an alternate-line expansion switch; see
PINNACLE_FIXTURE_ENDPOINT_PROBE_20260909.md. No automatic fixture fallback added.
The unused prepared directory nfl_both_demand_capture_20260909 was superseded
before capture because its Kalshi request budget was only8. The executed full
capture used24 for both refreshers, with the same fresh account receipt.

Next move beyond short acquisition probes: reusable candidate pricing at arrivals,
full-compute latency, causal state/risk/creator audit and sustained collection.
Resolve exact payoff/limit-unit/account evidence before live promotion. Historical
collection and frozen validation supervisors remain active.

Artifacts: runs/nfl_both_demand_full_capture_20260909 and
runs/nfl_both_demand_{scenarios,terms,capacity,operations}_20260909.
