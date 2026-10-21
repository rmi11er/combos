# Updated storage forecast: all 31 MLB dates, NFL and one final 48-policy snapshot

Read-only inspection around September 8, 2026 02:48–02:52 UTC. No files were compressed, vacuumed, removed or modified by this audit. Frozen storage helpers remain unchanged. Current measured free space: **39.84 GiB**.

## Updated measurement

Three dated MLB reports are complete (July 1, July 15 and July 29); August 12 cohort indexing is active. NFL raw collection has 163 of 336 hourly partitions completed at the sampled status. Full longitudinal prefix recomputation is no longer assumed in this forecast.

Allocated dated report sizes after existing primary-JSON compression and scratch archival:

| Date | Allocated report tree |
|---|---:|
| July 1 | 961.1 MiB |
| July 15 | 287.8 MiB |
| July 29 | 1,039.8 MiB |

The two active slates average **about 1,000 MiB/date (0.977 GiB)**. July 15 is unusually quiet; extrapolating its size to the remaining calendar would be misleading.

Raw tape averages remain approximately **0.339 GiB/date**. Raw tape is separate from the dated report trees. Twenty-seven dates beyond the four already collected/in-progress tapes imply approximately **9.2 GiB** of additional raw storage, subject to changing volume and the current partial August 26 collection.

The completed three-date streaming verification directory measures **785.1 MiB of non-SQLite artifacts plus 471.5 MiB allocated input SQLite**. Its three dates contain approximately two active slates and one quiet date. A final 31-date snapshot therefore plausibly requires:

- **8–12 GiB** for one set of all 48 policy decision/curve/fill outputs, extrapolating between per-calendar-date and per-active-date intensity.
- **4.8–7.1 GiB** for its uncompressed ingestion/input SQLite at current structure, including its retained free pages.

The second item was missing from earlier forecasts of the final non-streaming snapshot. Streaming fixes RAM growth, but does not itself eliminate disk storage for the input index.

## Remaining capacity estimate

Planning range, not a hard upper bound:

| Remaining consumer | Additional GiB |
|---|---:|
| 28 not-yet-completed dated report trees | 24–29 |
| Remaining MLB raw tape | 8–10 |
| Distinct validation outputs with APFS duplicate sharing | 1.5–2 |
| One final 48-policy output set | 8–12 |
| Final streaming input SQLite | 4.8–7.1 |
| Remaining NFL raw/cohort/report work | 1–3 |
| Temporary compression/indexing headroom | 1–2 |
| **Total** | **48.3–65.1** |

Some current August 12 bytes are already included in existing used space, so extrapolating all 28 report trees slightly overstates incremental growth; this small overlap does not remove the shortfall. Against **39.84 GiB free**, the present layout has a plausible **8.5–25.3 GiB shortfall**. Midrange is approximately 17 GiB. These estimates exclude unrelated applications consuming additional disk and do not assume another full snapshot at every prefix.

The right conclusion is **not yet proven to fit**, even after the existing exact-byte maintenance. Native compression of additional completed artifacts can recover several GiB, but should not be presented as guaranteeing enough room for the whole plan.

NFL estimate basis: current raw pages total 10,849 and 0.412 GiB compressed, while completed/in-progress cohort directories occupy about 269 MiB and exchange history about 2.6 MiB. Remaining playoff trading windows may be busier, so a simple proportional estimate is insufficient; the 1–3 GiB allowance is deliberately broad. Existing request ceilings bound requests, not response bytes.

## Closed generated SQLite free pages

Read-only SQLite PRAGMAs found:

| Path | Logical size | Free pages | Free-page bytes |
|---|---:|---:|---:|
| `runs/mlb_longitudinal_disk_20260907/input.sqlite` | 469.5 MiB | 71,306 | 278.5 MiB |
| `runs/mlb_longitudinal_streaming_verified_20260907/input.sqlite` | 469.5 MiB | 71,306 | 278.5 MiB |

These two databases contain **557 MiB of reusable/free SQLite pages** in total. At initial inspection `lsof` showed no database handles, although the streaming parity verifier was still active elsewhere in its output directory; root subsequently confirmed that verification finished. Recheck closed-file and completed-snapshot state immediately before any maintenance.

**Do not VACUUM certified originals in place.** VACUUM changes file bytes and therefore their certified SHA256. Native transparent compression, if separately authorized and proven compatible with the exact SQLite files, can preserve all original bytes and paths while compressing both free and occupied pages. A future fresh snapshot could compact its input index before producing its final certificate, with a new frozen implementation and validation; that is different from rewriting an already-certified file.

Eight evenly spaced 8 MiB zlib probes (64 MiB sampled per file) gave a **10.86% compressed ratio** for each input database. This suggests substantial potential, roughly 0.8 GiB across both, but it is **not a native-filesystem compression guarantee**: native block/dictionary sizes and page layout differ. The exact allocated saving must be measured after any approved operation.

The active August 12 `cohort/tape_index.sqlite` is about 403 MiB logical/416 MiB allocated and has zero free pages. It must remain untouched until its stage is complete; the existing archive watcher already handles this case.

## Other large closed candidates, for explicit review only

These paths were not altered and are not on the frozen JSON helper's allowlist. Any maintenance needs its own explicit bounded scope, closed-file/WAL checks, exact-byte hash verification and receipt. Some contain retained source-derived evidence, so preservation is essential.

| Path | Allocated GiB | Free pages | Sample zlib ratio | Interpretation |
|---|---:|---:|---:|---|
| `runs/nfl_capture_20260906_2234/events.sqlite` | 4.359 | effectively zero | 67.35% | Retained capture evidence, not disposable scratch; modest compression potential |
| `data/derived/rfq_sniffer/evidence_v2.sqlite` | 4.178 | zero | 26.80% | Derived blacklist evidence; preserve all data and associated journal state |
| `runs/cfb_performance_audit_20260907/market_benchmark/native_metadata.sqlite` | 1.078 | zero | 7.74% | Completed metadata analysis cache; strong candidate for exact-byte native compression |
| `runs/mlb_historical_20260907/cohort/metadata_index.sqlite` | 0.734 | zero | 7.31% | Completed older cohort metadata cache; strong candidate for exact-byte native compression |

The first two had no `lsof` database handles in the sampled check. The latter two were opened only through read-only audit connections; a fresh full sidecar/journal open-handle check is still required before modification. Do not infer quiescence from age alone.

The sampling-based upper aspiration across these four candidates is about 6 GiB saved; use **3–5 GiB as a provisional planning allowance**, not a booked capacity gain, until exact native tests and allocated-byte measurements are complete. Retained evidence databases may later be reopened for writes, which can undo native compression gains; they cannot be treated as permanent cold-storage savings without a lifecycle decision.

The largest plain JSONs still uncompressed are completed `exchange/pm_events_complete.json` files: approximately 129, 131 and 136 MiB allocated for July 1, July 15 and July 29. These are exchange source evidence, **not current helper candidates**. Exact-path native compression could preserve readers and hashes, but needs a separately authorized source-evidence policy; no automatic expansion of the frozen allowlist is recommended. A completed July 1 whole-file zlib probe previously suggested roughly 119 MiB potential saving. The three current files offer only around 0.35 GiB, though similar per-date growth becomes material over 31 dates.

## Recommended next maintenance and final-run gate

1. Keep collection, dated analysis, existing JSON compression, verified completed-index archival and validation clone dedup unchanged. No raw-data deletion and no reduced date scope.
2. Review a new bounded native-compression operation for the **two finished generated streaming input SQLite files and the two completed metadata-analysis SQLite caches**, after checking all DB/WAL/SHM handles and final certificates. This is the clearest low-impact next step; preserve exact bytes, paths and hashes, and measure allocated savings rather than estimating them.
3. Separately assess cold retained capture/sniffer evidence compression if more room is needed. Never mix this with automatic scratch cleanup or assume zero free pages means zero compression potential.
4. Before the final all-31-date snapshot, reserve room for **the input database as well as the 48-policy artifacts**. Do not launch on an assumption that streaming means low disk use.
5. Continue the existing 20 GiB review / 15 GiB urgent-review telemetry. For final snapshot launch, use a workload estimate from the actually collected paired-print count; require that estimate plus at least 5 GiB operational margin. If that reserve is unavailable, additional storage or a separately validated more compact future output representation is necessary. Recomputability is not permission to discard current artifacts.

The remaining shortfall must be recalculated after measured maintenance and more dated slates complete. All 31 dates and every policy remain in scope; the storage concern affects execution scheduling and representation, not which research gets done.

## Root follow-up checks

A broader inventory found `data/derived/rfq_sniffer/evidence_v2.sqlite-wal` occupies another 3.000 GiB allocated. The sniffer main database must not be treated as a complete cold dataset independently of this WAL. It is excluded from the first four-generated-database operation. A read-only normalized-gzip hash audit across all >1MiB gzip files in the three completed daily report trees found zero duplicate groups, so no additional daily-body clone savings are booked. Evidence: `runs/morning_research_20260908/storage_daily_duplicate_audit.json`.

## Measured first maintenance pass

Root executed the separately tested four-database workflow. Both streaming input databases were transparently compressed with exact original hashes, logical sizes and successful SQLite quick checks. Savings were 828,571,648 allocated bytes (790.19 MiB / 0.772 GiB) combined. The CFB and older MLB metadata caches showed no native physical-compression benefit and were not replaced. This supersedes the roughly2.5GiB aspiration for those four files: only0.772GiB is booked. Root independently rehashed and quick-checked all four afterward. Receipts: `runs/morning_research_20260908/generated_sqlite_compression/summary.json`; pinnedmanifest: `config/generated_sqlite_compression_20260908.json`. The storage shortfall remains unresolved and current collectors continue.

### Native size-limit probe changes the next action

A temporary synthetic repeated-byte probe found that 480 MiB compressed to 4,243,456 allocated bytes with native flag 32, while 520 MiB remained 545,259,520 bytes without that flag. The generated probe files were removed with their temporary directory. The exact threshold was not identified, but this demonstrates size-dependent refusal between 480 and 520 MiB on this machine; source entropy does not explain it. Evidence: `runs/morning_research_20260908/generated_sqlite_compression/native_size_probe.json`.

Do not extrapolate successful 469.5 MiB input compression to the projected 4.8–7.1 GiB final index or 4 GiB capture databases. Further capacity work requires a separately validated compact final representation and/or lossless archival with verified restoration, keeping all source evidence and every decision/curve available. Existing raw data and certified outputs have not been removed.

## Completed catalog maintenance

The three completed July `pm_events_complete.json` catalogs were transparently compressed, saving 352,997,376 allocated bytes (0.329 GiB). Root independently verified original source hashes and logical lengths afterward. Completion and inactive/open-handle guards remain enforced by the separate `scripts/compress_completed_exchange_catalogs.py`; existing frozen watchers are unchanged. Retain a new output directory for each future maintenance checkpoint so receipts are not overwritten. Combined measured savings from the generated SQLite and catalog passes are 1,181,569,024 bytes (1.100 GiB). No August catalog or outcome was inspected.

## July 21 completion maintenance

Eight newly completed July exchange catalogs were transparently compressed, saving 911,937,536 allocated bytes (0.849 GiB). Root independently verified every original hash and logical length after compression. July1/15/29 were already compressed and skipped. No raw tape or August outcomes were changed or inspected. Receipt: `runs/morning_research_20260908/catalog_compression_july21/root_verification.json`. This saves space but does not prove sufficient capacity for all remaining processing and final snapshots.

## July25 completion maintenance

The two newly completed July23/25exchange catalogs were transparently compressed with the same certified inactive-file workflow. Measured savings:241,291,264bytes (0.225GiB); both original hashes and logical lengths independently verified. Receipt: `runs/morning_research_20260908/catalog_compression_july25/root_verification.json`. Free space was approximately12GiB before this operation. This small saving does not establish capacity for remaining dates or final snapshots; active sniffer database/WAL remain untouched.
