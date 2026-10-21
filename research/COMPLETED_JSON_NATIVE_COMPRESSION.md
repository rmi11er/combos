# Transparent compression of completed generated JSON

`scripts/compress_completed_json.py` uses macOS `ditto --hfsCompression` to store eligible generated JSON with native filesystem compression. Original paths, logical bytes, SHA256 hashes and normal reader behavior remain unchanged. It does not substitute `.gz` paths or modify model inputs logically.

```sh
.venv/bin/python scripts/compress_completed_json.py \
  --batch-root runs/mlb_historical_20260907/dated_fee_primary \
  --timing-root runs/mlb_timing_sensitivity_20260907/july1 \
  --timing-root runs/mlb_timing_sensitivity_20260907/july15 \
  --out runs/morning_research_20260908/completed_json_compression \
  --max-files 20 --execute
```

The allowlist includes completed dated replay `opportunities.json`, certified plain `pricing_context.jsonl` if present, and explicitly supplied completed timing study `opportunities_extra{0,30,60,120}.json`. It excludes raw tape, exchange source data, gzip files, active stages and unrelated files. Timing outputs require summary, report, verified source-hash attestation and zero-lag parity.

Before mutation, the helper requires closed files using `lsof`, reattests the target's completion certificate, and verifies the source hash. A bounded native-compression probe verifies exact logical bytes and reduced allocated blocks. Compression writes a same-directory temporary file, checks logical size/hash, preserves mode/mtime, and compares source identity/hash again before atomic replacement. Files without physical allocation benefit are skipped. Full logical hashes are checked again after replacement.

Already-native-compressed files are skipped **before large-content hashing**. The file bound counts only uncompressed targets; previously handled files cannot starve future completed dates. Target reattestation does not repeatedly hash every other large replay. The script runs once, takes an output lock, and creates no watcher.

Executed first on three completed dated replays and eight completed timing JSONs: **11 files**, **1,216,319,488 allocated bytes saved (1.133 GiB)**, with all original logical SHA256 hashes preserved. Original execution code is retained at `runs/morning_research_20260908/completed_json_compression/executed_script.py`, and exact per-file evidence is in `summary.json`. A subsequent final-code idempotence run found nothing to recompress and saved zero, as expected: `completed_json_compression_idempotence/summary.json`.

The source snapshot differs from current code only because the subsequent optimization skips already-compressed content before hashing and bounds work by new targets. Current code and dependency hashes are recorded by each run.

Six tests cover closed-file refusal, corrupt-copy preservation, no-benefit skip, real native roundtrip/idempotence, completed-stage gating, target-only certificate checking, and no rehash of native-compressed candidates. Together with the five gzip clone tests, **11 tests pass**.

This solves the primary JSON compatibility obstacle identified in `MLB_PREFIX_STORAGE_AUDIT.md`; readers retain their original paths and hashes. It does not change the recommendation to avoid retaining every full longitudinal prefix. Compression savings are measured from per-file allocated blocks; concurrent system activity can make total filesystem free-space changes differ.
