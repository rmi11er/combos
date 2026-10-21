# Explicit snapshot verification candidate

`book_verification.py` validates REST/WS full-depth agreement without rewriting
native timestamps. It requires the correct token, unchanged connection generation
and book revision, positive noncrossed ladders, exact Decimal price/size equality,
request duration at most two seconds, bounded HTTP Date/Age evidence and an
acceptable native clock offset. The verification time conservatively uses the
earlier of request start and HTTP Date, minus cache Age; causal availability remains
response receipt.

The separate candidate-time accessor checks token, generation, revision, full-depth
fingerprint, availability and a 15-second verification lifetime. Reconnection,
any revision or stale evidence invalidates this certificate; it is not renewed by
a local heartbeat. Native timestamp is retained alongside candidate observed time.
This intentionally conservative first version does not propagate a certificate
across subsequent deltas.

Ten focused tests passed. The bounded `polymarket_snapshot_check.py` runner now
uses this validator. A new eight-book live comparison verified all eight at REST
receipt; all price levels and quantities matched before and after, with no updates
during the request. Native ages were still 73 minutes to 9.9 hours. One public REST
batch request was used. Artifacts: `runs/polymarket_snapshot_verification_20260909`.

The connection closed after the test, so these certificates are historical test
evidence, not current usable trading state. The candidate is not wired into the
production pricing path. No live age limit or pinned historical source changed.
REST and WS may share backend state, so agreement is not independent proof against
a common upstream freeze.

Next integrate bounded quiet-book snapshot requests into the shadow collector,
publish certificates with generation/revision context, and compare resulting fair
coverage against the native-age baseline. Keep both decisions for later evaluation.
