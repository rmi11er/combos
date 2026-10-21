# Parquet/DuckDB storage plan — September 9, 2026

DuckDB 1.5.5 is available in the virtual environment. A benchmark converting
the certified MLB replay rows to Zstandard-compressed Parquet produced:

| Dates | JSON source | Parquet output | Rows |
|---|---:|---:|---:|
| July 1, 15, 29 | 389.8 MB | 8.4 MB | 297,952 |

The converter is `scripts/convert_replay_to_parquet.py`; its manifest is
`runs/mlb_replay_parquet_20260909/manifest.json`. Each file records source and
output SHA256 hashes, row count and schema. The original JSON was not changed.

This is appropriate for **derived replay opportunities and pricing contexts**:
DuckDB can filter by model/date/time without loading the full JSON object, and
Parquet's column encoding removes repeated strings and nested structure very
efficiently. It is not a replacement for raw source evidence whose exact bytes
are part of a collection certificate, nor for the creator blacklist SQLite
database while it is actively receiving writes.

The migration sequence should be:

1. Convert every completed replay date to a new Parquet tree.
2. Verify row counts, source hashes, model/date coverage and economic-field
   equality against the original JSON.
3. Teach the streaming evaluator to consume Parquet directly, with one date
   read at a time and no multi-gigabyte SQLite input index.
4. Only after a complete parity certificate, archive or remove regenerated
   derived JSON. Keep raw tapes, fee evidence, mappings and creator evidence.

The benchmark shows that this should reduce the replay working set by roughly
two orders of magnitude. It does not by itself solve the 10 GB creator-evidence
database or guarantee enough room for all raw historical captures; those need a
separate retention/backup decision.

## Capacity estimate from the current worktree

The saved data inventory currently contains approximately:

| Category | Current bytes | Evidence-based replacement estimate | Potential saving |
|---|---:|---:|---:|
| Replay opportunities JSON | 5.29 GB | 0.11 GB Parquet, or about 0.30 GB including a compressed original archive | ~4.8–5.2 GB |
| Pricing context gzip | 1.05 GB | ~0.20 GB Parquet | ~0.8 GB |
| Exchange source JSON | 5.44 GB | ~0.3–0.7 GB compressed archive plus Parquet index, based on a 129 MB sample | ~4.7–5.1 GB |

The first three categories therefore offer a realistic **10–11 GB** recovery
while retaining lossless originals in Zstandard archives and a Parquet query
copy. The upper end assumes the sample compression ratios generalize; it is a
planning estimate, not a certificate. Other plain JSON is heterogeneous and
should not be included until individually benchmarked. Already-compressed JSON,
raw tape archives and active SQLite evidence databases should be assumed to
save little or remain unchanged until a separate snapshot/restore audit.
