# July starting capital versus outstanding deployment

The continuous funded backtests enforce a $10,000 initial bankroll and allow settled profits to finance subsequent trades. They do **not** enforce a separate fixed $10,000 ceiling on outstanding committed cash. This distinction matters for the user's requested committed-cash top and must be resolved before selecting deployment parameters.

An independent integer exposure audit checked all 467,583 decisions in each of three completed July portfolios: Kalshi, Polymarket and equal blend, with $2,000 event limits and $10,000 underlying/combo limits. Every admission reconciled. A separate chronological curve scan verified available cash equals initial capital plus actually settled P&L minus committed cash throughout; no cash balance went negative beyond rounding tolerance. Input artifact hashes were unchanged before/after verification.

| Model | Peak committed cash | Settled P&L at that peak | Available cash at that peak |
|---|---:|---:|---:|
| Kalshi | $10,608.70 | $692.97 | $84.27 |
| Polymarket | $11,247.79 | $1,259.62 | $11.83 |
| Equal blend | $10,662.74 | $673.27 | $10.53 |

These peaks are funded by previously settled gains, not retrospective trade-attributed future outcomes. The finding is a policy mismatch with a fixed deployment ceiling, not evidence of look-ahead funding. Existing results remain valid for their documented reinvestment policy; they must not be labeled hard-$10k deployment portfolios.

Required follow-up: add an explicit, separately configured outstanding-cash limit, with admission bounded by both available settled funds and remaining deployment allowance. Preserve the reinvestment scenario as a comparison. Apply the same policy to research sizing, the backtester and production reservations; test settlement release, outstanding reservations, reduced sizes, losses and profitable reinvestment. Replay candidate funded policies before freezing risk parameters. Do not change source files imported by the active frozen historical jobs.

No risk configuration, execution system, frozen runner or historical artifact changed in this audit. August outcomes remain uninspected.

## Candidate implementation

`src/combos/deployment_risk.py` now provides `DeploymentCappedRiskLedger`, a separate subclass of the existing atomic reservation ledger. It requires `maximum_committed_dollars`, floors that allowance to ledger precision, and limits reservations by both settled cash and remaining deployment headroom. Rejections retain which funding constraints bind. It counts both pending reservations and simulated filled positions, with the existing durable transition lifecycle releasing their exposure. No schema migration is needed.

Eight focused tests pass (`PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_deployment_risk.py`), including settled gains, loss-limited cash, restart persistence, idempotent reservations, filled positions surviving quote expiry, cancellation release, transaction rollback and precision boundaries. The first test invocation without the repository's `src` import path failed collection; the explicit-path invocation passed.

This class is deliberately not wired into active frozen runners. Integration into backtest configuration, runtime reservations and research sizing, followed by replays under the same policy, remains required. Its current lifecycle is inherited from the simulated ledger; these tests do not validate live execution or exchange reconciliation.

## Streaming replay integration (September 9)

The streaming evaluator now accepts an optional `ledger_factory`, defaulting to the unchanged original ledger. A `DeploymentConfig` subclass records the fixed ceiling in candidate portfolio configurations, and `scripts/mlb_deployment_cap_sweep.py` passes the capped ledger explicitly. No global monkeypatch, modification to the base backtest configuration, or production runtime change is involved.

The completed July evaluator and its 16-file imported source closure were preserved and hash-verified in `runs/source_archives/july_streaming_before_deployment_cap_20260908`. The completed snapshot's publication verifier now resolves a changed source against that archive; the full publication verification passed again. Every path pinned by the still-active dated historical batch remains unchanged.

Twenty-six integration/regression tests passed. A causal synthetic replay proves that settled gains can fund a $105 position from a $100 starting bankroll in the old policy, while the new $100 deployment ceiling rejects it. Changing a subsequent outcome does not change that admission. The separate integer auditor in `scripts/deployment_exposure_audit.py` reproduces the decision and rejects a deliberately tampered admission; nine focused tests passed after adding that audit check.

Eight candidate July portfolios are running in `runs/mlb_july_deployment_cap_20260909`: four source models at $1,000 and $2,000 event-risk settings, each with both $10,000 starting capital and a fixed $10,000 committed-cash ceiling. Independent full-data admission audits, comparison with uncapped funding, and production/partial-sizing integration remain pending. No live orders were submitted.

## Completed capped study and shadow integration

All eight portfolios subsequently completed. `scripts/deployment_exposure_audit.py` independently reconciled every admission, settlement release, funding constraint and canonical risk bucket across 467,583 decisions per portfolio. Source/index provenance also passed. The $1,000 scenarios exactly match the original portfolio and selection summaries for every model; the fixed ceiling never binds on those paths.

| Model | $1,000-limit net | $2,000-event net with fixed ceiling | Peak cash at $2,000 |
|---|---:|---:|---:|
| Kalshi | $1,972.04 | $2,170.95 | $9,996.94 |
| Polymarket | $1,864.23 | −$944.02 | $9,999.78 |
| Equal blend | $2,894.47 | −$1,859.08 | $9,993.76 |
| PM75 | $3,515.80 | −$1,333.91 | $9,999.16 |

The ceiling changes which later prints fit and can improve or worsen realized outcomes. It corrects the deployment-policy mismatch; it does not establish an optimal model or risk limit. These remain exchange-only, point-fair development experiments at public-print prices with the historical fee-applicability caveat.

`ShadowEngine` now uses the same capped ledger when `maximum_committed_dollars` is configured. Both NFL shadow configurations explicitly set it to $10,000, with verified before/after backups proving this was their only change. Fifty-seven focused tests passed across the runtime, shadow cap and Pinnacle freshness/normalization suites. The shadow integration test verifies consecutive RFQ reservations, restart persistence and quote-expiry release. Existing runtime manifests require a fresh experiment after code/config changes; no already-running trading service was modified or started.

Partial-sizing integration and a live exchange execution/reconciliation lifecycle remain outstanding. The base historical backtester and the frozen dated collection pipeline remain unchanged.

[Capped admission audit](../runs/mlb_july_deployment_cap_20260909/exposure_verification.json) · [Provenance](../runs/mlb_july_deployment_cap_20260909/provenance_verification.json) · [Shadow configuration verification](../runs/morning_research_20260908/runtime_cap_integration_20260909/verification.json)

[Fixed-ceiling equity curves](../runs/morning_research_20260908/july_deployment_cap_plots_20260909/trade_attributed_equity.png). The new plot preserves every economic change, checks source hashes and endpoint/peak summaries, and was visually inspected. The generalized plotting workflow also emits committed-cash and modeled-edge curves. The preceding uncapped renderer is preserved with its matching hash alongside its v2 outputs.

## Partial-sizing policy consistency

The research partial sizer now reads the optional `maximum_committed_dollars` field, tracks outstanding commitments separately from available cash, and sizes each ticket against both. Fees are recalculated at the reduced quantity; only actual settlement releases the commitment. Each capped sizing decision records the ceiling, prior commitment and remaining headroom. Uncapped calls retain their prior behavior and metadata shape. The previous implementation is preserved with its hash under `runs/source_archives/partial_sizing_before_deployment_cap_20260909`.

Ten tests passed, including an end-to-end partial-sizing replay through the capped streaming ledger and independent integer admission audit. The checks cover reinvestment, blocked additional tickets, settlement reuse, fee repricing and future-outcome invariance. This establishes consistency on the tested scenarios; a full July partial-sizing experiment remains to be run, and executable partial RFQ quantities remain a separate exchange-integration question.

[Verification](../runs/morning_research_20260908/july_cash_ceiling_audit/verification.json) · [Reproduction](../runs/morning_research_20260908/july_cash_ceiling_audit/verify.py)
