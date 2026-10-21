# Complete-cohort disk-backed longitudinal replay

This is a separate research implementation. The frozen `mlb_longitudinal_sweep.py`, `BacktestConfig`, `RiskLedger`, daily replays and three-date oracle remain unchanged. No provider requests or orders are involved.

## What changed

- `scripts/mlb_disk_index.py` incrementally parses certified daily replay JSON, performs exact four-model pairing, cross-fold fixture purge and global `(at, evaluation_id)` ordering in SQLite. Shared print economics are stored once; model-specific fields remain exact JSON. It rejects duplicate IDs, changed hashes, incomplete calendars and inconsistent paired economics. All complete eligible prints are retained.
- `scripts/mlb_streaming_longitudinal.py` evaluates one policy/regime at a time using the existing disk-backed risk ledger. It streams decisions/fills immediately and stores ordered curve deltas, pending actual settlements, duplicate IDs and combo concentration on disk. Input batches are 1,000 rows and settlement batches 512. No unknown position expires to conserve memory.
- Curve construction preserves evaluation/fill addition order, including same-timestamp settlement contributions. Known eventual P&L is attributed to trade time; spendable cash is released at actual settlement. Baseline integer reservation rounding and raw-float display curves remain distinct and unchanged.
- Summaries use compensated streaming sums for the original Python `sum` statistics; per-fixture and combo accumulation preserves original ordering. Full-resolution curves are saved. Only the exact original approximately 2,400-point extrema representation is retained for each plotted policy.
- `scripts/verify_mlb_streaming_parity.py` compares all decoded decisions, fills and curve rows exactly; quantities, fees, risk decisions and timestamps have no tolerance. Only aggregate summary display floats permit a tightly bounded rounding comparison, with every such difference listed in its output.
- `scripts/run_mlb_streaming_snapshot.py` is the production research entry point. It refuses an existing output directory, pins code and plan, records immutable input metadata/hashes and hashes every output. `snapshot_complete.json` is its final publication marker. A failure leaves diagnostics without that marker.

The configurations remain four exchange fair models × six entry variants × funded/unlimited = 48 policies. Funded limits remain $10,000 capital, $100 contract, $100 combo and $250 fixture; no ticket cap. These are full observed-print fills or rejections, preserving the oracle. The separate partial-sizing study is not silently substituted.

## Restart and scheduling

This first implementation deliberately replays a fresh certified snapshot from the beginning. It does not append a newly collected older date, reset cash by day, or reuse a ledger after development fixtures change validation eligibility. It has no mid-policy checkpoint resume: interruption requires a new output directory. This trades repeated computation after interruption for clear correctness, while avoiding the old automatic rerun after every completed date.

Root should launch one final run when the intended 31-date cohort is certified, or explicitly choose a new intermediate snapshot. Missing dates stay explicit; `snapshot_complete.json` means the selected certified snapshot finished, not that all planned dates were collected.

```sh
.venv/bin/python scripts/run_mlb_streaming_snapshot.py \
  --batch-root runs/mlb_historical_20260907/dated_fee_primary \
  --plan config/mlb_validation_20260907_expanded.json \
  --out runs/mlb_historical_20260907/longitudinal_streaming/FINAL_NEW_ID
```

The wrapper must own its foreground process. No agent-owned background collector or replay should survive the agent's turn.

## Verification

The index contains **290,244 model rows / 72,561 unique prints** from July 1, 15 and 29. Every decoded input dictionary matches original `prepare`: 31,263 + 392 + 40,906 common prints. Index parity artifact: `runs/mlb_longitudinal_disk_20260907/index_parity.json`. Index construction took 11.38 seconds with **499,204,096 bytes measured peak RSS**.

Twenty-three tests cover source/parser/pairing/purge invariants, duplicate rejection, exact synthetic parity across all entry variants and both regimes, shared timestamps, settlement within calendar gaps, unresolved positions, reduced risk multipliers, fractional cap boundaries, quote guards, no fills, exact plot extrema/tie behavior, refusal to overwrite output and suppression of a completion marker after a code change.

The first full run completed all 48 policies in **294.09 seconds after ingestion**, with **822,132,736 bytes (~784 MiB) measured evaluator peak RSS** before plot rendering. The subsequent decoded oracle audit took 135.17 seconds and checked **3,482,928 decisions, 364,804 fills and 3,545,353 full curve rows**: every row was exactly equal, and every summary metric matched with **zero tolerated rounding differences**. All four PNG files are byte-identical to the oracle. The PNG selection panel was visually inspected; legends, date gaps and axes render correctly.

The finalized wrapper run is `runs/mlb_longitudinal_streaming_verified_20260907`. It completed all **48 policies and 155 hashed artifacts in 310.68 seconds end-to-end**, including certified ingestion, plotting and output hashing. Its measured peak RSS is **838,402,048 bytes (799.6 MiB)** including plotting, comfortably below the 2GiB target. `snapshot_complete.json` confirms unchanged code/plan hashes and includes source/input/output hashes. The direct final-code oracle comparison completed successfully and is saved alongside it as `parity.json`: all 48 policies, all 144 decoded row artifacts, identical quantities/fees/decisions/order/curves and zero summary rounding exceptions. All four PNGs are byte-identical; all four SVGs parse as valid XML.

These measurements use the entire available three-date common cohort, without a sample cap. At the observed throughput, 1.24 million common prints implies roughly 84 minutes of evaluation, but the existing risk SQL scans can slow with more retained positions. This is an estimate, not a full-31-date load benchmark. The final collection run must still be owned and monitored by root.

## Practical limits

The ≤2GiB target is per sequential worker. SQLite limits its caches and uses file-backed temporary sorts; disk needs still scale with every retained decision and full curve. The existing completion verifier hashes one daily replay using its original whole-file helper, so the ingestion RSS includes one daily file buffer. At the present daily file sizes this is below the target; an unusually enormous single day would merit a separately tested streaming certificate verifier.

Risk checks reuse existing SQL sums and joins; this is a memory-safe implementation, not a claim of constant time per reservation. Its performance must be measured on the final cohort. Full 31-date performance is not inferred from the three-date statistical results. Historical public prints remain upper-bound execution proxies, and this infrastructure does not establish RFQ fill probability or live readiness.

The three-date index uses 492,302,336 physical bytes, of which 292,069,376 are SQLite free pages reusable after per-day staging. Active normalized content is 200,232,960 bytes. Extrapolating active content to 1.24 million prints suggests about 3.4GB plus one-day staging and indexes; output gzip/scratch/collector reserves still require separate budgeting. This is a planning estimate, not a full-scale benchmark.

Root also ran the complete repository suite after the finalized implementation: **531 tests passed in 7.86 seconds**. No implementation source changed afterward. Both replay runs and both parity audits have finished; this task leaves no background replay process.
