# As-of creator evidence reviews

The persistent importer now writes an availability receipt only after committing
the primary evidence batch. `available_by` is a conservative timestamp proving
that the evidence had committed by that time; it is not the trade time or the
pre-commit observation timestamp. Reviews require that receipt and a cutoff no
earlier than `available_by`.

If receipt insertion fails after evidence commit, the evidence remains stored
but is excluded from as-of reviews. A later import confirms it at the later time,
without backdating. Existing rows migrated to the receipt schema were confirmed
at migration time, not at their earlier `first_seen_at` value.

Added `scripts/review_creator_evidence_asof.py`. It reads one consistent committed
database snapshot, applies the availability cutoff, and groups observed labels
using the existing fixture-dependence review. Unavailable status counts are
retained. Immutable source identities form separate strata: two runs are not
automatically pooled merely because the same creator appears in both.

Ten focused importer/grouping tests passed, including explicit pre/post-commit
cutoffs and a real SQLite trigger failure on receipt insertion. On the populated
store, a cutoff before its first receipt exposes zero labels; a cutoff after the
last exposes all 5,079. The after report contains 525 source-stratified
creator/horizon reviews across two source identities. This differs from the
earlier pooled 456 reviews intentionally; no source compatibility was assumed.

Artifacts in runs/nfl_persistent_creator_evidence_20260909:
- evidence.sqlite: persistent labels and availability receipts
- asof_before.json: empty review before availability
- asof_after.json: source-stratified review after availability

No creator sanctions or live order actions were added. Concurrent operation
alongside a new capture, model-compatible pooling, and evidence-backed policy
decisions remain separate requirements.
