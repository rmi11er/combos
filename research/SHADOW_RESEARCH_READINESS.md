# Three-source shadow research capture — September 7, 2026

The bounded runner is `scripts/shadow_research_capture.py`. It copies the reviewed NFL nonplayer runtime, weighting policy, and polling policy into an isolated experiment; refreshes the account allowance; and runs the Kalshi/Polymarket runtime together with the Pinnacle recorder against one initialized event database.

The prepared experiment is `runs/shadow_research_20260907/capture_001/`. It retains **all 454 `pinnacle_payoff_mapping_unreviewed` pricing blocks** and the 2–4-leg pregame scope, $10,000 capital, and configured contract/combo/fixture limits. Data collection does not lift these blocks. No order endpoint is called and no RFQ acceptance is fabricated.

The account refresh confirmed the `pinnacle+30` football subscription, **100,000 requests**, **19 used**, and billing boundaries September 7 at 18:23:19 UTC through October 7 at 18:23:19 UTC. The experiment uses the existing subscription-wide budget database, reconciled upward to the account usage. This is the existing delayed REST subscription; no upgrade or paid-tier change is involved.

Preparation and execution are separate commands. Execution requires a matching digest of the frozen runtime source, a fresh account reconciliation, unchanged prepared inputs, and a fresh event database. Its allowed duration is 90–120 seconds. The supervisor bounds shutdown, stops owned process groups, drains consumers, and exports the event archive, review files, and a `readiness.json` report with observation/depth coverage, resets, normalization errors, and real decision reasons.

Three focused tests pass: preserving blocked shadow configurations, matching the account tier and billing cycle without mutating the source policy, and cleaning up an owned child process group. Raw credentials are read only into memory and supplied through the Pinnacle/account child process environment; they are never embedded in arguments, configuration copies, or reports.

## Completed capture

The 100-second capture completed successfully. Both supervised processes exited zero, both consumers drained to zero lag, and archive/review exports completed. The archive contains **254,563 events in 26 compressed chunks (61,794,648 bytes)**. The database is approximately 225 MiB. No orders, invented acceptances, or simulated fills were submitted.

| Source | Actual collection |
|---|---|
| Kalshi | 169,283 raw messages; 2,931 active normalized book observations |
| Polymarket | 4,455 raw messages; 4,552 active normalized book observations |
| Pinnacle | Four fresh REST snapshots, each containing 16 NFL fixtures; 1,816 normalized records |

Both exchanges provided **positive two-sided depth for all 454 configured market keys**. The three sources overlapped in wall-clock collection, and all 454 keys have source records. However, **zero keys have usable active observations on all three venues**: each Pinnacle snapshot correctly preserves 265 `pinnacle_payoff_mapping_unreviewed` and 189 `pinnacle_selector_unreviewed` records. These are mapping/payoff verification blocks, not missing exchange depth. The raw Pinnacle snapshots are available for subsequent mapping review.

The four odds requests advanced the shared subscription allowance from **19 to 23**. There were no disconnect/reconnect failures; venue resets consist only of initial connection and clean shutdown. The creator monitor recorded 27 real policy transitions. All 69,093 shadow decisions were skips, including 521 that reached the preserved payoff-review block. Collection success does not mean live pricing is ready.

## Processing-lag finding

**25,239 of 69,093 decisions (36.5%) exceeded the unchanged 2-second processing-age guard.** RFQ receive-to-decision lag was **1.344 seconds median, 4.687 seconds p95, 5.767 seconds p99, and 6.946 seconds maximum**. The queue became material after the first 20 seconds and recurred through the capture; this was not merely an initial connection effect.

Most late RFQs were outside the strategy's scope, but the issue also affects relevant traffic. Of **946 RFQs passing basic leg-count/sport/nonplayer/unsettled-leg checks**, **307 (32.5%)** were skipped for backlog. Of those 307, 259 also had configured ticker mappings and distinct fixtures; 29 had missing mappings and 19 repeated a fixture. Mapping/payoff blocks would still prevent quoting today, so these counts are not missed executable trades.

Measured `decide()` computation was 10.9 microseconds median, 26.7 microseconds p95, and 3.48 milliseconds maximum, totaling 0.981 seconds across all decisions. **These timings predominantly measure scope/mapping rejection paths**, exclude subsequent decision serialization/database writes, and do **not** establish the throughput of healthy three-venue pricing or quote generation.

Code inspection supports a concrete architectural diagnosis: both consumers read and decompress the global event stream, including irrelevant and derived events; each event triggers checkpoint writes, and the shadow worker additionally writes its clock and invokes maintenance. They share SQLite's serialized writer path. The shadow cursor also waits for creator processing before each RFQ, so queued RFQs can delay later market observations. Transaction and creator-wait durations were not separately instrumented, so this capture cannot apportion the delay precisely among them.

The next bounded remedy is to reduce per-event database/maintenance work and unnecessary event decoding while preserving raw recording, chronological state updates, prior creator evidence, and the 2-second guard. Test atomic batched checkpoints and relevance-aware consumer work before considering a larger architectural split. No guard was relaxed, no source refactor was made from this finding, and no additional capture is needed this turn.

Evidence: `capture_001/readiness.json`, `processing_lag_audit.json`, `archive/manifest.json`, the four `pinnacle_raw/` snapshots, and the complete `review/` export. The capture used frozen source digest `7c38a2d9ca14d0e234c5a227b17c247f0cecd3852ecd350b1a2a0f254c2a697c`.
