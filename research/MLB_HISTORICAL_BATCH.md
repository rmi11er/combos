# Durable MLB historical research batch

`scripts/mlb_historical_batch.py` waits for complete acquired calendar days and runs the existing research adapters sequentially. It does not collect the public tape itself, issue orders, query Pinnacle, or change trading limits. Its outputs are hypothetical printed-price experiments under explicit dated fee assumptions. The initial five dates are pipeline screening; risk limits require the larger dataset and independent validation.

For the expanded frozen date plan and per-date fee files, preview the exact commands with:

```sh
.venv/bin/python scripts/mlb_historical_batch.py \
  --plan config/mlb_validation_20260907_expanded.json \
  --fee-scenario-dir runs/mlb_historical_20260907/fee_scenarios \
  --out runs/mlb_historical_20260907/dated_fee_primary
```

After code review and the collaborators' edits are complete, add `--execute --wait-timeout-seconds 172800` to run. `--dates` can restrict execution to a subset of dates already in the frozen study plan. A single policy file explicitly covering all requested dates can instead be supplied with `--fee-scenario`. The existing September 5 input is a separately identified descriptive reference, not a newly collected validation day.

Each date runs:

1. Full-day page/hash/cursor verification, cached native combo and underlying metadata recovery, and cohort export. All native metadata must be recovered; a budget stop is an incomplete stage.
2. Exact ordinary-game exchange mapping and Kalshi/Polymarket historical acquisition. Every planned history job must finish with HTTP 200 before replay; empty returned history remains explicit coverage failure downstream.
3. Causal historical fair replay using that day's fee scenario.
4. Common-cohort model reports and the fixed entry-threshold sweep, both funded and unrestricted.
5. A versioned cumulative validation report on ready daily inputs plus the descriptive reference.

A complete day with no eligible 2–4-leg, distinct-fixture, pregame YES-taker prints is marked `complete_empty_eligible_scope`, preserving its cohort evidence and skipping exchange requests. It is not promoted into a priced zero-fill result. Incomplete tape or missing pricing is never silently substituted with a smaller sample. Currently the cumulative report displays such absent priced dates as missing inputs; the batch status retains their more specific empty-scope classification.

The expanded collector is supervised separately so only one tape collector controls that cache. The batch can wait alongside it and process whichever dates become complete first. It polls in 20-second intervals, writes a durable heartbeat and has explicit acquisition-wait and per-stage timeouts. Metadata attempts are capped at 10,000 public GETs per stage invocation by default. This is a bound, not a consumption forecast; native recovery and exchange acquisition cache successful requests. There are no paid odds calls.

`batch_manifest.json` freezes the explicit 12-script MLB dependency closure, source-package modules, study, fee and reference-input hashes and saves code/policy copies. Unrelated NFL scripts are outside this scope. Changing a frozen file stops execution; use a new reviewed output run for a changed model or scenario. `batch_status.json` records each day's state, every stage's argv, attempts, child PID/heartbeat, exit code and output hashes. Logs are retained under `logs/`. A filesystem lock prevents two batch processes from writing the same output root. Restarting with the same command verifies completed artifacts and skips successful stages.

Transient HTTP 429/5xx and transport failures permit at most two stage attempts, with the count persisted across restarts. Data-integrity, mapping, fee, entitlement and incomplete-metadata/budget failures stop immediately for review. Budgets do not increase automatically. Existing HTTP adapters retain their own bounded request retries. A process interruption terminates the active child and leaves resumable caches and state.

Validation:

```sh
.venv/bin/python -m pytest tests/test_mlb_historical_batch.py -q
```

Twelve tests cover completeness, overlaps and missing pages, the pregame buffer, durable success and modified outputs, missing success artifacts, bounded persistent retries, immediate metadata failures, source mutation, failed exchange jobs and command scope. A regression confirms unrelated NFL script edits do not invalidate the frozen MLB pipeline. The expanded-plan dry run validated all configured dates and dated fee coverage. Launch remains an explicit separate action after review; no batch was started by the implementation task.
