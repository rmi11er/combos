# Durable maker ownership and cumulative fills

MakerOwnership now stores immutable exchange/order-to-intent bindings in the
execution journal. Registration requires a matching private quote, matching maker
order, and a previously dispatched create-quote intent. Quote reconciliation,
ownership insertion and the audit event share a transaction; failed intent matching
leaves no ownership record. Conflicting bindings cannot silently replace ownership.

Cumulative reconciliation reads the existing deduplicated account-fill evidence,
checks the bound market/account/exchange/direction, enforces maker status and the
NO limit, and aggregates actual quantities, fees and principal. It reports three
states: counts_match, fill_evidence_incomplete, or order_snapshot_behind_fills.
The latter distinguishes an ordinary asynchronous snapshot race from missing fills.
Cumulative quantity above the bound order maximum is an error.

Forty-one focused tests pass, including duplicate fill-page ingestion, durable
restart, cumulative overfill, missing dispatch, and no fills yet. This is synthetic
execution evidence; there has been no strategy quote submitted to validate private
accepted-side/size/time semantics. Caller-supplied order fill counts still require
fresh authenticated snapshot provenance in the end-to-end reconciler.

No result releases cash or risk. Matching fill counts alone does not establish a
terminal order or settled balance, and an unfilled canceled remainder must not be
confused with a settled filled position. Next connect fresh terminal-order evidence
and account/settlement reconciliation to the persistent hold lifecycle.

Implementation: src/combos/execution_ownership_store.py.
Tests: tests/test_execution_ownership_store.py and existing ownership/fill/quote tests.
Historical collection and validation supervisors were verified live; four August
dates remain pending at this check.
