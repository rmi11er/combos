# Persistent creator markout evidence

Added a standalone bounded importer, `scripts/import_creator_evidence.py`, backed
by `scripts/creator_evidence_store.py`. A plan can include multiple completed or
currently written markout databases. Each read uses a read-only SQLite transaction
and sees only committed labels. The destination uses WAL/FULL durability and a
single-process lock in the CLI. Import batches are atomic per source.

Evidence is keyed by source identity, decision sequence and horizon. Original
payloads, creator/RFQ IDs, mapped fixtures, valuation/computation times and first
observation time are retained. Changed or disappeared imported labels fail the
import; mapping/source identity changes also fail. Unknown horizons, unsupported
statuses, missing fixtures and observed marks without creator IDs are rejected.
Pending horizons remain in their source worker and are not fabricated as labels.

Publication is governed by committed destination-row visibility. `first_seen_at`
records importer observation time, not original trade time or exact commit time.
Each pass reports a commit-return diagnostic. Historical imports are therefore
not backdated into a live creator decision timeline. This importer adds no creator
policy events and does not adapt labels into the old CreatorService schema yet.

Imported both completed captures: 5,079 labels, consisting of 4,376 observed and
703 unavailable. Restart imported zero new labels. Every stored row, including
its first-seen time, retained the same hash. Original import receipt and restart
verification are preserved in `runs/nfl_persistent_creator_evidence_20260909`.

Six tests passed: persistent restart/deduplication, changed/deleted source labels,
injected second-row transaction failure and rollback, invisibility of uncommitted
source rows, mapping mismatch, and missing observed creator. Real completed-data
imports and restarts passed; concurrent production following remains to be tested
alongside a future capture. This is an evidence store, not a toxicity classifier.

The grouped-review workflow currently reads source markout databases. A further
adapter should let it consume this store with explicit as-of availability and
model/source stratification before any policy decision uses the evidence.
