# Quiet books can have old native timestamps and current contents

Selected eight mappings with the oldest observed Polymarket native timestamps in
the earlier capture. A new WebSocket subscription reconstructed their books, then
one public REST batch request fetched all eight while the WebSocket receiver kept
running. Every bid/ask price level and size matched the local book both immediately
before the request and after its response. No book updates occurred during the
request window. Independent Decimal comparison verified all 32 ladder comparisons.

Despite this agreement, REST native timestamps were approximately 71–86 minutes
old for seven books and 9.9 hours old for one. This selected diagnostic sample
demonstrates that native timestamp age alone does not establish stale local book
contents. It is not a random sample or proof that either venue's entire backend
is current. REST and WebSocket may share a backend; their agreement cannot detect
a common upstream freeze.

The public [batch book endpoint](https://docs.polymarket.com/api-reference/market-data/get-order-books-request-body)
is a read-only data operation despite using POST. No private credentials, orders,
Pinnacle requests or production book timestamp changes were involved.

Artifacts: `runs/polymarket_snapshot_check_20260909` contains selection, raw WS
frames, timed REST envelope, full before/after ladders, summary and independent
verification hashes. Reusable runner: `scripts/polymarket_snapshot_check.py`.

Next implement an explicit snapshot-verification timestamp alongside native change
time, with matching-token, full-depth, request-latency and connection-generation
checks. A mismatch should invalidate/replace local state through a defined resync
procedure; never renew it merely because a heartbeat arrived. Evaluate this as a
shadow freshness policy before changing live eligibility.
