# Nightly creator-sniffer health — September 8

## Final completion observed September 9

The nightly dispatcher now records successful completion at **00:10:37 Chicago on September 9**, after starting at **18:00:51 on September 8** for a one-hour capture. No sniffer process remains live. The final verifier reports **9,261,135 unique requests**, **8,522 verified bursts**, **6,062 block-eligible bursts**, and **298 active blacklist IDs**: 12 recurrent and 286 provisional. The export reports 154,471 creators and zero missing-creator requests. These are cumulative database/export totals, not the isolated one-hour capture count.

The verification covers stored behavioral evidence, thresholds, recurrence/separation/expiry, exports and trade-horizon consistency; it does not establish malicious intent or economic benefit. The underlying clean capture ended near 19:00, so the complete scan/export/verification pipeline finished more than five hours later. The summary's `generated_at` predates publication and cannot substitute for publication time or per-RFQ causal availability.

This confirms the batch research workflow completed; it does not make it a real-time blacklist service. Forward quoting should use the separately tested causal creator consumer, with sustained mature-database throughput and publication-lag validation still required. No blacklist thresholds or historical selection cohorts were changed. Evidence: `runs/rfq_sniffer_nightly/2026-09-08/status.json`, `run.log`, and the retained `report` directory.

The retained blacklist contains 487 entries including inactive history, with 298 active at export. Evaluating their existing expiry timestamps at the first configured NFL kickoff (**September 9, 19:20 Chicago**) leaves only **12 unexpired active entries**, assuming no new evidence or expiry refresh. This is a deterministic snapshot-expiry projection, not a forecast of live creator behavior. It reinforces that the current export cannot substitute for ongoing causal monitoring. Do not extend expiries merely to retain a larger blacklist. Evidence: `runs/morning_research_20260908/sniffer_completion_review_20260909/expiry_projection.json`.

The scheduled one-hour passive capture reports clean closure at approximately 19:00 Chicago. Its manifest records **5,263,297 RFQ-created events, all with creator IDs**, and **535,161 public trade events**. These are manifest counters, not independently deduplicated totals or linked RFQ fills. The raw archive has not been re-audited here.

At about 21:43 Chicago, the original `rfq_sniffer.py run` process (PID11820) remained CPU-active after capture. Indexed read-only database queries found **5,251,995 committed request IDs in this capture time window**, with latest request timestamp **19:00:45.807**. The worker was left intact. A count difference from the capture manifest does not by itself establish loss: processing/commit boundaries and duplicate IDs must be reconciled after completion.

The exported summary still belongs to the preceding dataset: **3,997,838 unique requests**, **86,642 creators**, **217 active blacklist entries** (212 provisional,5 recurrent). It is not a current September8 export. Do not treat an old summary file or a running process label as proof of live blacklist freshness.

## Implication for the live system

The scheduled command captures first, then scans the journal, then exports. Thus this workflow provides behavioral research archives but does not establish updates as each live RFQ arrives. Export also relabels trade context over the full request table; that is a potential scaling concern, not a measured attribution of this particular runtime. No active code or database was modified during this inspection.

Before live use, separate causal behavioral updates and small blacklist snapshots from the heavier historical trade-context/reporting work. Measure receipt-to-decision and receipt-to-published-blacklist lag, keep a durable replay cursor, and prove restart equivalence without duplicate strikes. Publish observation times, confidence, evidence and expiry; avoid treating an old snapshot as current. Benchmark on the captured rate and preserve raw events even when a creator is blocked.

Spamming/template repetition is behavioral evidence, not proof of negative economic edge. A later trade on the same market is not a creator-specific fill. We still need causal with/without-blacklist comparisons and independent-reference markouts; historical MLB/NFL print P&L cannot be retroactively repaired with these later creator labels. The three-source pricing shadow and actual quote lifecycle remain separate requirements.

## Storage

The active evidence database measured approximately9.15GiB plus3.02GiB WAL. The WAL belongs to the live database; never delete or archive the main file independently of it. This process consumes space alongside the historical study, so earlier static storage forecasts need to include its growth. No checkpoint, vacuum, compression, deletion or additional capture was initiated.

[Read-only observation and source hashes](../runs/morning_research_20260908/sniffer_health/observation.json)

## Reusable health observation

`scripts/sniffer_health.py` now records process presence/identity, capture manifest counters, latest committed request timestamp through the existing time index, export generation age, and database/WAL sizes. It opens SQLite read-only with a bounded query deadline and reads live WAL state; it does not initialize the writer or checkpoint it. Missing database/export observations are explicit, and a missing database is not created. Two focused tests pass, including reading committed WAL data while its writer remains open.

At 21:52 Chicago the latest committed request advanced to 19:00:52.973, approximately two seconds before capture closure. This is evidence of ingestion progress, not proof of complete processing or publication. The export remained 24.84 hours old; process 11820 was present. Free disk was approximately 19 GiB, so storage remains part of runtime monitoring. The independently observed July25 collector and batch supervisor were also still live; no worker was restarted.

[Latest reusable health observation](../runs/morning_research_20260908/sniffer_health/current.json). The tool deliberately reports causal policy freshness as unproven: generation time and latest event time cannot substitute for a durable processing watermark or receipt-to-policy latency measurement.

## Independent creator consumer benchmark

The live runtime already has a separate `CreatorService`; it is not the nightly `rfq_sniffer` batch implementation and uses a different, simpler policy. Its input cursor and policy transitions commit together. A bounded replay of the first ten verified closed chunks tested this existing service in two fresh isolated databases, once continuously and once with a close/reopen after 50,000 source rows. No running service source or database was changed.

Both runs processed 98,135 journal envelopes, retained 47,078 distinct RFQ IDs and produced five watch transitions with zero consumer errors. Request, policy history, active policy, grouped-markout and per-creator state fingerprints match exactly after restart. A further empty step changes no state. All thirteen input/source hashes were independently rechecked.

The sample spans only 34.29 seconds at 2,862 envelopes/second. Combined ingestion and consumer processing achieved 12,298–12,671 envelopes/second on the currently busy host; isolated consumer processing achieved 18,559–19,251/second. This provides short-sample throughput headroom, not sustained multi-hour capacity or end-to-end policy latency. Sequential batch ingestion does not reproduce contention with pricing and feed writers. No cooldown transition, crash inside a transaction, economic toxicity or blacklist benefit was established by this sample.

Next tests should extend across multiple nonoverlapping burst windows and a mature database, measure processing-watermark lag with concurrent pricing, and compare the two policy definitions explicitly before selecting a forward-test policy. Avoid building a duplicate consumer or assuming the nightly export is the live policy path.

[Benchmark evidence and timings](../runs/morning_research_20260908/creator_consumer_benchmark/verification.json) · [Reproducible replay](../runs/morning_research_20260908/creator_consumer_benchmark/benchmark.py)

The extended replay of sixty verified chunks completed both continuous and restart variants: 518,628 envelopes over 170.98 seconds, 247,886 distinct requests, 77 transitions (76 watch, one cooldown), zero consumer errors. All retained state fingerprints match after restart at 250,000 source rows; all63input/source hashes were independently checked. Combined throughput was 7,592–8,352 envelopes/second versus captured arrival rate3,033/second (2.50–2.75x). Throughput is lower than the first-ten-chunk result; this is still a fresh database and short window, not proof of day-long capacity. It exercises entry into cooldown, not hour-long expiry or economic effectiveness. Evidence: [extended benchmark](../runs/morning_research_20260908/creator_consumer_benchmark_extended/verification.json).

## Live postprocessing stack sample

At22:24Chicago a three-second native stack sample of existingPID11820 collected247main-thread samples. All were inside `pysqlite_connection_execute`/SQLite execution;225ended in `pread`,16in `pwrite`,6in WAL lookup. This short observation supports database-page I/O as the current bottleneck, not capture/network waiting. It does not identify the exact active SQL statement or prove that the entire preceding delay had this cause.

A separate read-only `EXPLAIN QUERY PLAN` of the trade-context lookup shows a request scan, correlated search using `trades_market_time(ticker,at)`, and a coverage scan. The exchange timestamp predicates require table data absent from that index. A covering `(ticker,at,exchange_at)` index is therefore a concrete candidate for an isolated benchmark; it has not been built on the active database and its performance benefit is not yet measured. Avoid adding more full-table passes to publish a small live blacklist. Preserve the independently checkpointed creator-policy consumer as the live path and keep historical context reporting separate.

[Native sample](../runs/morning_research_20260908/sniffer_profile/sample.txt) · [Read-only query plan](../runs/morning_research_20260908/sniffer_profile/query_plan.json)

## Isolated covering-index benchmark

A bounded read-only extraction of the first100000retained trade rows supplied an isolated SQLite database. Ten thousand synthetic requests were derived from those trade times; these are benchmark queries, not an economic RFQ sample. The existing `(ticker,at)` index and proposed `(ticker,at,exchange_at)` index return identical result hashes at both60and300second horizons. EXPLAIN confirms a covering search for the candidate. Alternating query order, one warmup and five measured repetitions per index/horizon yield median time reductions of25.3%and28.5%. The additional candidate index occupies5,591,040bytes on this small database.

The result supports benchmarking the candidate at larger scale once the active source is quiescent. It does not prove multi-hour export acceleration: no full UPDATE, WAL growth, coverage-label pass or mature-database contention was benchmarked. No source index, cache setting, checkpoint, data or scheduled process was changed. Source query extraction had a15second progress deadline and used read-only access. [Benchmark, query plans and timings](../runs/morning_research_20260908/sniffer_covering_index_benchmark/verification.json).
# Later export observation

The latest read-only health check observes a newer exported summary: 9,261,135 unique requests and 298 active blacklist IDs, replacing the previously observed 3,997,838 requests / 217 IDs. Its `generated_at` is 1788921843.5729501; the summary file modification time is September 8 at 22:49:17 local host time. These are distinct timestamps and neither alone certifies causal policy freshness. The original sniffer PID 11820 remains live after more than five hours, so export publication is not evidence that the entire nightly task has terminated. Database and WAL were approximately 10.04 and 4.95 GiB at the observation.

Evidence: `runs/morning_research_20260908/sniffer_health/latest.json`. The new export demonstrates processing progress, not validated live blocking or reduced adverse selection. Do not infer that all 298 IDs would have been blocked prospectively under the separate runtime CreatorService policy.
