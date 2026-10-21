# Longitudinal replay scalability audit

Read-only audit of the current implementation and existing three-date artifacts. No simulation, matching, pricing, collection or frozen source was changed. The parent stopped the idle longitudinal watcher after its three-date version completed; collectors and the core daily batch continue. The full 31-date scope and all 48 policy/regime combinations remain required.

## Finding

The current implementation is unsuitable for the full intended dataset on this 18GiB machine. It eagerly retains every decoded model row, then creates several additional per-run representations of the largest selected sets. Moving only `EventStore` to disk or lowering plot resolution does not solve this.

The intended scale is approximately 31 × 40,000 common prints = **1.24 million unique prints**, **4.96 million model rows**, and **59.52 million decisions** across four models × six fixed entry variants × two funding regimes. This is not a reason to cap the sample or drop variants. It requires disk-backed input ordering, streaming single-policy evaluation and bounded curve/report aggregation.

### Concrete current evidence

| Baseline daily replay | File bytes | Model rows | Approximate deep size of first decoded row excluding dictionary-key strings |
|---|---:|---:|---:|
| July 1 | 169,151,003 | 129,026 | 4,023 bytes |
| July 15 | 3,150,205 | 2,378 | 3,882 bytes |
| July 29 | 217,462,621 | 166,548 | 3,749 bytes |

The object sizes were measured from one decoded row per file with recursive `sys.getsizeof`; they are representative estimates, not peak-RSS measurements or a rigorous per-row lower bound. JSON dictionary keys can be shared by the parser, while repeated nested source objects and their string values are generally decoded separately. Multiplying these examples by 4.96 million rows gives roughly **18.6–20.0GB decimal (17.3–18.6GiB)** for input-row objects alone, before list/set indexes, portfolio decisions, fills, curves, interpreter overhead and the OS. Input serialization is roughly 6.5GB at this scale; full-file `read_text` also creates transient large strings.

The existing completed three-date version is `runs/mlb_historical_20260907/longitudinal/versions/99747429892956068fe7`, with July 1/15/29 common counts 31,263 + 392 + 40,906 = **72,561 prints**. Its 48 policy/regime records account for 3,482,928 decision rows. Compressed artifacts total:

| Artifact family | Bytes |
|---|---:|
| Decisions | 545,459,282 |
| Full curves | 187,650,888 |
| Fills | 30,607,720 |
| Summary/plots/other | 10,359,148 |

A linear extrapolation of that final-version payload to 1.24 million prints is about **13.2GB decimal**. Compression, fill fraction and curve density can change, so this is a planning estimate, not a disk guarantee. Current free disk was **42GiB**. This estimate excludes normalized inputs, scratch databases/WAL, all existing raw data, later collector growth and retained prior versions. The separate retention audit must budget those together.

## Allocation and retention paths

1. `mlb_longitudinal_sweep.main` calls `prepare({date: load(file) for ...})`: every daily `opportunities.json` is decoded before pairing starts. `prepare` adds per-date lists/dictionaries, common-ID sets, fold-purge fixture sets, a global sorted row list and duplicate identities. Some structures share row references, but the decoded source data remains the dominant full-study allocation.
2. `evaluate` builds `model_rows` and runs 12 portfolios per model. The **48 runs are sequential**, not simultaneous; the problem is the full input plus the peak of one large run, not 48 fully resident portfolios.
3. `run_backtest` materializes duplicate-validation sets; a sorted per-model list; evaluations; shallow decision dictionaries; fills; and a pending settlement heap. Every accepted unresolved/future-settled print can remain active for a long interval. `EventStore(':memory:')` puts reservation, exposure and risk event tables in RAM as well.
4. `build_curves` builds nested timestamp dictionaries and duplicate-ID sets, then a complete curve list. `attribute_trade_performance` builds another changes dictionary; `daily_statistics` repeatedly filters fill lists. These are additional O(N) allocations, even before output writing.
5. `evaluate` constructs `selected`; `metrics` constructs known/unknown lists, edge lists and fixture/combo accumulators; `sampled_statistics` stores selections again in day buckets. The caller retains `result` while these representations coexist.
6. `gziprows` writes incrementally, but receives already materialized lists. `compact_curve` runs **after** the full curve exists. Its display reduction therefore has no meaningful effect on the peak during replay.
7. The watcher fully reevaluates every changed completed-input identity. If one new date arrives per iteration, repeated full-prefix work scales like 1+2+...+31 = 496 date-equivalents per policy instead of 31 for a single final run. Full prior-version output retention compounds this; the other audit owns retention policy.
8. Disk-backed `RiskLedger` alone still uses `SUM` over reservations and exposure joins on repeated risk checks. This preserves behavior but can leave CPU/I/O costs that grow with historical positions. Do not assume a storage-location change is a complete performance remedy.

## Proposed implementation: separate leaf workflow

Build a new streaming longitudinal runner and supporting modules, leaving the frozen baseline and current three-date artifacts untouched until exact parity is established. Keep one active policy/regime at a time. Reuse immutable normalized input and decode only the current row or a bounded batch.

### 1. Certified ingestion, pairing and purge on disk

Retain `discover`'s completed-stage/hash certificates and the same requested-date rules. Ingest **one bounded record batch**, not all daily JSON documents. Use a proper incremental JSON parser or a verified streaming exporter to JSONL; do not split arbitrary JSON by braces or line breaks. Record original input hashes and parsing/schema versions.

A scratch SQLite input index can store:

- `prints(day, evaluation_id, at, quantity, yes_price, maker_fee, settled_at, yes_settlement, buckets_json, source_json)` once per observed print;
- `model_values(day, evaluation_id, model, fair_point, stressed_upper, quote_allowed, risk_multiplier)`;
- `fixture_membership(day, evaluation_id, fixture)`;
- immutable day certificates, primary-model counts and common/purge eligibility.

Pairing must compare all economics, settlement, bucket and source fields exactly across required models, as `paired_day` does today. Missing an entire required model makes that date unavailable, not a smaller-source day. An empty common intersection remains explicit. Detect within-day duplicate model IDs before pairing; detect duplicate retained IDs across dates after applying the same eligibility/purge stages as the baseline.

Build development fixture membership from the **paired pre-purge development cohort**, then anti-join validation prints containing those fixtures. Preserve complete-empty dates, missing-date reasons and the provisional-purge status when development dates are absent. Eligibility must not depend on outcomes.

Index rows for `ORDER BY at, evaluation_id COLLATE BINARY` for each model. Store timestamps and pricing floats without lossy rounding and retain original bucket-family order. No model-specific sorting, ID integer conversion, timestamp bucketing or float-to-decimal repricing is permitted.

### 2. Stream the exact portfolio transition sequence

Port the current `run_backtest` loop into a separate iterator-based evaluator, with the same `BacktestConfig`, quote guards, edge thresholds, price/size/fees and reason precedence. Fixed variants remain sell-all, 0c, 0.1c, 0.3c, 0.5c per combo, and 0.3c per leg. Both funded and unlimited regimes remain present: **48 final runs**.

Use the existing `RiskLedger` with a disk-backed `EventStore` first, so the arithmetic and canonical risk behavior have a direct oracle. Configure a bounded SQLite cache, file-based temporary sorts and bounded WAL checkpoints. If measured SQL scans become a bottleneck, add a separate parity-tested integer aggregate ledger/cache afterward: committed cost, settled P&L and per-bucket active exposure must update in the same transition transaction. That optimization must preserve returned risk reasons/checks and must not net opposite combo exposures.

Persist pending settlements in an indexed table ordered by `(settled_at, evaluation_id)`. Before each trade, consume every settlement with time ≤ actual trade time in the same order as the baseline heap. A fixed-size fetch batch (for example 512 rows) bounds memory. Unresolved outcomes remain active/reserved; they cannot be aged out to control memory. Known future outcomes may be stored as scheduled research events, but allocation must see their cash only when the real settlement clock is reached.

Preserve the baseline's exact expressions: float `q*(1-p)+fee` followed by `risk.units` ceiling; `q*(1-outcome)` followed by the existing settlement-unit treatment; floored reduced concentration caps; original fees; unchanged fee effective dates. Do not opportunistically change rounding or replace baseline floating calculations with SQL `SUM(REAL)`/Decimal arithmetic in a scalability patch.

Emit each decision/fill to bounded output chunks or an indexed scratch output table immediately, referencing the immutable input payload instead of retaining copied source dictionaries. Reconstruct the existing full JSONL row schema during export. Do not accumulate `all_decisions`, `all_fills`, validation sets or a Python pending heap for the whole study. Unique indexes provide duplicate protection.

### 3. Curves and statistics without a full in-memory path

Persist curve deltas with timestamp, field, and **original evaluation/fill sequence**. A second external ordered pass reconstructs cumulative curves. Preserve the exact event timestamps, start/end endpoints and settlement cutoff behavior.

Floating addition order matters. `build_curves` accumulates evaluations in their original evaluation order and fill/settlement contributions in original **fill order** within each timestamp. The allocator's settlement heap order is not automatically the curve helper's floating aggregation order. Match each field's original contribution sequence before adding it in Python; do not let SQL group aggregation reorder sums. Likewise preserve trade-attribution changes and unknown-outcome bound accumulation in fill order.

Trade-time eventual P&L and edge remain a separate display layer. Spendable cash/risk still follows actual settlement. Baseline display curves use raw floating economic cost/P&L while the allocation ledger rounds integer reservation units; preserve that existing distinction for parity instead of silently reconciling it as part of this change.

Write every full curve row incrementally. Track peaks/drawdowns, funding requirements, totals, per-day contributions and outcome bounds incrementally. Keep only the small observed-date summaries in RAM; compute their variance/mean-SD ratio using the same existing statistics functions after all days are known. Missing calendar dates must not become fabricated zero-return observations.

Store fixture and combo concentration aggregates on disk where cardinality is large. Accumulate them in original selected-row order so floating totals match. Preserve the overlapping any-leg fixture interpretation and existing leave-one-fixture contribution calculations.

For plotting, reproduce `compact_curve` with two bounded passes: obtain full row count, compute its exact bucket size, then retain each bucket's endpoints and first-occurring minima/maxima for the same fields. This needs only current-bucket extrema plus the approximately 2,400 display rows. Load compact paths one figure/panel at a time. All four final figure families remain: funded/unlimited six-policy panels and funded/unlimited sell-all-versus-current-entry selections, in PNG and SVG.

### 4. Checkpoints, watcher behavior and output identity

Each run identity pins certified input hashes, normalization/purge identity, exact code and configuration. A checkpoint commits the input cursor, portfolio state, pending settlements, aggregate state and output watermark atomically. Publish compressed chunks/manifests only after matching durable state exists; do not claim a gzip append and SQLite commit form one atomic operation. On restart, recover to the last verified watermark and discard only unreferenced new scratch output, never original captures.

Do not simply append a new date's P&L. The acquisition order includes older dates arriving after later ones, and adding a development date can change validation fixture purging. Reuse a checkpoint only when every prior sorted input and purge decision in that prefix is identical. Otherwise replay the affected policy from an earlier valid checkpoint or start. This changes computation, not the experiment's trade order.

Coalesce newly completed dates while an evaluation runs; queue only the newest pending input identity. Full final 31-date output is mandatory. Intermediate publication checkpoints can be explicit, rather than retaining/rerunning every possible prefix by default. Coordinate chunk/content-addressed reuse and previous-version retention with the separate disk audit.

## Resource target and acceptance tests

Target **≤2GiB measured peak RSS for the replay worker**, independent of total prints, using one policy/regime worker, bounded parser/output batches (initially ≤2,000 model records), SQLite caches around 64MiB per active database, no large mmap and no unbounded in-memory query results. This is a proposed target, not an achieved benchmark. Instrument peak RSS, scratch size, WAL high-water mark, rows/s and output byte counts by stage. Enforce a disk reserve based on projected remaining output plus collector allowance; do not delete original data or reduce the sample to meet it.

First parity dataset: the existing exact July 1/15/29 inputs and three-date version above, **72,561 common prints and all 48 combinations**. Do not validate only the current 0.3c model or only funded runs: unlimited sell-all is the largest memory path.

Required parity checks:

1. Identical observed/missing/empty dates, per-source counts, common IDs, cross-date duplicate behavior and fixture purge results.
2. Identical ordered decisions, reasons, risk checks, accepted quantities, fees, reservations, fills and real settlement timing for every policy/regime. Compare decoded records, not gzip headers or dictionary serialization order.
3. Identical full curve timestamps/fields, known/unknown P&L bounds, committed cash, funding, drawdown and per-date/concentration summaries. Require bitwise float equality where the original arithmetic sequence is preserved; investigate rather than broadly tolerating selection differences. Display rendering may have nonsemantic metadata differences, but plotted input points must match.
4. Exact compact-curve selected timestamps/extrema and all final plot families/legends.
5. Existing synthetic invariants: settlement within a gap, still-open positions across missing dates, unknown outcomes, reduced risk multipliers, complementary canonical contracts, no target-size clipping, both threshold units, missing required model, cross-fold shared fixtures and fee rounding at a cap boundary.
6. New adversarial cases: many equal trade/settlement timestamps with different IDs; contributions that expose floating addition-order differences; many unresolved positions; cancellation/unknown-outcome placeholders remaining unresolved; interrupted ingestion and interrupted output commit; source hash mutation; older-date insertion changing a prefix; development-date insertion changing the validation purge.
7. A separate, clearly labeled scale fixture repeating structurally independent synthetic days to approximately 4.96 million model rows validates bounded memory/disk growth. It is a load test, never historical trading evidence. The complete actual 31-date run follows only after parity and resource measurements pass.

Suggested implementation order is the normalized disk input index, streaming evaluator and delta/metrics passes, then exact plot compaction/export, followed by checkpoint optimization. Keep the current three-date outputs as the oracle throughout. No full-study rerun or code change was performed for this audit.
