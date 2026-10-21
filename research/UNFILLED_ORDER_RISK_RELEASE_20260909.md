# Canceled zero-fill order risk release

Implemented `UnfilledHoldReleaser` in `src/combos/unfilled_hold_release.py`.
It releases a local reservation only for its durably matched maker order after
a fresh terminal cancellation reports zero fills and the current durable fill
store also contains zero fills for that order. The original ownership fill
floor and later reconciliation history are checked again within the release
transaction. Evidence must originate from the authenticated private collector;
structural checks do not authenticate arbitrary caller-supplied JSON.

Every non-abandoned reservation operation must be acknowledged. Additional
operations are restricted to confirmation/cancellation of the same quote.
Prepared, inflight and unknown operations retain the hold. The hold update,
fresh evidence recheck and release audit event commit atomically. Restarting
returns the original release receipt without releasing twice.

This restores local risk capacity only; it does not increase an exchange
balance or release a filled position. Filled positions still need the separate
settlement and cash reconciliation path. No exchange operation or actual
reservation release was performed by this work.

Validation: 44 focused tests passed across unfilled release, order
reconciliation, risk holds and ownership storage. Release-specific cases cover
stale evidence, unresolved confirmation, acknowledged confirmation, fills
arriving after the zero-fill observation, reconciled partial cancellation,
restart idempotency and rollback on audit insertion failure.

Historical collection was independently confirmed live through process IDs
57437, 57439 and 57443. Its intermediate validation report completed at
2026-09-09T10:53:25Z; no held-out outcomes were inspected or used for tuning.
