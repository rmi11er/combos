# Pooled MLB spread calibration

This workflow pools quantity-weighted sufficient statistics, not daily coefficients or daily mean ratios. At most one dated replay/features join is held in memory; fixture-group moment matrices persist across dates. Cross-date print-ID checks use a temporary SQLite table. No full 31-date trade frame is constructed.

```sh
.venv/bin/python scripts/mlb_pooled_spread_calibration.py \
  --batch-root runs/mlb_historical_20260907/dated_fee_primary \
  --feature-root runs/morning_research_20260908/spread_v2 \
  --plan config/mlb_validation_20260907_expanded.json \
  --out runs/morning_research_20260908/pooled_spread \
  --once
```

Repeat `--batch-root` for separately certified collections. Default output separates development and validation; `--include-pooled` adds a clearly descriptive pooled fold after validation fixture purge. Optional `--date YYYY-MM-DD` restricts a smoke test while preserving the full plan's missing-date accounting. The command exits after one run and launches no watcher.

Every complete batch-day replay must match its completed-stage hash certificate. Feature manifests must attest completion and match their feature hash. The generic row loader validates feature timestamps, duplicate identities and identical cross-model prices, quantities, fees, outcomes and risk identities. The intersection requires every fixed primary model in the plan; a missing model is unavailable, never silently dropped.

Both raw and fee-expanded sums of opposite-team moneyline spreads are analyzed. Each specification uses identical known-outcome prints for compensation, residual and realized P&L. `spread_only` has an intercept and width; `price_and_leg_count` additionally has traded price per 10c and categorical 2/3/4-leg effects. The component coefficients sum to realized P&L coefficients.

For each model/measure/fold, accumulate `X'WX`, `X'WY`, weighted outcome sums and squared sums, total weight, squared weight and print count. Removing a fixture subtracts its moments, where each print contributes once to each unique fixture it contains. The resulting slope ranges describe overlapping-group influence, not confidence intervals. No IID standard errors or p-values are reported. Rank-deficient or ill-conditioned normalized moment systems are explicitly unavailable; the workflow never adds a ridge term to manufacture coefficients.

Bins accumulate quantity × component directly, then divide by pooled known quantity. Unknown outcomes remain in coverage and all-priced compensation, but are excluded equally from the three realized decomposition components.

Validation prints touching any fixture in a certified development replay are purged, including development fixtures lacking spread features. The purge remains provisional until all planned development dates are certified. A completed development replay without features can strengthen the purge while its regression date remains missing. This prevents feature availability from weakening fixture separation. No calendar gaps are assigned zero returns.

Output includes `results.json` with coverage, provenance, coefficient tables, R², fixture-deletion failure reasons and bin sums; `REPORT.md`; and per-fold raw/fee PNG/SVG plots. Results inherit unverified historical fee scenarios, moneyline-only feature coverage, and public-print execution limitations. Nothing promotes a model, changes edge charges or sends orders.

The July 1 smoke is saved in `runs/morning_research_20260908/pooled_spread_july1_verified`. Across 25,318 common prints, all four models, both widths and both specifications match the existing row-level workflow: maximum absolute coefficient difference 6.16e-11, fixture-deletion slope difference 1.98e-11, bin-cent difference 6.84e-14, and R² difference 9.11e-14. `numeric_parity.json` records these checks and both input hashes. Eight targeted tests pass. The raw PNG was visually inspected. The run reports 30 missing plan dates and a provisional validation purge, rather than presenting this smoke as completed historical validation.
