# Completed exchange catalog compression

`scripts/compress_completed_exchange_catalogs.py` is a separate one-shot workflow for only `dated_fee_primary/<date>/exchange/pm_events_complete.json`. Existing helpers and watchers are unchanged.

```sh
.venv/bin/python scripts/compress_completed_exchange_catalogs.py \
  --date 2026-07-01 --date 2026-07-15 --date 2026-07-29 \
  --out runs/morning_research_20260908/exchange_catalog_compression --execute
```

Without `--execute` it plans. With no date arguments it considers only declared batch dates and retains the same completion gates, permitting future idempotent reruns. Already-native-compressed catalogs are skipped. No background task is created.

Both the whole dated batch day and its exchange stage must be complete, with exchange exit code zero and no live retired child PID. The exchange acquisition and reviewed mapping output hashes must match their stage certificates. Catalog hashes and logical sizes are pinned to `pinned_inputs.json` before work. Files must be closed; the existing compression helper receives a callback that reattests the stage and checks `lsof` before the atomic swap. Hash/size and closed-file completion checks repeat afterward. Symlinks and files outside observed native size support are excluded. Compression changes only physical representation, preserving source bytes, path, file mode and mtime. No source catalog is deleted.

Executed only the three explicit July dates above; no August catalog was touched and no outcome contents were inspected. All three original SHA256 hashes match after compression.

| Catalog date | Allocated before | Allocated after |
|---|---:|---:|
| July 1 | 135,634,944 bytes | 21,000,192 bytes |
| July 15 | 137,777,152 bytes | 19,951,616 bytes |
| July 29 | 142,581,760 bytes | 22,044,672 bytes |

Total measured allocated saving: **352,997,376 bytes (336.64 MiB; 0.329 GiB)**. Exact hashes and completion evidence are retained in `runs/morning_research_20260908/exchange_catalog_compression/{pinned_inputs,summary}.json`.

A targeted test verifies refusal of an incomplete date, incomplete exchange stage and altered certified output. The native compression mechanics reuse the existing tested helper read-only.
