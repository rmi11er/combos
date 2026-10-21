# NFL demand experiment: implementation and dry run

## Decision and scope

Keep flat 0.3 cents as the benchmark. Test flat 0.2 and 0.5 cents; do not fit or deploy a price curve from the January retrospective results. These are per-contract net hurdle settings after candidate maker fees and the same reserves, not promised realized profits. The question is whether changing the quote improves customer acceptance and net execution economics. Historical prints at other makers' prices cannot answer it.

Implemented offline assignment, candidate construction, response scoring, and conditional execution markouts. **No live experiment has started, no orders are enabled, and no demand effect has been measured.** The retained account quote probe has zero returned quotes; simulated fill logs are not acceptance evidence. This is not a claim that the account has never quoted.

## Dry-run result

Source: retained September NFL RFQ scenarios, not January historical prints. Of 47,937 observed RFQs, 694 have priced scenarios. Only 77 have fixed requested quantities. All 77 pass this dry-run eligibility and produce three distinct native-grid candidate asks. The remaining 617 priced RFQs specify spend and are excluded pending verified candidate-dependent sizing including fee treatment. Fixed-size coverage is therefore 11.1% of priceable RFQs; it cannot represent spend-sized demand.

The source conversion, independent-leg fair, sampled grids, balance precision, and uncalibrated non-uncertainty reserves remain research assumptions. The uncertainty reserve is held constant across arms. Maker fees come from captured terms rather than a universal January coefficient. This checks plumbing, not production quote safety.

Reproduce:

```sh
.venv/bin/python scripts/nfl_demand_experiment.py prepare --out runs/nfl_demand_experiment_20260909
```

Artifacts: `assignments.json` contains all candidate ledgers and deterministic assignments; `summary.json` contains input hashes, seed, exclusions and arm/price-band counts. Zero observed exposures yields null acceptance rates, not zero rates. Retrospective assignments cannot be scored as customer exposures.

## Prospective protocol to freeze before exposure

1. Use one immutable seed and assign each eligible RFQ once, with equal probability to the three flat hurdles. Reprocessing the same RFQ preserves its arm. Require all three candidates to pass common pre-assignment checks and have distinct prices. Do not rerandomize after a rejection. Repeated creator behavior and shared games must be recorded for dependence analysis.
2. Use identical fair inputs, reserve models, fee terms, quote TTL, side, sizing rule, latency path and risk checks. Freeze all candidate payloads, assignment timestamp, response-window endpoint, creator identifier, fixture identifiers, source ages and risk eligibility before dispatch. Initially restrict to verified fixed-size requests. Candidate-specific post-assignment skips must stay in the assigned denominator with reasons.
3. Quote only the assigned arm. A prospective record must have `experiment_stage=prospective_frozen`, `assignment_frozen_at`, `decision_at`, `response_end_at`, and the candidate payloads. The execution integration must persist this record before sending. Merely changing a retrospective stage label is not valid prospective provenance.
4. Record actual quote ID and customer visibility evidence separately from transport acknowledgment. Capture acceptance, cancellation, expiry, fills and actual allocated fees. No response record means not exposed/unknown, never rejection. Incomplete observation or early withdrawal without acceptance is censored. Negative labels require continuous observation and exposure for the full frozen window. Acceptance requires its own evidence reference and is not itself execution.
5. Obtain independent as-of fair observations at 10, 30, 60 and 300 seconds after each execution. Freeze fair methodology; require source availability by the horizon and maximum two-second staleness. Do not fill missing horizons with zero or extrapolated prices. Report gaps.

The current code provides assignment and scoring, **not a live journal/transport integration**. A verified adapter, source/market validation, candidate-dependent risk checks, approved exposure limits and fixed experiment duration are prerequisites for live operation. Do not enable an order sender to obtain these results implicitly.

## Daily readout and decision rule

Report assigned RFQs, exposed RFQs, transport/risk skips, accepted RFQs, censored responses, executed RFQs, contracts and dollars by arm. Primary price bands use pre-treatment fair: below 10c, 10–25c, 25–40c and 40c+. Secondary diagnostics should separate leg count, leg-book width, size, creator and game slate; retain fixture overlap rather than treating every print as independent.

The scorer returns acceptance among resolved responses plus worst/best censor bounds among exposed RFQs. These are descriptive, not a completed causal analysis; exposure-only comparisons can be selected by risk or transport. Analyze assignment-level outcomes as well once dispatch reasons are captured.

Conditional seller markout in dollars is `quantity * (execution YES price - horizon fair) - actual allocated maker fee`. Positive favors the seller. Show contract-weighted cents per contract and quantity coverage at every horizon. Each horizon is a separate valuation, not additive PnL. Acceptance, execution probability, conditional markout and total economics per eligible assigned RFQ must remain separate. A high acceptance rate with adverse selection is not success.

Use creator/game-cluster-aware uncertainty and a fixed evaluation endpoint; the 77 retrospective RFQs are not a power calculation. Estimate baseline acceptance and clustering from a prospective pilot before fixing the confirmatory sample requirement. Do not repeatedly test daily until significance. A curve merits a subsequent experiment only if a price-by-treatment interaction is economically meaningful, stable across slates and supported by adequate coverage; an aggregate preference for one flat hurdle does not establish that interaction.

## Scoring interface

```sh
.venv/bin/python scripts/nfl_demand_experiment.py score \
  --assignments PATH_TO_FROZEN_PROSPECTIVE_ASSIGNMENTS.json \
  --responses PATH_TO_VERIFIED_RESPONSES.json \
  --fills PATH_TO_VERIFIED_FILLS_AND_MARKS.json \
  --out runs/nfl_demand_experiment_live/scored.json
```

`tests/test_demand_experiment.py` supplies minimal schema examples. Responses require assignment/arm, exact exposed quantity and ask, quote identity, source and exposure evidence, dispatch/ack/window/observation timestamps, and explicit full-window flags. Positive responses also require acceptance time and evidence. Optional fill records require actual fill identity, matching accepted quote, quantity, YES execution price, allocated maker fee, execution time and provenance. Marks contain horizon seconds, fair, observed and available timestamps, and provenance.

Do not populate those files with simulated labels. The next dependency is real prospective customer exposures with verified provenance, not another regression on completed trades.
