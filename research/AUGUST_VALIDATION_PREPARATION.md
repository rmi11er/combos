# August validation preparation

Before evaluating candidate performance, remove validation prints touching any fixture whose outcomes were inspected in development. The existing priced-row purge alone covers 392 July fixtures. Our broader native-universe analysis inspected 428, including 36 absent from the common-priced cohort. Restricting the exclusion set to priced rows would therefore be incomplete.

`runs/mlb_validation_preparation_20260909/development_fixture_exclusions.json` freezes the union of all 428 fixture identities, with hashes of the inspected July native summary and the common-priced index. Its builder reads no validation inputs or outcomes. It checks that the indexed dates belong to the inspected July scope and preserves doubleheader game suffixes. Two focused tests cover broad-only exclusions, doubleheader identity and rejection of non-July inputs.

This manifest is preparation, not proof that a validation replay has applied it. The eventual evaluator must load it before model selection and capital replay, report excluded prints by date, and assert that retained fixtures do not intersect the manifest. All candidates must use the same retained cohort. The current frozen dated-batch scripts have not been modified while collection/pricing runs.

`scripts/heldout_fixture_filter.py` now provides this streaming boundary. Construction requires the frozen manifest hash and validation-date list. It rejects changed manifests, development-date overlap, out-of-date rows, missing/noncanonical fixtures and reuse of the same reader across models. It preserves retained rows without altering economics. A receipt is available only after full stream consumption and reconciles input/excluded/retained counts per date. Zero input does not certify acquisition completeness. Four combined manifest/reader tests pass. Actual held-out evaluation remains pending candidate freeze; the reader has only been exercised on synthetic validation rows.

The candidate specification is frozen below; validation-adapter implementation and verification remain pending before inspecting August performance. Refresh the exclusion manifest if further development outcomes are inspected. Known exceptional-date/fixture aliases require explicit semantic handling; this manifest does not invent fuzzy identity equivalences.

## Candidate specification frozen

`config/mlb_august_candidates_20260909.json` and `runs/mlb_validation_preparation_20260909/candidate_freeze.json` now freeze the exact candidate specification and its hash before root inspection of August outcomes. The primary is equal exchange blend, point reference, 0.3c/combo, $1k underlying/combo/event, with $10k initial capital and fixed outstanding ceiling. PM75 point and PM-only quarter marginal reserve are two named challengers. The 11 other specifications are benchmarks or diagnostic sensitivity settings, not additional primary hypotheses.

The equal blend is selected for balanced source exposure and its development path, not because it maximizes July P&L. It had lower retrospective drawdown than PM75 and retained positive P&L under date/fixture omissions. This is still development-driven selection and requires validation. PM75 tests the PM preference; the PM-quarter challenger changes both source and reserve relative to primary, so source/reserve attribution must use the separate PM-point and equal-quarter controls.

Edge controls use 0, 0.1 and 0.5c/combo and 0.3c/leg. Risk controls use joint $500 and $2,000 bucket caps plus the original $100/$100/$250 caps; these jointly changed caps cannot isolate the event-cap effect alone. The earlier isolated-event sweeps remain separate evidence. All 14 specifications run funded/unlimited, with identical unlimited risk settings explicitly treated as duplicate controls. Sell-all refers to the common retained priced cohort.

The frozen specification requires a continuous funded replay over all 15 August dates, no daily reset, exact fixture exclusions and reporting of the primary even if a challenger wins. Newly tuned winners need a new validation window. Existing evaluator source hashes are captured; the remaining validation adapter must be sealed and verified against this specification before outcome evaluation. No historical three-source claim, fee certification, quote acceptance or automatic live promotion follows from this freeze.

## Validation runner sealed

`scripts/run_frozen_august_validation.py` now implements the frozen specification. Its 23-file project source closure is archived under `runs/mlb_validation_preparation_20260909/implementation_v1/sources`; `seal.json` pins those hashes and the specification. The runner requires matching source/specification/exclusion hashes before discovery, complete dated certificates, paired input coverage, causal context reconstruction and identical purge receipts across all 28 policy/regime replays. All original specification-time source hashes still match.

Seven focused tests pass. The integration test runs all 28 candidate evaluations and real risk ledgers on a synthetic cohort, proving that the excluded trade cannot enter any portfolio and that the retained trade's P&L reconciles. Acquisition/index construction and feature storage are synthetic in that integration test; separate tests exercise actual feature reconstruction and future-observation rejection. These tests do not certify real August input coverage or future output admissions.

At sealing, six August dates were certified complete; nine remained in the live batch. No actual validation replay was launched. The runner refuses a completed prefix. After all dates are available:

```sh
PYTHONPATH=src:scripts .venv/bin/python -u scripts/run_frozen_august_validation.py \
  --spec config/mlb_august_candidates_20260909.json \
  --freeze runs/mlb_validation_preparation_20260909/candidate_freeze.json \
  --parent-plan config/mlb_validation_20260907_expanded.json \
  --implementation-seal runs/mlb_validation_preparation_20260909/implementation_v1/seal.json \
  --batch-root runs/mlb_historical_20260907/dated_fee_primary \
  --out runs/mlb_august_frozen_validation_20260909
```

The eventual completion receipt explicitly leaves independent admission/policy audit pending. Do not interpret successful execution alone as fully verified held-out results.

## Independent output audit ready

`scripts/audit_frozen_august_validation.py` separately reconstructs the frozen exclusion set, checks retained input rows against every decision, verifies point/fractional-reserve pricing and combo/per-leg thresholds, and runs the independent integer admission audit on all funded paths. It reconciles fill identity, time, size, price, fees, outcome and native seller P&L to accepted decisions, verifies the exact 28-policy/regime census and reconciles date-level purge counts. Input, artifact and audit-source hashes are retained.

Seven tests pass, including an independent audit of all 28 synthetic integration outputs and deliberate corruption of fees, reserve and hurdle fields. This is readiness of the auditor; real August output verification remains pending. Run after the actual replay completes:

```sh
PYTHONPATH=src:scripts .venv/bin/python -u scripts/audit_frozen_august_validation.py \
  --study runs/mlb_august_frozen_validation_20260909 \
  --spec config/mlb_august_candidates_20260909.json \
  --freeze runs/mlb_validation_preparation_20260909/candidate_freeze.json \
  --out runs/mlb_august_frozen_validation_20260909/independent_verification.json
```

## Automatic replay/audit continuation

`scripts/supervise_frozen_validation.py` is running from `runs/mlb_validation_preparation_20260909/supervisor_plan.json`, with authoritative state/logs under the sibling `supervisor/` directory. Do not manually launch the reproduction commands while it owns `dated_fee_primary/frozen_validation_supervisor.lock`.

The supervisor waits for all 15 dated completion statuses and at least 8 GiB free, then executes the sealed runner followed by the independent audit. The runner still verifies actual completion certificates and paired coverage; the supervisor's status check alone is not certification. Code/specification/manifest fingerprints are pinned. Three focused tests cover pending dates, sequential stage execution and failure preserving prior outputs while preventing the next stage. Failed stages are not automatically retried or overwritten.

Live collection and recovery identities are checked while waiting. If both terminate with missing dates, the supervisor records a stopped state rather than claiming completion. Full-study completion still requires reviewing the real audited results and outstanding diagnostic plots/cuts; this supervisor does not promote parameters or initiate live orders.

Reproduce with `scripts/build_development_fixture_exclusions.py --native-summary runs/morning_research_20260908/july_full_universe/report/summary.json --development-index runs/mlb_july_development_snapshot_20260908/input.sqlite --out <new-manifest-path>`.
