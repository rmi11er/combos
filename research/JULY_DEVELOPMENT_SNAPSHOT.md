# July development snapshot preparation

The full original July/August study remains in scope. Before examining August outcomes, build a separate certified July development projection and run the continuous 48-policy evaluator once. Daily funded profits must not be added to substitute for this replay.

`scripts/prepare_development_snapshot.py` selects only dates marked development in the original plan. It refuses to publish while any development date lacks a terminal certificate. It verifies completed replay hashes through the existing discovery code, links only development day directories, retains the original selected stage certificates and publishes a filtered plan plus source provenance. July 13 remains an explicit `collected_unpriced_identity` gap; it is not relabeled as an empty or zero-profit day. The other 15 scheduled July dates must be priced or explicitly certified empty before publication.

```sh
.venv/bin/python scripts/prepare_development_snapshot.py \
  --plan config/mlb_validation_20260907_expanded.json \
  --batch-root runs/mlb_historical_20260907/dated_fee_primary \
  --out runs/mlb_july_development_inputs_20260908
```

Two focused tests pass for exclusion of held-out dates/stages, preservation of the unpriced gap and refusal to publish with running/missing dates. The first actual invocation correctly reported July 31 pending and created no projection. July 31 subsequently completed exchange acquisition on its second attempt and is running model replay; the batch's existing retry path handled this without another collector launch.

Once ready, inspect available disk space and the measured output estimate before starting `run_mlb_streaming_snapshot.py` with the projected batch root, its `development_plan.json`, a new output directory and `--artifact-codec zstd`. The wrapper pins code/plan and publishes completion only after all 48 policies. It also produces plots; follow the visualization workflow before running. Do not append later dates to an existing funded ledger or rerun every growing prefix.

The retained three-date reference uses 585,220,276 bytes of row artifacts and 492,302,336 bytes of input SQLite for 72,561 common prints. This provides a measured scaling reference, not an upper bound: input composition, selected trades, temporary scratch and concurrent collectors change storage demand. Current free space is approximately 13 GiB; the final all-31-date snapshot and remaining acquisitions still require a separate capacity check.

Review the complete July source comparison, fee-aware margin grid, leg counts, spread/calibration diagnostics, fixture influence and continuous funded utilization before freezing a primary model and limited challengers. New reserve assumptions and sizing rules remain exploratory until evaluated on the same July cohort. Freeze parameters and evaluation rules before reading August outcomes; retain January NFL as inspected development evidence, not fresh validation.
