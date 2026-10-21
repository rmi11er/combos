# Three-source scenarios at actual RFQ arrivals

The causal replay accounts for all 43,003 captured RFQs. It retains the intended
2–4-leg, distinct-fixture, pregame, mapped non-player scope. Each Pinnacle snapshot
rebinds exact catalog selectors when it becomes available; completed-period payoff
enumeration is cached by selector identity. No later source prices fill missing
observations. Polymarket verification evidence is consumed in event sequence;
Kalshi refresh snapshots use the existing captured observations.

Of the 545 RFQs that reached the original mapping/payoff exclusion, 167 have usable
three-source scenario inputs:

| Legs | Priced RFQs |
|---|---:|
| 2 | 106 |
| 3 | 32 |
| 4 | 29 |

The other 378 are excluded by missing exchange candidate coverage (309), stale/future
Kalshi observation (60), Pinnacle not yet available (8), or missing exact Pinnacle
selector (1). This reconciles exactly to the original 545. Exclusions outside this
stage are retained individually, not sampled away.

Three hypothetical native-stake-to-USD scales (0.1,1,10) yield 501 priced scenarios.
Each assumes 1% tie probability for full-game moneylines, up to 0.5% exceptional
settlement probability with payout in [0,1], and independence across distinct games.
These are sensitivity inputs, not calibrated facts. Captured exchange depth,
fee-expanded intervals and source ages determine the actual weights. Pricing gates
in the live normalizer remain intact.

Across priced RFQs, the median point-fair range across the three unit scales is
0.087 cents per combo, maximum 1.007 cents. At the illustrative 1:1 scale, median
independent marginal upper minus point is 3.489 cents. That reserve includes the
configured fee-expanded intervals, delayed-feed protection and payoff assumptions;
it is not the extra 0.3-cent edge hurdle or a dependence-robust bound. It is currently
the larger typical pricing lever in this sample.

Actual priced leg occurrences are 414 full-game moneylines, nine spreads and one
total. Other supported families were not represented in the successfully priced
RFQs here; this run does not establish their executable opportunity.

All 501 scenario products, interval ordering and per-leg weight sums reconciled.
No quote submission, fill probability, settlement P&L or funded allocation is
inferred. Actual requested contracts/target costs are saved for subsequent sizing.
Candidate output and every exclusion are retained under
`runs/nfl_rfq_three_source_scenarios_20260909`; reusable workflow:
`scripts/rfq_three_source_scenarios.py`.

Next apply explicit quote-reference/edge scenarios to these RFQs, solve full-RFQ
target-cost quantities consistently with fees, and replay the actual risk and
causal creator policy. This will quantify quote capacity rather than mistaking
available fair values for fills.
