# Lossless longitudinal storage codec audit

No frozen source or existing research artifact changed. Three representative complete files from the verified three-date, 48-policy snapshot were read: Kalshi unlimited sell-all decisions, fills and curves. Their full decoded gzip streams were compressed, then decompressed and verified against exact SHA-256, byte length and line count. No JSON rows were parsed/reformatted or omitted.

## Measured codecs

XZ uses Python stdlib `lzma`, preset 6, default CRC64. Zstandard uses installed `/opt/homebrew/bin/zstd`, version **1.5.7**, command `-q -6 -c`, default single-thread/window settings; no dependency was installed. Both receive 1MiB chunks from gzip decoding.

| Family | Rows | Gzip MB | XZ MB | XZ saving | XZ encode s | Zstd MB | Zstd saving | Zstd encode s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| decisions | 72,561 | 10.88 | 5.48 | 49.6% | 27.825 | 7.33 | 32.6% | 0.171 |
| fills | 72,561 | 6.07 | 4.38 | 27.8% | 18.036 | 5.61 | 7.4% | 0.097 |
| curves | 90,891 | 9.32 | 6.14 | 34.1% | 49.513 | 8.89 | 4.7% | 0.153 |

XZ driver peak RSS was **138.7 MiB**. Zstd compressor peak RSS, measured separately using `/usr/bin/time -l`, was **63.1 MiB**; the Python driver was 29.5 MiB. Compression timings include gzip decode and pipe/write overhead. XZ verification took 0.47–0.78 seconds per file; Zstd verification 0.03–0.09 seconds. All six round trips passed exact decoded SHA/length/row-count verification.

XZ temporary outputs were removed only after successful verification, before creating the three Zstd temporary outputs. Thus at most three codec output files existed at once. The three verified `.zst` files and complete `measurement.json` are retained under `runs/mlb_storage_codec_audit_20260907`. Source gzip files remain untouched.

## Full-scope projection and limits

Use the measured family-specific ratios against actual totals for all 48 gzip policies, then scale from 72,561 to the inherited planning estimate of 1,240,000 common prints. This is an estimate: funded versus unlimited records differ, changing dictionary repetition/compression. Three representative files do not certify all 48 compression ratios.

| Representation | Estimated final GiB | Saving versus gzip GiB |
|---|---:|---:|
| Gzip | 12.16 | — |
| XZ preset 6 | 6.70 | 5.46 |
| Zstd level 6 | 9.15 | 3.01 |

**Neither codec alone closes the stated 8.5–25GiB disk shortfall.** Zstd plus estimated per-row index compression still saves only about 3.70GiB at this scope; XZ plus index compression about 6.15GiB. Root must combine this with other storage measures or additional capacity; do not claim the final run now fits.

XZ materially increases CPU time: the decisions representative alone implies about 6.3 hours for 48 equal-sized decision streams at 1.24 million prints, before curves, fills and evaluation. This deliberately simple extrapolation is not a benchmark of the final workload. Zstd offers a much better observed runtime/storage tradeoff, though the curve and fill savings at level 6 are modest.

## Compressed JSON payload index: feasibility, no implementation

The current index stores queryable IDs/timestamps/model/fixture membership separately from exact shared and per-model JSON TEXT. A new format can retain these query columns and change only JSON payload columns to BLOB containing `zlib.compress(utf8, 6)`. Its iterator would decompress one row before the existing `json.loads`; ordering, fees, source values and economics remain unchanged. Record an explicit codec/schema version in metadata and reject unknown codecs. No whole-database decompression or native filesystem compression is required.

| Payload | Rows | Original UTF-8 MB | Zlib6 MB | Saving MB |
|---|---:|---:|---:|---:|
| prints.shared | 72,561 | 81.08 | 46.86 | 34.22 |
| models.payload | 290,244 | 54.85 | 45.62 | 9.24 |

**All 362,805 payloads were independently compressed/decompressed and byte-verified**, without writing a new index. Actual SQLite pages were not reallocated; this is a payload-size measurement, not a promised final SQLite file size. Estimated raw payload reduction at 1.24 million prints is only **0.69GiB**. Index overhead, page packing and reusable staging free pages must be measured in a new version. It is feasible and memory-bounded but not the largest storage lever.

## Recommended smallest safe next change

1. Implement a **separate versioned Zstd artifact writer/reader**, leaving existing gzip outputs and frozen sources intact. Write `.jsonl.zst` directly during the final replay, using the installed pinned CLI with bounded pipes; do not first build a full gzip copy. Final manifests should record codec/version plus compressed and decoded hashes/lengths. Check subprocess exit status before publishing the final snapshot marker.
2. Preserve every decision/fill/full curve and all 48 policy outputs. Provide an iterator that selects gzip or Zstd from explicit format metadata/suffix, and a bounded export command that streams Zstd-decoded bytes into ordinary `.jsonl.gz` for old consumers. Never place XZ/Zstd bytes behind a `.gz` suffix. The existing three fixed gzip opens and the hardcoded parity reader cannot consume Zstd unchanged; use a new adapter/version, not a silent import substitution.
3. Require full decoded oracle parity on all 48 policies, unchanged summary/plot inputs and encoder failure/partial-file tests. No repricing, quantity reduction, row dropping or curve downsampling belongs in this change.
4. Consider the compressed-payload index only after root identifies the remaining disk gap. Its prospective 0.69GiB reduction does not justify claiming the storage problem solved. A higher Zstd level or a normalized decision-reference format could be a further bounded experiment; neither is measured or recommended as already validated here.

Plain Zstd is the least complex practical codec improvement observed. XZ is appropriate only if its additional roughly 2.46GiB saving at this scope is worth the much longer measured compression time. Whole-SQLite archival compression would help retained storage after a run but would not remove the need for an accessible index during replay; it is not a solution to peak active-index space by itself.

Measurement workflows: `scripts/measure_mlb_xz_storage.py` and `scripts/measure_mlb_zstd_storage.py`. All benchmark subprocesses finished; no background jobs remain.
