# Runtime consumer throughput

The September 7 capture exposed receive-to-decision lag above the unchanged two-second guard. The first improvement preserves the global event order and every raw record, decision, policy transition and maintenance event.

`EventStore.read(..., payload_kinds=...)` now lets each consumer skip fetching and decompressing irrelevant payloads. Every envelope remains present, including sequence and receipt time. Unfiltered reads still return complete payloads for archives and review. New event handlers must add their kinds to the corresponding consumer's payload set.

Creator and shadow checkpoints are committed once per existing 250-event transaction, together with all state and output writes. The shadow replay clock is carried locally inside that transaction and persisted with its last processed sequence. On rollback, none of the outputs, state changes, clock or checkpoint survives; the next attempt rebuilds all local deadlines from durable tables. A creator cursor snapshot is safe inside the same SQLite writer transaction because the creator writer cannot advance while that transaction holds the write lock. An RFQ beyond the snapshot still stops the shadow batch.

Transaction-local earliest-expiry and earliest-markout caches avoid querying empty/not-yet-due work on every message. Every envelope still advances expiration, including irrelevant raw and derived events. Newly reserved quotes and inserted markouts update the deadlines immediately. Existing markout retry behavior, event order and quote revalidation triggers remain unchanged. No latency guard is relaxed, no synchronous logging is removed, and no live-order capability is added.

## Validation

Focused runtime, quote-policy and new equivalence/recovery tests pass (45 tests). The new scenarios compare complete derived events and durable business state with the legacy scheduler through expiration on an irrelevant envelope, markout processing and creator blocking. Additional cases cover a transaction interrupted at checkpoint, restart after rollback, and a blocked creator barrier.

`scripts/runtime_throughput_benchmark.py` restores every non-derived event from a retained capture into two fresh databases and drains both consumers using either their original scheduling methods or the optimized methods. It compares complete derived event sequences and durable tables. Only nondeterministic wall-clock/computation diagnostic fields are excluded from equality; decision time uses the replay clock, and creator evidence source sequences, quotes, risk transitions and markout timestamps remain compared. The captured inputs retain their original sequence numbers.

This is a sequential offline drain using the capture's blocked Pinnacle mappings. Its speed measurement isolates scheduling overhead. It does not establish live receive-to-decision latency, performance of healthy three-source pricing, or acceptance/fill behavior. Those require a new bounded capture after the complete source tree is frozen.

## Complete captured-input benchmark

`runs/runtime_throughput_20260907/benchmark_003/benchmark.json` records a full replay of **185,443 inputs**, producing **69,093 decisions and 27 creator-policy transitions**. The two arms have identical derived-event and durable-state fingerprints after removing only the five timing diagnostic fields listed above. Both require 1,020 consumer batch rounds.

| Metric | Legacy scheduling | Optimized scheduling |
|---|---:|---:|
| Complete sequential drain | 83.50 s | 16.60 s |
| Input events/second | 2,221 | 11,174 |
| Creator worker time | 10.76 s | 9.29 s |
| Shadow worker time | 72.74 s | 7.30 s |
| Creator batch p95 | 24.40 ms | 23.67 ms |
| Shadow batch p95 | 102.39 ms | 11.32 ms |

The observed overall improvement is **5.03×**. This is an isolated offline scheduling result, not a claim that RFQ latency improved by the same factor. SQLite contention with concurrent collectors, HTTP/WebSocket work and healthy pricing must be measured in the next capture. The report records hashes of the exact optimized source and benchmark script.

A reversed-order repetition (`reverse_order/benchmark.json`) again produced identical event/state fingerprints: optimized **17.06 s**, legacy **84.52 s**, or **4.95×**. This checks execution-order/cache sensitivity without changing the source or data. The approximately fivefold offline gain is consistent across the two runs.

## Bounded live follow-up

The subsequent 100-second capture completed with runtime/Pinnacle exit codes zero, zero consumer lag after drain, and complete archive/review exports. It retained all 454 mapping blocks and the two-second guard; no orders or assumed acceptances were submitted. Four Pinnacle odds requests advanced both the local allowance and a fresh provider account check from **23 to 27**.

| Observed metric | Prior capture 001 | Optimized capture 002 |
|---|---:|---:|
| Actual RFQ decisions | 69,093 | 85,147 |
| Receive-to-decision median | 1.344 s | 0.126 s |
| Receive-to-decision p95 | 4.687 s | 0.189 s |
| Receive-to-decision p99 | 5.767 s | 0.210 s |
| Decisions beyond 2 s guard | 25,239 | 8 |
| Basic-scope RFQs beyond guard | 307 / 946 | 1 / 965 |

All eight late decisions came from RFQs received at approximately 100.55 seconds and evaluated at 102.65 seconds during the bounded shutdown. They remain included in the metrics and were correctly rejected. Basic-scope p95 latency in capture 002 was **0.192 seconds**. “Basic scope” covers leg count, NFL nonplayer families and absence of settled legs; it does not imply executable mappings or fair values.

Both exchanges again provided positive two-sided depth on all **454** mapped keys. Pinnacle produced **1,816 inactive observations across four raw snapshots**, retaining payoff/selector review blocks. Consequently, there are still **zero active three-source pricing intersections**, and all 85,147 decisions are skips. This measures a scope/mapping rejection workload, not healthy quote-generation throughput.

Traffic composition and capture time differed, and a separate six-thread historical MLB HTTP acquisition ran concurrently during capture 002. The live before/after comparison is therefore observational, not a controlled causal estimate. The separate identical-input benchmarks support the scheduling improvement independently. Evidence is in `runs/shadow_research_20260907/capture_002/{readiness.json,processing_lag_audit.json,account_summary_after.json,archive/manifest.json}`. The reusable audit command is `scripts/runtime_lag_audit.py --capture <directory>`.
