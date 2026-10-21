# CFB retrospective walk-forward validation

The reusable validation and markout tools are implemented and have been run on the frozen CFB week. This is **retrospective walk-forward analysis of a week whose outcomes and charts were already examined**, not an untouched holdout. No model or threshold is promoted by this exercise. The fixed calibration candidate has too little eligible prior training data to operate before the dominant Saturday slate; its one usable Sunday fold does not improve the blend's common-cohort Brier score or selected-trade hypothetical profit.

Reproduce from the repository root:

```sh
.venv/bin/python -m pytest -q tests/test_research_validation.py tests/test_pinnacle_history.py
.venv/bin/python scripts/cfb_walk_forward_validation.py
```

Ten focused tests pass. The script performs no HTTP requests or trading actions. It leaves the pricing service, production configuration, and capital-allocation backtester unchanged. Results and input/code hashes are in `runs/cfb_selection_research_20260907/validation/`.

## Scope and evaluation rules

The cohort contains 8,295 public prints with all four existing benchmark forecasts, 2–4 distinct full-game fixtures, and customer YES premium at most $50 per print. This fixed cap follows the current matched-size research comparison; it is a cohort definition, not a newly imposed live ticket cap. It is configurable through `--maximum-yes-premium`. There are 4,892 unique economic combo payoffs across 91 fixture identities. Of these prints, 8,084 have a supplied known settlement, including settlements after the observation window. The other 211 are excluded from outcome scores, retained in forecast/exposure counts, and never treated as zero outcomes.

Of 61,205 original public prints, 51,694 lack the common four-model intersection and another 1,216 exceed the research premium cap. Results therefore do not estimate all-market opportunity. The same economic prints are used for every model's **all-candidate** comparison. Selected subsets differ between models and cannot be compared as though their event and risk composition were identical.

There are seven daily folds, August 31–September 6, 2026, using America/Chicago day boundaries. For each fold:

1. Training decisions must precede midnight at the start of the test day.
2. Their outcome availability timestamp must be **strictly earlier** than that fit time. A known eventual result is insufficient.
3. Every training combo containing any fixture present in the test fold is removed in its entirety. Removing only the overlapping leg would leak event information.
4. Test forecasts use the existing frozen source probabilities, with no outcomes supplied to the fitter. Outcome scores can use later supplied settlements, but those labels do not travel backward into fitting.

Test fixture membership is used only as an offline exclusion boundary. A deployable equivalent needs to declare its exclusion universe at fit time, such as all fixtures in the coming evaluation block; it cannot rely on knowing which RFQs will subsequently appear.

Forecast availability is inherited from the previously audited replay decision time, assuming zero computation/response latency. This experiment adds label-time and fixture-purge hygiene; it does not independently establish historical feed health or execution latency.

The input replay obtains `settled_at` from the native combo market's `settlement_ts`; this serves as the historical label-availability proxy. The experiment enforces the strict cutoff on that timestamp. It does not possess an archived local receipt time proving when our process actually learned the result. Forward validation should use recorded label receipt time, including any settlement revisions, in the same API.

## Fixed calibration candidate and actual training coverage

`src/combos/research_validation.py` provides immutable forecast records, chronological folds, whole-fixture purging, calibration fitting, exposure metrics, and causal markout primitives. The calibration is a deliberately simple, falsifiable additive correction:

- Average `(outcome − forecast)` within each economic payoff first, preventing repeated identical prints from receiving proportional influence.
- Average those payoff residuals within each constituent fixture, then average equally across fixture identities.
- Shrink this fixture-balanced residual by `n_fixtures / (n_fixtures + 50)` and limit the absolute adjustment to 0.03 probability, or 3 cents per contract.
- Require at least 20 training fixture identities, 100 unique training payoffs, and 3 training **decision dates**. Otherwise return the original probability and record each failed requirement.

These are fixed candidate rules, not parameters optimized against this week's results. Fixture balancing reduces repeated-print influence; it does not make overlapping combo observations statistically independent or replace an event-outcome model. Decision-date diversity also does not establish diversity of settlement slates.

The training counts are identical across the four models because they use the common cohort:

| Test day | Eligible training prints | Training payoffs | Training fixtures | Decision dates | Test prints | Result |
|---|---:|---:|---:|---:|---:|---|
| Aug 31 | 0 | 0 | 0 | 0 | 2 | Identity fallback |
| Sep 1 | 0 | 0 | 0 | 0 | 0 | Identity fallback |
| Sep 2 | 0 | 0 | 0 | 0 | 3 | Identity fallback |
| Sep 3 | 0 | 0 | 0 | 0 | 9 | Identity fallback |
| Sep 4 | 2 | 2 | 2 | 1 | 93 | Identity fallback |
| Sep 5 | 77 | 55 | 9 | 2 | 8,031 | Identity fallback |
| Sep 6 | 5,920 | 3,739 | 85 | 5 | 157 | Candidate fitted |

Twenty-four of 28 model/fold fits use the explicit identity fallback. Before Saturday, nine otherwise labeled training prints are purged for fixture overlap; before Sunday, 192 are purged. Saturday represents 96.8% of the evaluated prints. Sunday has only six test fixtures, and one fixture occurs in combos accounting for 96.6% of that day's gross maximum-loss sum. The Sunday fold is consequently a very concentrated test, despite thousands of training prints.

Sunday's additive adjustments are −0.689 cents for Kalshi, −0.419 cents for Pinnacle, −0.601 cents for the blend, and −0.541 cents for the stronger-Pinnacle blend. They are derived from earlier eligible labels, not the Sunday results.

## Outcome and exposure results

For a hypothetical maker selling combo YES at the observed public price `c`, quantity `q`, combo probability `p`, and supplied maker fee `f`:

```text
expected net edge = q × (c − p) − f
settled hypothetical profit = q × (c − outcome) − f
point-entry selection = quote_allowed AND expected net edge >= 0.003 × q
gross maximum loss per print = q × (1 − c) + f
```

The 0.003 threshold is a minimum net edge of 0.3 cents per contract at **somebody else's observed transaction price**. It is not a simulated fill at our generated quote. This report evaluates point selection, without the old stressed dependence envelope. The gross maximum-loss sum is an exposure diagnostic across prints, not required simultaneous capital or a funded equity curve. There is no inference of executable fills, portfolio returns, or Sharpe from these sums.

Across all 8,295 common capped prints, payout notional is $1,248,223.49, customer YES premium is $111,785.22, and the gross maximum-loss sum is $1,139,256.96. All models have the same −$10,117.29 known-outcome hypothetical profit when **every** print is taken, because model probabilities cannot change the realized result of a fixed set of trades.

Common-candidate outcome Brier scores are comparable because their observations match:

| Model | Static unweighted Brier | Static quantity-weighted Brier | Calibrated unweighted Brier |
|---|---:|---:|---:|
| Kalshi | 0.155258 | 0.057744 | 0.155308 |
| Pinnacle | 0.156990 | 0.058089 | 0.157022 |
| Blend | 0.155792 | 0.057849 | 0.155835 |
| Stronger Pinnacle | 0.156213 | 0.057932 | 0.156253 |

The small differences are descriptive, not statistical evidence that one venue is consistently sharper. Repeated payoffs, shared fixtures, one dominant slate, and an already-inspected week prevent that conclusion.

Static point-entry results, shown with quantity and fixture concentration in the machine-readable outputs:

| Model | Selected prints / known outcomes | Expected edge, all selected | Known-outcome hypothetical profit | Quantity-weighted outcome minus forecast |
|---|---:|---:|---:|---:|
| Kalshi | 706 / 686 | $144.50 | −$2,802.82 | +9.50 pp |
| Pinnacle | 3,296 / 3,160 | $1,581.50 | −$14,202.16 | +9.22 pp |
| Blend | 1,601 / 1,512 | $434.14 | −$7,143.97 | +10.30 pp |
| Stronger Pinnacle | 2,308 / 2,192 | $750.40 | −$9,779.65 | +9.65 pp |

For the static blend, all-candidate quantity-weighted outcome-minus-forecast is +0.77 percentage points, versus +10.30 points on selected observations. The blend-selected gross maximum-loss sum is $56,529.58; the largest fixture accounts for 33.0% of that sum. This conditional residual merits investigation, but selecting on price relative to model probability changes the price, outcome probability, size, and fixture mix. It is not proof of an arithmetic bug, execution toxicity, or one stale source. The previously profitable unrestricted all-trade population is not an appropriate control for these capped observations.

The calibrated blend selects 1,666 prints and records −$7,171.97 known-outcome hypothetical profit. On Sunday's actual test fold, its common-candidate Brier rises from 0.141413 to 0.143878, and selected profit changes from −$277.83 to −$305.82. Quantity-weighted Brier on the **selected subset** falls, but that subset changes from 45 to 110 prints; this is not a matched-sample calibration improvement. A global residual correction does not solve the conditional-selection problem in this small retrospective test.

## Historical markout feasibility

`PricePoint`, `CausalPriceSeries.asof`, and `score_markout` are reusable independently of the CFB script. The as-of series uses availability timestamps, fails closed on a latest inactive state, rejects conflicting simultaneous states, and prevents a late arrival carrying an older source timestamp from replacing newer information. Markouts require:

- Entry information available no later than the decision.
- Target information available no later than decision plus the requested horizon.
- A genuinely post-decision source update, newer than the entry composite source state.
- Both entry and target still pregame, at least 60 seconds before the earliest constituent kickoff.

The script uses the existing causal archive adapters: Kalshi minute candles with their additional 60-second publication allowance, and Pinnacle history with its additional 30-second archive delay. These allowances are modeling assumptions, not observed live delivery timestamps. A joint mark is the product of the selected-side probabilities. At least one component must have qualifying new information; other components can remain carried active prices. The composite source time records the latest constituent update, so the scorer is conservative about recognizing asynchronous component updates.

| Venue / decision-clock horizon | Scored / 8,295 attempted | Actual post-decision source horizon among scored |
|---|---:|---|
| Kalshi / 60 seconds | 0 | No qualifying source information under the publication allowance |
| Kalshi / 300 seconds | 7,759 | 1.44–239.44 seconds |
| Pinnacle / 60 seconds | 400 | 0.04–29.98 seconds |
| Pinnacle / 300 seconds | 1,804 | 0.05–269.90 seconds |

For example, a 60-second Pinnacle decision-clock mark cannot contain source information later than about 30 seconds after entry under the archive delay. It should not be described as observing the true undelayed price at entry plus 60 seconds.

Among the static blend-selected prints with scorable targets, aggregate maker-NO mark changes are −$2.28 at the five-minute Kalshi mark (1,501 prints), −$0.52 at the one-minute Pinnacle mark (81 prints), and −$4.65 at the five-minute Pinnacle mark (350 prints). The quantity-weighted probability changes are respectively +0.00318, +0.01146, and +0.02507 cents per contract. These near-term venue marks do not reproduce the much larger eventual settlement residuals. They also do not establish that the original fair was correct: target coverage is conditional on observed updates, shared fixtures remain highly dependent, and both sides of a markout use the same imperfect venue benchmark.

Missing, unchanged archive states and inactive targets are exclusions, not zero returns. In particular, Pinnacle has no qualifying new future information for 7,490 one-minute attempts and 5,807 five-minute attempts. A lack of archived changes does not distinguish quiet prices from unobserved upstream news or feed health, and cannot test or refute a delayed-anchor innovation model. No actual historical PM bid/ask spread or top-of-book depth is present, so these archives cannot validate a real-time three-source depth-aware 30-second innovation correction. PM historical price-point semantics must not be upgraded to an observed bid/ask midpoint or an independent spread measurement.

## What a genuine next validation block needs

Freeze the candidate model, source-availability rules, selection threshold, risk limits, and intended fixture exclusion universe before observing the next NFL/MLB outcome block. Collect all eligible RFQs and rejection contexts, source bid/ask/depth, native and local receipt timestamps, inactive messages, and repeated source health evidence. Retain unselected opportunities as controls. Do not select a different model after reviewing that block and continue calling the same block held out.

Use a separate warm-up set with enough completed fixture slates for fitting. Then evaluate a future block with complete fixture purging; reserve subsequent blocks for replication. Report common-candidate calibration, selected/rejected matched exposure strata, fixture concentration, and source markout coverage alongside the existing funded backtest. RFQ responses, acceptances, and fills are needed to evaluate our own quote-placement policy; public-print counterfactuals cannot supply those labels.

The current infrastructure enforces causal bookkeeping and exposes when there is insufficient training or markout coverage. It does not provide sufficient held-out evidence to authorize a live model on its own.

## Output inventory

- `summary.json`: cohort, fixed policy, markout coverage and source horizons, limitations, input/code hashes.
- `fold_fits.json`: label availability, purge counts, training sizes, adjustments and explicit fallback reasons.
- `fold_metrics.json`: per-fold all/selected scores for static and causally fitted candidates.
- `aggregate_metrics.json`: quantity-weighted and unweighted scores, economics and fixture exposure summaries.
- `predictions.jsonl.gz`: fold-specific frozen predictions and training adjustments.
- `markouts.jsonl.gz`: entry/target timing, venue, future probability changes, and entry-time selection flags.
