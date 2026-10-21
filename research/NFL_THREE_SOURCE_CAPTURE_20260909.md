# Fresh three-source research capture

A 90-second read-only capture completed with all mapping pricing blocks retained.
Runtime, Pinnacle collector, creator/shadow drains, archive and review export all
exited successfully. Account usage was reconciled before capture (32 requests
reported used); three raw Pinnacle snapshots were saved. No quotes or orders were
submitted, and no hypothetical acceptance events were invented.

| Measurement | Result |
|---|---:|
| Mapped markets observed by each exchange | 454 |
| Markets with positive two-sided Kalshi depth at least once | 454 |
| Markets with positive two-sided Polymarket depth at least once | 454 |
| Active Kalshi / Polymarket observations | 3,005 / 3,295 |
| Pinnacle raw snapshots | 3 |
| RFQ decisions | 44,533 |
| Decisions reaching payoff-review exclusion | 642 |
| Missing mapping / same-fixture exclusions | 182 / 77 |
| Processing-backlog skips | 23 |

Pinnacle's 1,362 normalized records are inactive: 795 payoff-review exclusions and
567 selector exclusions. Seeing a record for all 454 keys is not three-source
pricing coverage; the adapter emits excluded observations as well as usable ones.
The two-sided exchange counts mean observed at least once, not continuously fresh
or simultaneous depth at every RFQ.

Local source-event receipt to decision-event receipt latency across every decision:
median 117ms, p95 180ms, p99 202ms, maximum 2.125s, no negative intervals.
The 23 backlog skips have source times within a 44ms interval at capture shutdown.
This should be investigated as shutdown/draining behavior before interpreting it
as steady-state overload. Most decisions exit on scope/mapping checks, so these
metrics do not certify full fair computation, correlation solving or live quote
network latency.

The completed artifact is `runs/nfl_three_source_capture_20260909`:
prepared input hashes, source freeze, event database, three raw snapshots, archived
events, review export, `readiness.json` and `latency_review.json` are retained.
The capture is finished; it is not a running continuous shadow service.

Next use this causal capture for paired candidate pricing diagnostics, retaining
actual exchange depth and explicit Pinnacle payoff/liquidity assumptions. Then run
a sustained capture with those decisions enabled, rather than treating this
scope-rejection throughput measurement as launch readiness.
