# MLB collection throughput and reuse audit

Read-only audit at approximately 2026-09-08 01:49–01:52 UTC (September 7, 20:49–20:52 Chicago). No collector, pacing, scope, budget or frozen source was changed. No network calls were made.

## Current work is progressing

Live OS process evidence:

- PID 79936: original five-date MLB public collector, approximately 2h29m elapsed, six workers, 80,000-request invocation ceiling.
- PID 80267: expanded 26-date queue, waiting for the five screening dates to finish.
- PID 82095: dated model batch, approximately 1h38m elapsed, 15,000 metadata GETs per attempt, 48-hour overall wait.
- PID 84452: July 29 cohort metadata stage, initially 18m47s elapsed; continued advancing during this audit.
- PID 84066: resumed NFL public collector, two workers, 144,541 remaining invocation request ceiling.

Three MLB raw dates are complete: July 1, July 15 and July 29, each with 24 hourly partitions. August 12 had 12 completed hours at the first snapshot. July 29 metadata advanced from 193,100 to 220,100 recovered definitions during inspection, out of 365,763 requested. This is not a stalled process.

Public GET attempts in the last 600 seconds, measured directly from timestamped attempt logs:

| Consumer | Attempts | GET/s |
|---|---:|---:|
| MLB raw tape | 1,587 | 2.645 |
| July 29 metadata | 1,056 | 1.760 |
| NFL raw tape | 530 | 0.883 |
| Combined | 3,173 | 5.288 |

The shared `scripts/rate_limit.py` reserves one request slot every 0.18 seconds, a ceiling of 5.556 GET/s across these clients. The measured combined throughput is close to that ceiling. Increasing worker counts would predominantly redistribute slots and increase contention; it would not create more allowed throughput.

At the snapshot, MLB raw attempt history contained 30,816 attempts. July 29 metadata had 2,162 attempts over 1,234 seconds; its remaining approximately 150,000 definitions implied roughly 15 minutes at the then-current 100-definitions-per-request recovery rate. Underlying metadata and downstream stages still follow.

## Cache reuse: measured overlap is zero for the current dates

`recover_metadata()` loads the passed seed, then its own dated response cache. It does not automatically merge sibling-date caches. The batch passes `runs/mlb_historical_20260907/cohort` as the same seed for every date. That seed contains 159,450 September pure-MLB combo definitions, rather than the full all-sport metadata universe.

I extracted all returned ticker identities from completed dated metadata caches and compared them with July 29's requested ticker identities:

| Set | Tickers | Overlap with September seed | Overlap with earlier completed dates |
|---|---:|---:|---:|
| July 1 cached metadata | 506,899 | 0 | — |
| July 15 cached metadata | 166,698 | 0 | 0 |
| July 29 requested metadata | 365,763 | 0 | 0 |

Consequently, merging these caches would save **zero requests for the three measured dates**. The every-other-day expansion might have some shared definitions for future-game combos, but that has not been measured. It should not be assumed to offer material savings. Caches already make retries of the same date resumable.

Historical-first routing is selected only when every raw partition uses the historical endpoint. July 1 used historical-first; July 15 and July 29 use current-first. July 29's recovery rate is about 100 definitions per GET, consistent with successful first-route batches; changing routing would not improve this stage.

A future shared metadata cache could preserve immutable response envelopes and choose entries by ticker with hashes and provenance, but would require a new frozen implementation/run version. There is no evidence to justify disrupting healthy current jobs for it.

## The full 31 dates are unlikely to finish by morning

Closed raw dates require 8,231–9,376 pages, averaging 8,833 pages/date. Approximately 28 dates remain beyond the three complete tapes, less the partially collected August 12 day: about 243,000–247,000 additional tape requests at the observed average.

- Giving those requests the **entire** shared 5.556 GET/s capacity takes approximately **12.2–12.4 hours**, excluding all metadata, NFL and exchange-history requests.
- At the observed MLB tape share of 2.645 GET/s, tape alone takes approximately **25.5–26 hours**.
- Metadata, NFL collection and exchange history also consume the shared budget. The tape-only lower bound is therefore optimistic.

The audit began around 20:49 Chicago. It is not supportable to promise all 31 dates complete by the next morning. Morning findings should explicitly report the completed dates and missing validation coverage, while preserving the full requested collection and analysis scope.

The 400,000-GET expansion budget covers about 15,385 pages per expansion date, materially above the three-date average. It is plausible for the tape, but is a request ceiling rather than proof of sufficient coverage. The metadata budget of 15,000 GETs per dated attempt also exceeds the observed 1,667–5,864 successful-stage counts; retries and larger dates remain possible.

## Disk estimate and operational safeguard

Actual available filesystem space measured with `statvfs`: **51.67 GiB**. Current project subtrees were about 5.1 GiB MLB, 0.44 GiB NFL, and 0.05 GiB morning research. These are already reflected in the free-space figure and must not be subtracted again.

Closed raw tape storage:

| Date | Pages | Compressed bytes | Bytes/page |
|---|---:|---:|---:|
| July 1 | 9,376 | 401,742,358 | 42,848 |
| July 15 | 8,891 | 355,393,620 | 39,972 |
| July 29 | 8,231 | 335,536,347 | 40,765 |

Weighted average: **41,236 bytes/page**, or approximately **0.339 GiB/date**. Twenty-eight additional raw dates at that average require **9.50 GiB**, less approximately 0.16 GiB already present for the partial August 12 date.

The completed July 1 dated report tree is **1.064 GiB**, after its SQLite scratch index was archived. Breakdown: exchange 142.5 MiB, cohort 366.3 MiB, replay 191.7 MiB, common report 53.9 MiB, entry sweep 140.6 MiB, risk capacity 194.8 MiB. July 15 is only 0.267 GiB and should not be used alone to budget a normal active MLB slate.

An empirical planning case using July 1's report size for the 29 not-yet-completed report trees is approximately **30.9 GiB**, plus **9.3 GiB remaining raw tape**, or **40.2 GiB incremental**. This conservatively ignores some current July 29 bytes already written. It leaves about **11.5 GiB** for NFL growth, pooled outputs, temporary archives and other filesystem users. It is a plausible fit, **not a guarantee**. A 1.5× busy-date case would exceed present free space.

Verified scratch archives already demonstrate substantial savings:

- July 1 index: 725,352,448 bytes → 171,748,347 bytes, saving **0.516 GiB**.
- July 15 index: 341,278,720 bytes → 79,437,976 bytes, saving **0.244 GiB**.

If 29 additional July-1-sized indices remain uncompressed, that adds roughly **15 GiB** beyond the empirical report estimate, eliminating the expected headroom. Therefore the full run's plausible fit depends on continuing the established **verified archival of completed, no-longer-used scratch indices**. Archive creation temporarily needs space for both files; archive only completed stages and retain source/output hash evidence. Raw market data should remain intact.

The existing archive watcher (PID 84264, independently verified live) already records `free_disk_bytes` every poll in `runs/morning_research_20260908/index_archives/status.json` and has verified both completed archives. **No additional watcher is needed.** Recommended operational action: continue current collection and analysis unchanged and review the existing free-space telemetry at completed-date boundaries. Review storage forecasts at **20 GiB free** and treat **15 GiB free** as an urgent capacity review threshold, allowing time for transient compression and NFL growth; this is a monitoring threshold, not permission to delete raw data or truncate dates. Before any last-resort intervention, reconcile which completed intermediates are still referenced and whether they can be restored byte-for-byte from verified archives. No such intervention was performed in this audit.

## Conclusion

**Existing processes should continue.** They are progressing near the shared request ceiling; measured metadata reuse does not offer a speedup. The concrete operational issue is disk monitoring and completed-scratch archival, not increasing concurrency or shrinking the research universe. Morning deliverables should contain verified partial findings and a candid completion forecast while all 31 dates remain in the active plan.

Evidence: `ps -axo pid,etime,time,command`; dated cohort `attempts.jsonl`, `metadata_coverage.json`, `combo_metadata/*.json.gz`, July 29 `tape_index.sqlite` opened read-only; raw hourly manifests and page-file sizes; `expanded_queue_status.json`; archive manifests; `scripts/mlb_daily_cohort.py`, `scripts/mlb_historical_batch.py`, `scripts/mlb_public_day_acquire.py`, `scripts/mlb_collection_queue.py`, and `scripts/rate_limit.py`.
