# Strategy proof: development experiments and held-out decisions

This is an explicit expansion of the research agenda requested September 8. It supplements, and does not rewrite, the frozen 31-date collection plan. July observations have already influenced these hypotheses: they are development choices, not retroactive preregistration. August outcome summaries remain reserved for the candidate freeze. No item below is established merely because it has a proposed test.

## Order and common evidence

Complete the native universe and common priced-cohort audit first. Develop on all 16 July dates, using chronological July folds with shared fixtures purged for candidate comparisons. Freeze a small set of candidates, including pricing, sizing, feature transforms and risk settings, before inspecting 15 August dates. Evaluate the primary candidate first. Disclose every tried variant, unsuccessful results and secondary August grid comparisons. A change inspired by August requires new future validation.

Use paired prints to compare models, and separately report each model's standalone coverage: a common intersection can preferentially retain easier/liquid markets. Preserve unsupported identities and missing prices as coverage gaps, never zero-fill model performance. Keep MLB and NFL results separate; the January NFL study is an inspected diagnostic, not an untouched confirmation set.

The main unit of economic reporting is a sold YES contract. With quantity q, observed price p, model fair f, final payoff y and total maker fee F:

`net P&L = q(p - f) - F + q(f - y)`.

Report compensation, settlement residual and their sum. Trade-attributed eventual P&L can use y for evaluation; signals, admission, limits and spendable cash cannot see y before it becomes available. Cash releases at actual settlement. Report daily/account variance, drawdown, capital-hours, maximum fixture exposure and independent-date/fixture concentration. Do not treat overlapping prints as IID. Retain the existing minimum-data rule for Sharpe; if it cannot be estimated credibly, report N/A and the observed P&L distribution rather than inventing an annualized ratio.

## Experiment matrix

| ID | Question and development comparison | Required evidence and decision |
|---|---|---|
| S1 | Does PM improve fair value relative to Kalshi? Compare K, PM, equal blend and PM75 on paired observations, signed disagreement and probability bands. | Leg and combo Brier/log loss where labels are valid, reliability plots, compensation/residual decomposition, common vs standalone coverage, fixture-deletion and chronological-fold stability. A profitable PM-only subset alone is insufficient. |
| S2 | Does Pinnacle add information beyond both exchanges? Compare K, PM, Pin, K+PM, K+Pin, PM+Pin and all three; isolate Pin+PM agreement against K. | Requires verified causal historical Pin prices and mapping. Show incremental calibration and selection performance over K+PM at equal coverage, with explicit 30s availability and polling delay. Current MLB data cannot answer this; status is unavailable, not a negative finding. Use a separately frozen forward experiment if historical coverage cannot be obtained. |
| S3 | When should consensus outweigh K? Condition on signed disagreement, whether Pin/PM agree, spread, price band and time to start. | Prespecify disagreement in probability cents and evaluate both directions. Compare fixed weights with a bounded confidence adjustment. Estimate on July only; use July fold predictions rather than fitted-in-place predictions for comparisons. PM sharpness and K inventory distortion are hypotheses, not assumed causal explanations. |
| Q1 | What minimum compensation is useful? Keep sell-all and existing 0/0.1/0.3/0.5 cents per combo and 0.3 cents per leg. | Continuous constrained/unconstrained P&L, modeled compensation, coverage, admission volume and capital-hours; show sensitivity surfaces rather than only the best setting. Public prints test admission at an observed price, not the fill rate obtainable by changing our quote. |
| Q2 | Can a selective surcharge beat a flat hurdle? Add one signal at a time: propagated leg spread, source disagreement, stale-source divergence, time to start, and inventory concentration. | Start with low-dimensional bounded rules. Estimate incremental calibration/compensation value and held-fold economic improvement over the same source model and flat hurdle. Keep probability uncertainty distinct from desired profit margin. Only test a small number of economically motivated interactions after main effects. |
| L1 | How do 2, 3 and 4 legs change calibration, required compensation and capacity? | Matched probability/premium/liquidity/time-to-start cuts; compare combo, per-leg and propagated-spread charges. Hold other policy settings fixed first. Show 5+ and same-game structures in the broad benchmark, but price them only as an explicit model/scope extension with its own correlation validation. |
| R1 | What is the effect of fixture risk limits, independently of other caps? Sweep fixture dollars 100/250/500/1000/2000 at baseline underlying/combo limits, then repeat with fixed relaxed underlying/combo limits. | Continuous $10k ledger, all binding controls, sized/unsized admission, peak and average cash, drawdown and profit per capital-hour. A flat response under another binding cap is not evidence that fixture limits do not matter. Preserve conservative gross risk incidence and canonical fungibility; do not invent hedge credit. |
| R2 | How do underlying limits and sizing interact with fixture caps? Sweep underlying dollars 50/100/250/500/1000 and fixture caps in a bounded grid after R1, retaining original balanced scenarios. Compare full tickets with partial sizing. | Replay chronologically: smaller early fills can change later admission. Evaluate initial capital, settled reinvestment, sustained cash utilization and loss concentration, not merely terminal profit. Include explicit accounting for minimum quantity/fee rounding. Limit values remain research scenarios until frozen and validated. |
| X1 | Are signals robust to timing and market-data artifacts? Retain 0/30/60/120s added-lag sensitivities, source creation/publication checks, true price-change age vs observation age, and historical fee alternatives. | Do not equate simulated added exchange lag with a real delayed Pin feed. Test divergence around source updates and pregame cutoff; distinguish book quotes from historical traded-price proxies. Forward pricing requires actual depth; historical depth substitution remains historical only. |
| X2 | Does shared exposure or correlation explain apparent edge? Inspect same fixture, repeated team across dates, repeated tickets, leg dependencies, common game outcomes and largest print/fixture/date omissions. | Cluster-aware uncertainty and outcome concentration; examine joint calibration conditional on leg probabilities. Model residual dependence before pricing additional same-game structures. A narrow spread does not certify independence. |
| F1 | Can the RFQ strategy capture the historical opportunity? Log quote prices, sizes, source snapshots, latency, RFQ lifecycle, creator history, later marks and actual acceptance when available. | Public-print studies cannot identify acceptance elasticity, competitor behavior or our own fill probability. Shadow quote ladders can describe competitiveness, but hypothetical acceptance stays labeled. Actual small live observations are required to estimate own acceptance and fill-conditioned markouts. Creator rules use only prior observed behavior. |
| A1 | How should MLB and NFL share capital across the week? Report weekday/time-of-day demand, attractive compensation and committed capital-hours. | Descriptive historical sport windows are not contemporaneous allocation evidence. Collect simultaneous forward RFQs; account for NFL demand before kickoff and CFB competition. Select allocation by marginal opportunity subject to shared exposure, not calendar labels alone. |

## Discriminating quote policy

### Forward fill-edge calibration

The execution-validation workstream now records a confirmation-time edge event
for every explicit shadow fill. The primary forward features are the quoted
versus confirmation fair move, fee-adjusted edge, source disagreement, venue
weights, source ages, depth/spread scores, leg count, creator history and
markouts. This makes “too tight” measurable without using later settlement
outcomes in the admission decision. Public prints remain a separate opportunity
benchmark until actual quote acceptance and fill records are available.

A candidate seller quote should separate its fair probability from its compensation requirement. In dollars per contract, an illustrative development family is:

`required compensation = base + spread term + disagreement/freshness term + inventory term`.

All terms use information available at the RFQ time; coefficients and caps must be estimated or selected on July only. Where feasible, propagate uncertainty through the joint probability rather than simply adding leg widths. Under an explicitly independent-leg approximation, the sensitivity of product fair to leg i is the product of the other leg probabilities. This is a candidate uncertainty feature, not a proof of independent outcomes or a validated margin formula. Compare against exact lower/upper products when applicable and avoid double-counting the same spread/fee uncertainty twice.

Solve proposed quote prices using the actual price/size-dependent maker-fee formula and rounding. Do not convert an admission hurdle into a claim that customers paid an incremental surcharge. For printed-price research, hold the observed price fixed; margin variants alter eligibility. For quote-design research, report an acceptance-independent quote ladder until forward execution data support an acceptance model.

## Candidate selection and next actions

1. Finish July coverage and run existing baseline source/entry/leg/spread analyses. Record implementation gaps against the matrix before claiming any hypothesis tested.
2. Run isolated source, surcharge and risk effects, then a small bounded set of prespecified interactions. Prefer stable improvements across July folds and neighboring parameters over a single maximum. Do not optimize a giant Cartesian product and promote its winner.
3. Freeze one primary and at most two challenger policies plus unchanged K and sell-all benchmarks. The freeze includes parameter values, transforms, mappings, fee scenarios, confidence/acceptance criteria, code/input hashes and all trials. Choose economic tolerance thresholds before opening August.
4. Run August once for the frozen primary comparison. Report negative and inconclusive outcomes. Treat data gaps and unresolved fee/market equivalence separately from strategy failure.
5. Translate a defensible candidate into a pricing-shadow configuration, including source-health conditions, canonical exposure and creator logging. Deployment remains conditional on actual quote lifecycle, reconciliation/recovery and forward evidence; it is not automatic after a positive equity curve.

No candidate is frozen by this document. The existing collection, risk settings and live configuration are unchanged.

## Resumed objective and blacklist evaluation

The user authorized continuing all five follow-up workstreams after the initial study and morning synthesis: pipeline recovery/completion, genuine NFL pricing shadow, source ablations, selective margins/risk experiments, and candidate freeze/held-out plus execution validation. The liquidity-weighted K/PM/Pinnacle blend is a central candidate; historical comparisons without Pinnacle cannot resolve it. User trading authorization does not constitute evidence that unspecified hyperparameters or current execution code are ready.

Blacklist evaluation must use creator history available strictly before each RFQ, with versioned reasons, activation/expiry times, minimum evidence and review logs. Compare the identical pricing policy with and without the causal blacklist, recording lost opportunity, concentration and fill-conditioned markouts. Spam and large leg counts are observable behaviors, not by themselves proof of adverse selection. Do not retroactively remove losing historical prints based on future creator outcomes or invent creator IDs missing from the archive. Where IDs are absent, report the blacklist effect as unmeasured and establish a forward baseline. Raw RFQs and market context remain archived even when blacklisted.
# Added development hypothesis: joint reserve and executable quote parity

Exploratory addition after inspecting July results; not part of the original frozen grid. Quantify the gap between historical point-entry selection and actual shadow stressed-upper quoting, then test coherent joint-model alternatives on the same opportunity cohort. The first completed diagnostic spans14priced July dates and finds zero four-leg prints clearing the recorded stressed bound. See [point-versus-shadow reserve study](JULY_POINT_VERSUS_SHADOW_RESERVE.md). Candidate comparisons should retain the worst-case moment bound and evaluate independence with measured marginal uncertainty plus a coherent factor/copula model. No reduced reserve is approved by the diagnostic. Any candidate enters the immutable July development record before August outcomes are read; models adjusted after August require future validation. Preserve all original study hypotheses and full date scope.
