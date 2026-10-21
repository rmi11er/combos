# Retained-prefix storage and exact-byte deduplication

Follow-up audit around September 8, 2026 02:15–02:22 UTC. The earlier approximately 40 GiB remaining-storage estimate omitted repeated full longitudinal and validation ledgers. That omission materially changes the capacity conclusion.

## Quadratic growth is real

The longitudinal watcher reruns all four models × six policies × two funding regimes whenever a new completed input set appears. Each version writes full decisions, curves and fills for every observed date. Current retained versions:

| Completed dates | Longitudinal size | Validation size |
|---|---:|---:|
| July 1 | 325.2 MiB | 66.4 MiB |
| July 1 + July 15 | 330.6 MiB | 67.4 MiB |
| July 1 + July 15 + July 29 | approximately 672 MiB | 130.6 MiB |

July 15 is an unusually small slate, so the two-date version is not representative of two active MLB dates. At July 1's active-date intensity, retaining every prefix gives `1+…+31=496` date-equivalents: approximately **157.5 GiB longitudinal**, plus a conservative **32.2 GiB validation**, or **about 190 GiB**, before the raw data and dated reports. Validation includes a repeated September reference; a more refined estimate reduces its figure somewhat, but does not change the disk-full conclusion.

The current 42 GiB free space is insufficient for the unchanged retention pattern. This is a derived-output retention problem, not a reason to reduce the 31-date dataset.

## Future longitudinal cadence

Preserve the three already-created versions, plots, input identities and frozen code. At a verified idle boundary, stop only the longitudinal watcher; the collection and dated batch remain running. Future execution can use the **unchanged existing script without `--watch`**:

```sh
.venv/bin/python scripts/mlb_longitudinal_sweep.py \
  --batch-root runs/mlb_historical_20260907/dated_fee_primary \
  --plan config/mlb_validation_20260907_expanded.json \
  --out runs/mlb_historical_20260907/longitudinal_checkpoints \
  --poll-seconds 30 --max-runtime-seconds 172800
```

A separate orchestrator should invoke that command only at an explicitly selected checkpoint and at final certification of all 31 dates. **Final-only full-ledger recomputation minimizes storage.** An optional five-screen-date checkpoint costs roughly another 1.3 GiB at observed activity. Recomputing every date is unnecessary for preserving the final strategy comparison; dated model reports, pooled calibration and lightweight summaries can keep progressing separately.

Do not kill a current simulation mid-write or relabel a partial version complete. Record the retired watcher PID/status, immutable latest version, source hashes and new checkpoint policy. Root is handling this transition; this audit did not change the watcher.

Final-only longitudinal still costs around **9.8 GiB** at July 1 intensity. Together with roughly 39 GiB remaining raw/dated outputs and 1.6–2 GiB distinct validation ledgers, this remains above current free space once other consumers are included. Cadence solves the quadratic explosion, but is not by itself proof that all final artifacts fit.

## Exact-byte APFS dedup solves duplicated validation storage

Core batch validation runs at every prefix, but its required completed-stage output is `validation.json`. Its per-date independent experiments often produce identical gzip bodies across prefixes. Actual tests found July 1's 19,630,276-byte unconstrained decision files and 5,603,442-byte constrained curve files equal across three versions **except gzip timestamp bytes 4–7**.

The new `scripts/deduplicate_validation_clones.py` preserves every original path and every original compressed SHA256:

1. Require a completed batch validation-stage certificate whose `validation.json` hash still matches and whose retired child PID is absent.
2. Consider only the six known per-date generated validation ledger filenames. Ignore active stages, symlinks, raw data and unrelated files.
3. Group files only when their full compressed bytes match after normalizing the four gzip timestamp bytes.
4. Probe native `clonefile` support and copy-on-write behavior using a bounded 1 MiB temporary file.
5. Verify source and destination are closed using `lsof`; create an APFS clone into a same-directory temporary path, restore the destination's original four timestamp bytes, and verify the full reconstructed compressed SHA256 equals the original.
6. Recheck source/destination identity, source hash and closed destination; atomically replace the destination with its byte-identical clone. Verify both full hashes again. Persist receipts.

Because only the clone's first filesystem block changes, APFS can share the remainder. This is not a lossy archive or a deletion of records: ordinary gzip readers, paths, contents and existing hash references remain valid. The dedup command can run after future completed validation checkpoints without modifying frozen batch code:

```sh
.venv/bin/python scripts/deduplicate_validation_clones.py \
  --batch-root runs/mlb_historical_20260907/dated_fee_primary \
  --out runs/morning_research_20260908/validation_clone_dedup \
  --max-files 1000 --execute
```

Default without `--execute` only plans. Receipts avoid recloning unchanged processed paths. No background watcher is created.

**Executed on the current three completed validation prefixes:** 30 files replaced with exact-byte clones; all reconstructed hashes matched. Logical duplicate body bytes: **139,079,947 bytes (132.64 MiB)**. Filesystem free bytes moved from 44,621,144,064 to 44,762,660,864 during the operation. That change is recorded, but concurrent activity, APFS snapshots and shared-block accounting prevent treating it as a guaranteed isolated physical saving. `st_blocks` before/after per file is recorded and may continue counting shared extents.

Evidence: `runs/morning_research_20260908/validation_clone_dedup/summary.json` and `receipts.json`. Five targeted tests pass, including native copy-on-write probing, exact-byte reconstruction, open-file rejection, different-payload rejection, corrupt-clone protection and completed-stage validation.

If this pattern persists, validation's duplicate bodies can occupy approximately one distinct per-day result rather than 31 expanding prefixes: roughly **1.6–2 GiB**, plus small plots/JSON and any genuinely changed validation-purge results. Different payloads are never forced into the same clone group.

## Reversible gzip candidates and remaining headroom

The initial candidate audit below preceded the authorized transparent-compression follow-up; see the update below. No logical data bytes were changed.

The completed timing studies retain four generated `opportunities_extra*.json` files per date. July 1 totals approximately **881.6 MiB** uncompressed. A streaming compression-size probe on `opportunities_extra0.json` produced **9,956,398 bytes** from **231,355,100 bytes**, saving **211.14 MiB**. All four likely recover approximately **0.82 GiB**. The timing script writes these files but has no subsequent script reader for them in the current repository; verify no open process before archival. Keep `summary.json`, `verification.json`, reports and all original-hash references. A safe archive manifest must contain original path/length/SHA256 and compressed SHA256, then verify full decompression against the original before reclaiming the uncompressed generated copy. Restoration must recreate the exact original bytes/path before rerunning a consumer.

Other large files compress well but are **not immediately eligible** while frozen consumers depend on their original paths:

- July 1 primary replay `opportunities.json`: 169,151,003 bytes → 8,910,290 bytes, potential 0.149 GiB saving. Current watchers repeatedly load/hash original replay paths; do not replace them with gzip during the active run without a separately versioned archive-aware consumer.
- July 1 `exchange/pm_events_complete.json`: 135,633,157 bytes → 11,455,012 bytes, potential 0.116 GiB saving. This is source evidence used by mapping overlays, not an expendable derived ledger. Preserve its readable original for current consumers; future source-storage design can use a verified compressed representation.

At approximately 30 active dates, compressing both classes eventually saves roughly 8 GiB, but that potential cannot be booked as current headroom while their original-path dependencies remain active. Existing verified scratch-index archival must continue. Do not archive or delete raw tape to make derived prefix outputs fit.

## Decision

Retire per-date full longitudinal prefix recomputation at an idle checkpoint, retain existing versions, and use explicit checkpoint/final execution. Continue exact-byte completed-validation clone dedup after future checkpoints. These measures address the largest avoidable growth without changing models, scope, inputs or recorded byte hashes.

Even after those changes, maintain the existing free-space monitor and review at 20 GiB, urgently at 15 GiB. Budget the final full ledger before launching it. If headroom remains insufficient, use a separately versioned final runner that retains all policy results but emits full row-level ledgers only for explicitly selected audit policies, or arrange additional storage; do not silently discard existing artifacts, reduce the dataset or pretend that deterministic recomputability alone is a lossless archive of existing files.

## Transparent-compression follow-up

The source-path obstacle above was subsequently resolved for generated primary and timing JSON using native APFS/HFS compression, preserving original paths and logical hashes. Eleven completed JSON files reclaimed 1.133 GiB of allocated storage; no raw source files were touched. See `COMPLETED_JSON_NATIVE_COMPRESSION.md` for exact scope, checks and receipts. The plain `.gz` archival caveat still applies to changing file paths, but no such path change is needed for native compression.
