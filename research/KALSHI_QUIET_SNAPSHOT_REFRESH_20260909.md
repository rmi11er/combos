# Bounded Kalshi quiet-book refresh

The shadow collector accepts optional `kalshi_snapshot_refresh` settings. It uses
`update_subscription` / `get_snapshot` on the existing orderbook subscription,
targeting only static mapped books whose local updates have been quiet for at
least 15 seconds. Batches are at most 100 books, at least five seconds apart, with
a finite per-run request budget retained across reconnects. Sending a request does
not change any observed book timestamp.

Kalshi documents that this action returns current snapshots without modifying
the subscription. [Orderbook update documentation](https://docs.kalshi.com/websockets/orderbook-updates).
Returned snapshots go through existing ladder and stream sequence validation.
As with the normal initial Kalshi snapshot, responses lacking native timestamps
use receipt time minus the existing clock allowance. This is new snapshot receipt
evidence, not a synthetic heartbeat update or independent upstream-health proof.

25 scheduler/runtime tests passed. A 30-second live capture allowed two requests.
The first requested seven eligible quiet books; the second requested 100. All 107
had following snapshots, with none outstanding at shutdown. Median request-to-
snapshot receipt time was 50.9ms, maximum 77.6ms. No returned snapshot supplied a
native timestamp. No sequence-gap error or unexpected disconnect occurred.

Artifacts: `runs/kalshi_snapshot_refresh_20260909` contains exact runtime, event
database, request/snapshot associations and source-hashed verification. This
capture has stopped. No quotes/orders were submitted and no default runtime was
changed. The implementation remains opt-in and shadow-only.

Next combine both exchange refresh mechanisms in a bounded three-source capture
and compare simultaneous leg coverage. Then evaluate the liquidity-weighted fair
scenarios, keeping Pinnacle payoff/limit assumptions explicit.
