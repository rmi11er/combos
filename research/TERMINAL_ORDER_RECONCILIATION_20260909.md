# Terminal order evidence and filled exposure

OrderReconciler now connects a bounded authenticated individual-order GET to the
durable maker ownership and deduplicated fill ledger. The collector archives the
response privately before validation, including unsuccessful responses. No retry,
quote submission or capital release is introduced.

Validation requires the exact order/account/exchange/direction/limit/initial size,
a request-to-evaluation age no greater than two seconds, valid exchange chronology,
and consistent fixed-point quantities. Known terminal statuses are canceled and
executed. Terminal orders must have zero remaining count; executed orders must be
fully filled. Unknown or contradictory statuses fail closed. A prior terminal
snapshot cannot revert to resting or change its reported filled count; cumulative
counts and update timestamps cannot regress. These are conservative invariants;
amended-order and exchange correction workflows remain unimplemented.

A partially canceled ten-contract order with two fills records eight canceled
contracts and two filled contracts. Matching all fills establishes terminal fill
reconciliation, not settlement or spendable cash. Every assessment still has
capital_release_authorized=false. Order, fill and balance observations are not an
atomic exchange snapshot. Direct record() calls structurally validate envelopes;
authenticated provenance requires the collector path and retained private archive.

75 focused tests passed across order reconciliation, authenticated reads, ownership,
fills and quotes. Tests include partial cancellation, fully executed orders, missing
fills, restart regression, invalid identity/count/timestamps, path injection and
archiving a failed GET before rejection. No real strategy-owned order exists to
validate this lifecycle end to end, and no live order was submitted.

Historical supervisor PIDs20360/37399 and collection PID45066 were confirmed live
with ps during this work. Four August dates were pending at the last status check.

Next connect account/settlement evidence to hold accounting, test cancel/fill races
end to end, and finish sustained shadow and frozen historical validation. This
change does not select or promote model weights, edge charges or risk limits.

API references checked September9:
https://docs.kalshi.com/api-reference/orders/get-order
https://docs.kalshi.com/api-reference/orders/get-orders
