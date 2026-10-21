# Demand-prioritized Kalshi snapshots and Pinnacle selector audit

Kalshi snapshot refresh now optionally prioritizes legs from scoped RFQs received
in the preceding 60 seconds. Demanded books become eligible after eight seconds
without an update, before the 15-second pricing age limit; other books retain the
15-second quiet threshold. Batch spacing and request budgets remain unchanged,
and exploration capacity uses the same bounded selector as PM. Sending a request
does not change the last-observed time. Settings are shadow-only and default off:
kalshi_snapshot_refresh.demand_priority=true, demand_refresh_seconds=8.

Twenty-two scheduler/recovery tests pass. A 35-second Kalshi-only live capture
completed six batches (1,26,100,100,100,100 books), with 427 observed snapshot
responses, no pending selected keys at capture end, and maximum selection-to-
snapshot receipt 374ms. Every demanded selection had a prior RFQ mentioning that
leg. Response pairing is by market ticker after request selection, not a claimed
exchange command acknowledgment. No Pinnacle requests or exchange orders occurred.
The combined three-source priceability effect is not yet measured.

Separately, all 50 missing-exact-selector RFQs in the preceding full capture were
traced to their contemporaneous Pinnacle snapshots. They contain 88 missing leg
occurrences: LAC spread 6.5 (40), JAC spread 4.5 (38), CIN/TB total 45.5 (4), LAR/SF
total 42.5 (3), and three other lines once each. Every status is exact_line_missing,
not ambiguous. Snapshots match 265/267/265/267 of 454 configured exchange mappings.
The catalog matcher also rejects integer lines requiring a push model; this does
not authorize substituting one for a missing half-point line. The audit establishes
exact-match absence under our matcher, not that the provider can never supply those
lines. A provider endpoint/alternate-line availability review is still warranted.

Artifacts: runs/kalshi_demand_refresh_20260909 and
runs/nfl_rebuild_selector_audit_20260909. Reusable selector audit:
scripts/pinnacle_selector_capture_audit.py. Prechange sources are archived.
