# Concurrent NFL pricing and markout audit

The 180-second capture, 270-second pricing worker and 285-second markout worker
all exited successfully. No orders were submitted. Independent closed-database
audits cover the recorded source prefix, decision identity, horizon census,
source cutoffs and computation/commit timing. Fair arithmetic and cross-venue
payoff equivalence were not independently rederived by these audits.

All 65,995 RFQs through source sequence 259,525 have decisions. There are 687
priced candidates: 322 two-leg, 225 three-leg and 140 four-leg. Research risk
accounting admitted 78 reservations and rejected 609; these are assumed-fill
scenarios, not actual quote acceptances. Priced receipt-to-commit latency was
76.53ms median, 141.02ms p99 and 149.92ms maximum. All decisions have commit
receipts; none of the priced decisions took more than two seconds.

The markout ledger has 1,719 labels and 342 pending horizons, exactly 687 times
three. Of the labels, 1,348 have a fair and 371 are unavailable. Source cutoffs
and entry identities reconcile. Horizon-to-commit-return lag was 65.40ms median,
143.10ms p99 and 167.77ms maximum. Commit-return timestamps are diagnostic;
publication is governed by committed-row visibility.

| Horizon | Observed | Unavailable | Pending | Mean adverse move, cents |
|---|---:|---:|---:|---:|
| 10 seconds | 540 | 128 | 19 | +0.001889 |
| 30 seconds | 460 | 127 | 100 | +0.000357 |
| 60 seconds | 348 | 116 | 223 | +0.001008 |

Positive moves are adverse for a YES seller. These unweighted, same-model marks
include freshness-driven weight changes. Shared fixtures and repeated leg sets
make observations dependent. The short overnight window cannot establish
profitability, acceptance rates, source sharpness or creator toxicity.

Unavailable labels comprise 366 exchange-candidate coverage failures and five
Pinnacle availability failures. The former currently combines missing Kalshi
state with missing/inactive/zero-depth/stale Polymarket candidates. The latter
includes the check that delivery availability must precede valuation. Next
diagnostic work should expose those subreasons and determine whether any valid
prior snapshot is being replaced by a snapshot unavailable at the horizon.
Pending horizons remain pending because source collection ended; they are not
lost decisions and should not be filled with prices observed after the horizon.

Both workers were restarted with unchanged input and source identities. Every
row of the pricing checkpoint, decisions and commit receipts, and the markout
checkpoint, consumed-input hashes, labels, pending queue and commit receipts
remained identical. Original summaries and table hashes are retained.

Evidence:
- runs/nfl_live_markout_pricing_audit_20260909/verification.json
- runs/nfl_live_markout_audit_20260909/verification.json
- runs/nfl_live_markout_audit_20260909/horizon_diagnostics.json
- runs/nfl_live_markout_worker_20260909/restart_verification.json

Reusable workflows: scripts/audit_live_scenario_worker.py,
scripts/audit_markout_worker.py and scripts/summarize_durable_markouts.py.

Historical collection also resumed after the single August 24 rate-limited
exchange job succeeded using existing successful caches. Attempts were retained,
with the supplemental invocation explicitly recorded. All validation pins were
verified before relaunching batch/recovery/validation supervision under
runs/aug24_rate_limit_recovery_20260909/resumed. August 24 replay and report
completed; held-out outcomes were not inspected to choose parameters.
