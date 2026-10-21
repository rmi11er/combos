# Full three-source capture with targeted recovery

The requested 120-second capture completed. Runtime and Pinnacle exited zero,
post-capture drains/archive/export succeeded, and the only venue resets were
startup/shutdown. Four Pinnacle snapshots and 52,151 RFQs were saved. Provider usage
was reconciled at 41 before the run. No orders were submitted.

Among 827 mapped candidates, 462 (55.9%) had all required exchange legs usable and
435 (52.6%) were three-source scenario-priced: 239 two-leg, 124 three-leg, 72
four-leg. The earlier captures priced 30.6% and 43.5%; different flows, durations
and market states prevent causal attribution. PM coverage is materially better
in this sample descriptively: 2,186/2,321 leg occurrences usable, with 88 old-age,
45 not-observed and two inactive. Kalshi has 388 old-age leg occurrences and is
now the larger exchange coverage issue. Original first-failure counts include
241 Kalshi-age exclusions, 97 exchange-coverage exclusions, 50 missing exact
Pinnacle selectors, two inactive/changed Pinnacle outcomes and two pre-Pinnacle
RFQs. These sum with 435 priced to 827, without double counting.

Twenty-four PM checks produced 2,350 book verifications. There were 19 distinct
quarantine episodes: 12 recovered (median 23.09s, maximum 30.40s), seven unresolved
at capture end. Unresolved durations are censored, not recovery times. No global
feed reconnect was needed. Median local receipt-to-decision was 116.6ms, p99
200.2ms, maximum 2.151s. There were 33 processing-backlog skips whose RFQ receipts
span 84ms; examine their shutdown timing separately. These timings are the blocked
shadow path, not complete three-source quote-compute latency.

All 435 priced RFQs use captured zero maker fees and clear published creator state.
At point fair plus 0.3c/combo:

| Limits | No-fill 3s expiry admissions / peak holds | All-admitted-fill retention admissions / peak holds |
|---|---:|---:|
| Original $100/$100/$250 | 228 / $375 | 42 / $710 |
| $1k each | 406 / $1,617 | 98 / $3,971 |
| $2k each | 420 / $3,187 | 128 / $8,204 |

Capacity is not acceptance or profitability. Payoff/independence, Pinnacle stake
conversion, account precision and sampled market-grid assumptions still apply.
These runs executed the reusable pricing/coverage/terms/capacity workflows; the
new output has not yet received an independent full-row accounting audit.

Next apply demand scheduling to Kalshi refresh; investigate native Pinnacle
selector loss; run sustained candidate pricing and audit lifecycle/latency. Keep
risk calibration anchored to larger historical partitions, not this short sample.
The historical supervisors remain live, with five August dates pending.

Artifacts: runs/nfl_rebuild_three_source_capture_20260909 and
runs/nfl_rebuild_{rfq_scenarios,rfq_terms,rfq_coverage,rfq_capacity,operations}_20260909.
Reusable operational workflow: scripts/capture_operational_scorecard.py.
