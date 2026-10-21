# Authenticated account collection

Implemented `src/combos/kalshi_readonly.py` and `scripts/collect_account_reads.py`.
The production client signs GET-only allowlisted paths against the fixed Kalshi
host, disables redirects and transport retries, and retains request/receipt times
without authentication headers. Files are exclusive-create, mode 0600, under a
new mode-0700 run directory. Network errors retain exception class only.

Pagination has a finite page budget and explicitly distinguishes exhausted
cursors, page-budget exhaustion, cursor loops, malformed rows/cursors and request
failure. Complete pagination is not an atomic account snapshot and never
authorizes risk release or ledger initialization.

Eleven tests passed covering signature verification, path restrictions, pagination
failures, private artifacts and balance assessment. The empty quotes response
omits its optional cursor in production. Only this empty endpoint-specific shape
is accepted without a cursor; missing cursors on nonempty responses remain
incomplete. See the [quotes schema](https://docs.kalshi.com/api-reference/communications/get-quotes)
and [positions filters](https://docs.kalshi.com/api-reference/portfolio/get-positions).

Two four-GET collections were run without mutations. The first exposed the
optional-cursor shape; the corrected second run is retained at
`runs/kalshi_account_pagination_20260909_v2`. All three lists exhausted pagination:
zero nonzero primary-account market positions (`count_filter=position`), zero
primary-account resting orders, and zero self-created quotes. The first run's
balance remained -1048.3917 dollars. These findings do not establish historical
fill completeness, an atomic absence of exposure, account balance precision,
or funding for the $10k strategy. Event-position payloads remain in raw pages;
the market-position list is the enumerated position collection.

Next integrate these observations with order/fill reconciliation and account
activity timing. Keep actual cash separate from the hypothetical research bankroll.
The frozen historical implementation and running collection were not changed.
