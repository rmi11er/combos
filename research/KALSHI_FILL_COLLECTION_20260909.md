# Bounded incremental fill collection

`FillCollector` connects the authenticated GET client to durable fill evidence.
`scripts/collect_account_fills.py` accepts an explicit initial timestamp, fixed
upper timestamp, subaccount, page budget, private output directory and journal.

Subsequent polls overlap the previous successful upper timestamp by 120 seconds.
Every raw page is archived before ingestion. All pages must exhaust pagination,
validate fixed-point economics and match the requested subaccount/time window
before fills and checkpoint commit together. An invalid later page rolls back
earlier page ingestion. A concurrent checkpoint change rejects the stale poll.
The initial horizon cannot silently change across restarts.

The checkpoint means the window was successfully queried, not that exchange
reporting is final. Reports delayed beyond the overlap require periodic deeper
reconciliation; the workflow does not release capital or establish order ownership.
No background polling schedule has been enabled yet.

25 tests passed across collection, fill evidence and authenticated read helpers.
Live verification made two GET requests: the previous hour, then a two-minute
overlap after reopening the database. Both exhausted their cursors with zero
fills. Raw requests/receipts are private under `runs/kalshi_fill_poll_20260909`.
The initial verification version used `checkpoint_advanced=true` for a successful
repeat of the same upper bound; the implementation now distinguishes publication
from actual advancement. This labeling correction does not change stored bounds
or ingestion behavior.

Next connect authenticated quote/order ownership and terminal-order comparisons;
then schedule overlapping reads together with periodic deeper reconciliation.
