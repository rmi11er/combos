# Shadow collector snapshot verification

The Polymarket collector now accepts an optional `polymarket_snapshot_verification`
configuration. It is shadow-only, defaults off, bounds batch size to 100 books and
the run request budget to 100, and requires at least five seconds between requests.
It prioritizes books older than the baseline 15-second limit, rotating among those
not recently checked. REST requests run in a background thread while the WebSocket
receiver continues reconstructing ladders.

The event log retains raw REST envelopes, rejected checks, accepted verification
certificates and the associated baseline observations. Connection generation and
per-book revisions bind each certificate to local state. A reconnect or intervening
update rejects an in-flight verification. The request budget survives reconnects.
Normal observations retain their original native-age basis; no pricing consumer
has been changed to use the certificates yet.

40 tests passed across runtime, liveness, verification and asynchronous probe
integration. A 25-second live check configured three requests, 100 books each and
five-second spacing. It saved exactly three raw REST batches and verified 300
distinct markets, with no rejected comparisons or unexpected disconnects. Their
baseline observation ages at REST receipt ranged from 47.7 seconds to 9.95 hours.
All were outside the current baseline age limit when verified.

Artifacts: `runs/polymarket_shadow_verification_20260909`, including the exact
opt-in runtime, event database and source-hashed verification summary. The capture
ended normally. The run budget is not a monthly request budget or an always-on
scheduling policy. No OddsPapi requests or orders were made.

Next consume these events in a paired shadow candidate and measure sustained
coverage, churn and full-pricing latency. Keep native-age decisions alongside the
verified-state decisions. A certificate expires on revision/generation changes or
its age limit; common REST/WS backend freezes remain outside this check's proof.
