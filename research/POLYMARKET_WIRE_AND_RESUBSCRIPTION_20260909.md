# Independent wire replay and fresh subscription

An independent Decimal implementation, without importing `Books` or its level
parser, rebuilt all affected tokens directly from raw `book` snapshots and absolute
`price_change` sizes. It reproduced all 24 REST mismatches exactly. Across the 36
differing-level occurrences, eight levels last came from a delta, 16 from a snapshot,
and 12 were absent from the local book since its snapshot. These counts include
repeated checks of the same token/level.

This supports the recorded wire stream being inconsistent with the compared REST
responses, rather than a discrepancy unique to the production reconstruction.
It does not prove upstream completeness, explain why the messages differ, or
exclude an interpretation issue shared by both implementations.

A subsequent fresh WebSocket subscription for all 12 affected tokens was compared
with one new REST batch while updates continued to be received. All 12 full ladders
matched both before and after the request, with no intervening updates. All 12
snapshot certificates passed. Native timestamps remained 26–169 seconds old.
Because time elapsed and markets could change between experiments, this is evidence
that a fresh subscription can produce agreement, not a controlled proof that the
act of resubscribing alone fixed each earlier discrepancy.

Artifacts:
- `runs/polymarket_wire_audit_20260909`: independent reconstruction and exact token set.
- `runs/polymarket_resubscription_check_20260909`: selection, raw WS/REST, ladders and certificates.

Reusable workflows are `audit_polymarket_wire.py` and the optional `--tokens` input
to `polymarket_snapshot_check.py`. No live pricing limits, source weights or orders
changed. One public REST request was made for the new subscription comparison.

Next implement bounded resynchronization on confirmed depth mismatch: invalidate
the local pricing state, request a fresh stream snapshot through a reviewed
subscription operation, and require successful reconstruction/verification before
reuse. Do not silently patch individual stale levels from an asynchronous REST view.
