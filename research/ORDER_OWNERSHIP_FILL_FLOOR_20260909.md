# Preserve fill evidence from original maker ownership

Found a reconciliation gap while reviewing requirements for releasing unfilled
reservations. `OrderReconciler` enforced monotonicity against prior reconciliation
reads, but its first read did not compare against the private order snapshot
already archived when maker ownership was established.

For example, the original ownership snapshot could report two filled contracts,
then a first reconciliation snapshot could claim canceled with zero fills. With
no separately ingested fill records, the old path could label zero counts as
matched. It did not release capital, but would be an unsafe prerequisite for a
future release operation.

Reconciliation now checks every original ownership snapshot as well as earlier
reconciliation reads: filled quantity and update time cannot regress, creation
time cannot change, and an originally terminal order cannot reopen or change its
terminal fill count. Missing original snapshot evidence fails explicitly.

The prior synthetic zero-fill test inadvertently started from an ownership
snapshot containing two fills. It now uses a genuinely zero-fill original
snapshot. Added regression tests reject disappearing original fills after a
journal restart and reject reopening an originally canceled order.

Forty-seven focused ownership/order/risk tests passed. After strengthening the
restart regression case, all 27 order-reconciliation tests passed again. No live
order was submitted or local reservation released. A release method remains
unimplemented until its complete evidence checks and atomic transition are
tested; this change closes a prerequisite correctness gap.
