# Exchange freshness is another participation constraint

The completed 90-second capture had two-sided depth for all 454 mappings at some
point. That aggregate concealed much lower simultaneous coverage under the current
15-second exchange-age rule. At the second and third Pinnacle snapshot receipts,
only 26 and 24 market keys had both exchanges active, positive two-sided depth and
age within the rule. The first Pinnacle snapshot arrived before exchange bootstrap.

| Snapshot | Kalshi keys passing | Polymarket keys passing | Intersection |
|---|---:|---:|---:|
| Second | 80 | 70 | 26 |
| Third | 252 | 26 | 24 |

Of 3,295 Polymarket observations, 418 already exceeded 15 seconds of native age at
receipt and 313 exceeded 120 seconds. Maximum was about 9.7 hours. Kalshi's 3,005
observations all arrived within 0.297 seconds under the current adapter's timestamp
basis, but unchanged states later age out as well.

This is not evidence that every quiet book was wrong or disconnected. The adapter
uses native message timestamps when supplied and ages the retained state from that
time. Fresh connection delivery, an unchanged order book, and outdated/missed
updates are different conditions. Polymarket documents book events on subscription
and updates; Kalshi documents snapshot-plus-delta streams and supports explicit
snapshot requests. [Polymarket market channel](https://docs.polymarket.com/api-reference/wss/market),
[Kalshi orderbook updates](https://docs.kalshi.com/websockets/orderbook-updates),
[Kalshi changelog](https://docs.kalshi.com/changelog).

The audit walks the causal event stream, clears state on venue resets and selects
only observations preceding a Pinnacle event in sequence and available no later
than its receipt. Cross-process insertion order can differ from receipt order;
the join therefore falls back to an earlier eligible observation instead of using
a later-received state. No future data is used to replace missing coverage.

Reusable workflow: `scripts/capture_exchange_freshness.py`.
Result: `runs/nfl_three_source_capture_20260909/exchange_freshness.json`.
The original planned source-agreement comparison is not yet complete; this audit
identified a prerequisite that would otherwise bias it toward frequently updating
books. No freshness limit was relaxed and no heartbeat retimestamping was added.

Next add explicit evidence for connection liveness, subscription/snapshot readiness
and synchronization, retain last-change timestamps separately, and periodically
reconcile quiet books against new snapshots. A local heartbeat alone cannot prove
upstream book validity. Compare that policy in shadow before using it for quoting.
