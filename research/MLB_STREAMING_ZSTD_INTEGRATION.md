# Optional Zstandard streaming replay artifacts

The standalone streaming runner and snapshot wrapper now accept `--artifact-codec gzip|zstd`; gzip remains the default. Decisions, fills and full-resolution curves use the verified `replay_artifact_io.text_writer`, which publishes complete streams into new paths atomically and refuses overwrites. Zstandard uses `.jsonl.zst`; gzip retains `.jsonl.gz`. No economics, price selection, fees, risks, summary computations, raw inputs or plot data changed.

Artifact format version 2 and codec metadata appear in the summary/completion receipts. Zstandard executable path, SHA256, CLI version and compression arguments are captured and checked again at completion. The snapshot wrapper retains its source/plan stability checks and hashes every output. Existing gzip replay readers remain usable for default outputs; the parity verifier now resolves exactly one gzip or Zstandard artifact on each side and compares decoded JSON rows exactly, recording decoded text hashes too. Ambiguous dual suffixes fail closed.

Only these existing standalone files changed: `mlb_streaming_longitudinal.py`, `run_mlb_streaming_snapshot.py`, and `verify_mlb_streaming_parity.py`. All are absent from the frozen dated batch closure. All **58 frozen source hashes still match**; the archived original streaming sources remain at `runs/mlb_longitudinal_streaming_verified_20260907/verified_source_archive`. The verified codec helper itself is unchanged.

Validation: **34 tests passed** across streaming economics, snapshot guards, codec I/O and five new codec integration cases. New tests run actual native Zstandard, compare decoded bytes and complete economics/compact curves against gzip in funded/unlimited modes with known and unknown outcomes, cover empty streams, and reject ambiguous or invalid codecs. Existing tests cover chronology, duplicate IDs, fractional risk, settlement ties, atomic publication and failed/truncated codec streams.

## Three-date parity run (completed and verified)

A separate certificate projection at `runs/mlb_streaming_zstd_parity_inputs_20260908` pins July 1/15/29 and symlinks only those completed day directories. This prevents later collector completions from expanding the parity input cohort. It copies completion certificates without changing daily data and retains the original expanded plan, so missing-date coverage remains comparable to the oracle.

Root ran the following after storage review:

```sh
.venv/bin/python scripts/run_mlb_streaming_snapshot.py \
  --batch-root runs/mlb_streaming_zstd_parity_inputs_20260908 \
  --plan config/mlb_validation_20260907_expanded.json \
  --artifact-codec zstd \
  --out runs/mlb_longitudinal_streaming_zstd_parity_20260908

.venv/bin/python scripts/verify_mlb_streaming_parity.py \
  --oracle runs/mlb_longitudinal_streaming_verified_20260907 \
  --candidate runs/mlb_longitudinal_streaming_zstd_parity_20260908
```

The output must be new. Successful completion must verify 48 policies, 144 decoded row artifacts, all economic fields and order, matching compact PNGs, valid SVGs, and source/input/codec/output receipts. The three-date full-policy replay and exact verifier have now completed; no data was deleted. The expected final-scale storage reduction is a forecast until measured; Zstandard does not reduce the SQLite input or sequential scratch requirements.


Root verification: all 48 policies and 144 row artifacts match the retained gzip reference exactly, including decoded bytes: 3,482,928 decisions, 364,804 fills and 3,545,353 curve rows. There are zero summary rounding exceptions; all four PNGs are byte-identical and SVGs parse. All 16 source hashes and 155 output hashes were independently checked. Replay took 228.30 seconds with 704,823,296 bytes peak RSS. Row artifacts shrink from 763,914,189 to 585,220,276 bytes, a measured 178,693,913-byte (23.39%) saving. This verifies three-date format parity, not full-period strategy validity or sufficient storage for all remaining work. Evidence: `runs/morning_research_20260908/zstd_root_verification.json` and candidate `parity.json`.

## Source-disagreement downstream compatibility

The longitudinal source report now honors the summary-declared gzip/Zstandard codec, defaults legacy summaries to gzip, rejects unknown codecs and records its I/O helper hash. No pricing logic or frozen batch source changed. All 24 focused source-disagreement/artifact tests pass. Root verified complete July 1/15/29 economic parity for both 0.3c/combo and 0.3c/leg variants: 72,561 common prints per variant, with identical all-common, grouped and fixture-deletion metrics. Input/source hashes reconcile. Evidence: `runs/morning_research_20260908/longitudinal_disagreement_codec/{verification,root_verification,focused_test_receipt}.json`. This establishes format compatibility, not the full-period research result.
