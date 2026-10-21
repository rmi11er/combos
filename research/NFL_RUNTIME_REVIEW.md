# September 6–7 NFL runtime review

The exchange collection and mapping infrastructure is working. The requested
continuous-hour soak **did not pass**: macOS entered maintenance sleep repeatedly,
and the original monotonic duration limit did not include that sleep. The run
was stopped, drained and archived. A corrected short live run passed after the
duration and book-subscription fixes below. An uninterrupted soak on an always-on
host remains necessary before relying on multi-day collection.

## Captured run and creator evidence

The final recorded stream contains **5,272,509 events**, including **1,461,679
RFQs from 49,047 creators**. Every captured RFQ has a recorded decision, all
captured requests have creator IDs, and both consumers reached the final offset.
There were no consumer exceptions. Every decision was a skip because this run
used the original capture-only configuration. It did not submit orders.

The wall-time envelope, including final derived events, was about 85 minutes.
Eight recorded-message gaps longer than five seconds totaled **43.4 minutes**;
the longest was **956 seconds**. macOS power logs confirmed maintenance sleep.
The gaps are retained as gaps; this is not an uninterrupted-hour sample or a
complete census of traffic during the wall-time interval. Sleep/backlog also
raised decision latency: median 127 ms, p99 1.108 seconds, maximum 955 seconds.
Requests beyond the configured two-second backlog limit were skipped.

The creator service emitted 60 cooldown transitions. All 768 detected burst
windows met the 30-request / 80%-same-leg-set rule, and all 60 cooldown transitions
had three qualifying bursts separated by at least 60 seconds. Forty-four expiry
transitions returned creators to watch; 16 cooldowns remained active at the end.
These are repetitive-request findings. There is no calibrated correlation or
adverse-selection blacklist yet, and there were no automatic permanent bans.

Using the new mappings as an eligibility join, the captured flow contained
19,906 two-leg NFL RFQs; 11,522 had both legs mapped, and 10,454 crossed fixtures.
That join is coverage evidence, not an opportunity estimate. The public feed
also recorded 21,033 combo prints totaling 12.76 million contracts and about
$1.486 million of YES-side consideration in the captured windows. No strategy
fill or edge is inferred from those prints.

Artifacts:

- [Final metrics and message gaps](../runs/nfl_capture_20260906_2234/final_review/summary.json)
- [Creator transitions with reconstructed request windows](../runs/nfl_capture_20260906_2234/final_review/creator_evidence.jsonl)
- [Archive and rule validation](../runs/nfl_capture_20260906_2234/validation.json)
- [Complete compressed archive manifest](../runs/nfl_capture_20260906_2234/archive_final/manifest.json)

The database occupies 4.67 GB; the final archive occupies **1.26 GB** across 528
checksum-verified chunks. Its manifest includes the exact starting source code,
verified against all 20 hashes recorded at initialization. An earlier clean
90-second exchange-feed sample extrapolated to about **52 GB/day compressed**.
The interim uninterrupted SQLite growth rate was about 186 GB/day. These are
sample rates, not capacity guarantees. Off-host storage, automatic rotation and
hot-data retention are still required for a multi-day service on this laptop.

## Corrections made from the run

1. Bound worker, collector and supervisor duration by both calendar and monotonic
   time. Record both elapsed times at collector shutdown. Sleep cannot silently
   extend a configured session into a later trading window.
2. Handle deltas still in flight after unsubscribing from a dynamically selected
   book. All four `delta_without_snapshot` resets in this recording followed a
   `delete_markets` command for that same ticker. Retired-book updates are now
   logged and ignored; re-added markets wait for a fresh snapshot. Sequence-gap
   checking remains active. Replaying all **3,753,436 Kalshi messages** through
   the corrected normalizer produced four expected retired-book exclusions and
   **zero reconstruction errors**.
3. Snapshot source text as well as hashes at initialization, and reject service
   startup if code, configuration or weights differ from the initialized
   manifest. Changed experiments get a new database; saved source permits
   replay of an older experiment.
4. Persist the exact rolling counts and thresholds in future creator-policy
   events. The review command can also reconstruct them for older recordings.
5. Check structural eligibility before price-feed availability; explicitly gate
   collection-only payoff mappings, expired fees and already-settled legs.

The [book regression result](../runs/nfl_capture_20260906_2234/book_reconstruction_regression.json)
records the historical replay. A separate 241,347-event exchange sample was
archived, checksum-verified, restored and replayed using its saved code. Event-time
replay appropriately removes processing-backlog skips; it does not recreate the
original machine's pauses or customer fills.

## Final live verification

After the corrections, a new bounded run completed in **60.115 seconds** with
**29,949 RFQs**, complete decision coverage, and both consumers drained. Both
Kalshi and Polymarket delivered observations for **all 299 configured contracts**.
There were no reconnects, consumer errors or processing-backlog skips. Median
processing lag was **141 ms**, p99 **235 ms**, and maximum **275 ms**.

The test exercised same-fixture exclusions, already-settled-leg exclusions,
missing mappings and the Pinnacle-payoff-review gate. It generated no executable
quotes. [Final live verification](../runs/nfl_verified_20260907/review/summary.json).
The automated suite passes **56 tests**, including clock jumps, late subscription
deltas, mapping signs/thresholds, fee expiry, source pinning, risk and replay.

## Next launch steps

The [299-contract NFL mapping and fee configuration](NFL_MAPPING_REVIEW.md) is
ready for exchange data collection. Before three-venue shadow prices, connect
Pinnacle and review its payoff/push semantics, define exceptional-settlement
handling, and supply the per-contract/fixture/combo risk caps. Refresh market and
fee metadata before Wednesday. Then run an uninterrupted soak on an always-on
host with archive rotation. The future live order/quote lifecycle and exchange
position reconciliation still need an execution adapter and validation.
