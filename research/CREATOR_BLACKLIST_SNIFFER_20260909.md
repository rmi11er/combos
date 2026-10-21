# Separate creator blacklist sniffer

Added `scripts/creator_blacklist_sniffer.py` and an append-only SQLite review log.
It reads only committed, as-of-available observed labels from the persistent
creator evidence store. Each run records the source hash, thresholds and
per-creator evidence references. It never edits the evidence store, submits an
exchange request or applies an automatic sanction.

The first run reviewed 5,718 observed labels across 249 creators. No creator
met the review threshold. The largest 60-second RFQ burst was 174 labels; the
largest observed leg count was four, matching the current production scope; no
creator exceeded the short-horizon adverse-move criterion in the captured
sample. The largest behavior score was 3 (burst/monitor), below the review
threshold of 5. This is a small quiet-window sample and should not be read as
evidence that toxic flow is absent.

Current signals:

- excessive leg count (default five or more): +3;
- RFQ burst (default 50 labels in 60 seconds): +3;
- repeated 30-second adverse move of at least 0.3¢ on at least 20 labels and
  70% of that horizon: +4;
- score 5 or more: `review`; otherwise `monitor`.

The implementation preserves each run and the first 500 RFQ references per
creator. Thresholds are parameters and must be frozen before an OOS analysis;
they were not fitted to P&L. Short-horizon fair movement can arise from
freshness/weight changes, so the sniffer should be combined with venue-price
markouts and actual fill-conditioned evidence before a creator is blacklisted.

Artifacts:

- `runs/nfl_persistent_creator_evidence_20260909/blacklist.sqlite`
- `runs/nfl_persistent_creator_evidence_20260909/blacklist_run_20260909.json`

Two focused tests pass for burst/pickoff scoring and idempotent append behavior.

`scripts/run_creator_blacklist_sniffer.py` provides the separate bounded polling
process for live shadow use. It reads the evidence database in a read-only
transaction, appends a new source-hashed review run, and writes a supervisor
status file. A one-second supervisor smoke test completed successfully against
the persistent store; it created no sanctions and submitted no orders.
