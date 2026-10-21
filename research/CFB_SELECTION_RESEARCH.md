# Selection diagnosis and reusable research infrastructure

September 7, 2026. The blend's selected trades underperformed this CFB week, but the raw −$48k selected versus +$80k rejected comparison exaggerates how cleanly it diagnoses the pricing rule. Large-print exposure, payoff mix, repeated games and unresolved settlements materially affect its interpretation.

![Selected versus rejected, with exposure controls](../runs/cfb_selection_research_20260907/forensics/selection_comparison.png)

## What the deeper audit establishes

All figures below use the 9,511 common-model public prints, hypothetical unlimited selling at their observed prices, maker fees and known settlements. They do not represent our own RFQ wins or a $10,000 funded portfolio. Saturday has full retained print coverage; other days contain retained interval samples. There is no frequency expansion of those samples.

| YES premium scope | Selected known P&L | Rejected known P&L |
|---|---:|---:|
| All observed sizes | −$48,128 | +$80,265 |
| At most $50 per print | −$7,144 | −$2,973 |

Only 274 rejected prints above $200 premium contribute +$78,839, about 98% of rejected net profit. The rejected population commits about $2.23m cumulative NO cash on known outcomes, compared with $243k selected. These are cumulative exposures, not simultaneous required balances. The dollar totals compare substantially different amounts and kinds of risk.

After giving each group the same weights across overlapping leg-count, price and premium bands, mean individual-print return on NO cash is −18.00% selected versus −14.04% rejected. The residual selection disadvantage matters, but this descriptive comparison cannot identify its cause or establish significance from dependent outcomes.

The 20 largest selected losses and 20 largest rejected profits agree with the saved native prices, selected YES/NO leg definitions and official settlement products. The selected loss is −$45,657 before $2,471 in maker fees. A fee adjustment cannot explain most of it. The largest rejected profit came from an Oklahoma State × Duke combo priced at 60.4 cents against a modeled 61.745-cent fair; Oklahoma State subsequently lost. An outcome favorable to the seller does not establish that the original negative model edge was wrong ex ante. Other large rejected winners were positive-edge prints just below the 0.3-cent net threshold.

The strongest remaining symptom is conditional calibration. On ≤$50 selected prints, quantity-weighted modeled YES probability is 26.84% versus 37.14% realized; on rejected prints, 7.47% versus 7.64%. Across the full capped common cohort the residual is only +0.77 percentage points. Selecting where observed combo price exceeds a noisy model can preferentially select the model's downward errors. That is a plausible mechanism, not a demonstrated attribution to a particular venue, customer or delay.

The [full forensics](CFB_SELECTION_FORENSICS.md) includes distributions, exposure standardization, repeated-payoff experiments, leave-one-fixture-out results, and native evidence for the largest P&L contributions. Unknown outcomes remain unknown; the unrestricted rejected profit is not a guaranteed final result.

## What was implemented and tested

1. **Repeatable selection forensics and comparison plot.** `scripts/cfb_selection_forensics.py` exports selection, size/price/time strata, matched exposure comparisons, concentration and traceable native evidence. `scripts/plot_selection_forensics.py` renders PNG/SVG from those outputs.
2. **Chronological validation and source markouts.** `src/combos/research_validation.py` and its CFB runner enforce label availability, whole-fixture purging, fixed calibration rules and explicit insufficient-data fallback. They also expose when native updates cannot support a requested markout horizon.
3. **Composable quote-policy ledger.** `src/combos/quote_policy.py` separates fair, uncertainty, dependence, adverse-selection, inventory, exact cash fees, minimum profit and commercial markup. Optional shadow instrumentation records candidate arithmetic. Quote optimization requires calibrated acceptance and outcome-given-acceptance estimates; none are fabricated from public prints.
4. **Delayed-anchor point estimator.** `src/combos/delayed_anchor.py` combines a verified delayed Pinnacle level with a normalized blend of subsequent exchange log-odds changes, using actual depth and fee-expanded spreads. It refuses unverified clocks, imputed depth and inconsistent payoffs. The result does not supply a calibrated uncertainty bound or authorize a quote.
5. **Bounded three-source capture.** `scripts/shadow_research_capture.py` reconciles the account/budget, starts exchange WebSockets and delayed Pinnacle polling under one frozen runtime, stops its owned processes, and archives observations, RFQs, decisions, health and readiness. It preserves mapping blocks and runs only in shadow mode.

See [quote-policy details](QUOTE_POLICY_RESEARCH.md), [delayed-anchor requirements](DELAYED_ANCHOR_IMPLEMENTATION.md), and [actual capture readiness](SHADOW_RESEARCH_READINESS.md).

The completed bounded capture recorded positive two-sided depth for all 454 configured keys on both exchanges. Four Pinnacle responses each contained 16 fixtures, using four requests (shared usage 19 to 23). None of its 454 mapped keys became an active normalized fair: each snapshot contained 265 payoff-review blocks and 189 selector-review blocks. All raw responses and reasons were retained. This is successful three-source collection, with **zero priceable three-source intersections**.

It also recorded 25,239 `processing_backlog` skips among 69,093 decisions, under the existing two-second lag guard. Feed connections remained up, and all supervised processes and archive/review exports exited successfully. The throughput issue requires investigation before a sustained launch; relaxing the stale-decision guard would hide it. No orders were submitted. The source snapshot and capture hashes preserve the exact version that ran; the research estimator received an additional negative-horizon timestamp guard afterward. The complete suite then passed **219 tests**.

Receive-to-decision latency was 1.344 seconds at the median, 4.687 seconds at the 95th percentile and 6.946 seconds maximum. Of 946 RFQs passing basic scope checks, 307 were skipped for backlog (32.45%). Although most queued traffic was irrelevant to the strategy, the delay also affected eligible requests. Timed `decide()` computation totaled only 0.981 seconds across all decisions; serialization, database work and consumer coordination are outside that timer. Almost all decisions terminated at scope/mapping checks, so this does not benchmark fully functioning pricing. The next runtime work should reduce per-event database and consumer overhead while preserving complete recording, causal creator evidence and the stale-decision cutoff.

## The validation result does not rescue the current model

The [walk-forward run](CFB_WALK_FORWARD_VALIDATION.md) covers all 8,295 common prints meeting the ≤$50 comparison scope. Twenty-four of 28 model/day fits fall back because prior independent training is insufficient. Saturday has only 77 eligible prior prints covering nine fixtures. Only Sunday's 157 prints permit fitting, and that test is highly concentrated. The fixed blend correction changes known selected P&L from −$7,143.97 to −$7,171.97; it offers no demonstrated improvement.

This is retrospective analysis of an already-examined week. Native settlement timestamps are historical availability proxies. It is not a fresh holdout or a forward receipt-time replay.

Scorable blend-selected five-minute Kalshi marks move against the maker by only $2.28 across 1,501 prints. Pinnacle one-/five-minute marks move against the maker by $0.52/$4.65 on much smaller observed-update subsets. These near-term marks do not reproduce the large settlement residual. Their coarse, conditional coverage cannot establish that the fairs were right, nor can it measure a true real-time 30-second correction. They provide no basis for claiming the delay alone caused the losses.

## Research priorities before changing live pricing

First, resolve the Pinnacle mapping and clock prerequisites and retain synchronous bid/ask/depth, inactivity, creator and rejection context. The feed arriving is different from a verified priceable payoff. Keep this readiness issue distinct from the historical selection result.

Second, freeze the existing blend and delayed-anchor candidate for the same new evaluation block. Fit on prior completed fixture slates, then evaluate common-candidate calibration and conditional residuals by probability, price disagreement, market type and fixture exposure. Use outcome-availability timestamps as well as trade-time attribution. A new model picked after seeing the block needs another block for validation.

Third, estimate reserves and commercial markup separately. The prior worst-case dependence reserve that produced zero quotes is an uncalibrated guard. Replacing it with a small arbitrary amount or lowering the point-edge threshold to capture known rejected winners would not solve calibration. Validate dependence and stale-information protection on appropriate joint data, including a no-quote response to unsupported combinations.

Finally, collect actual quote lifecycle outcomes when an execution implementation is ready. A public print clearing our modeled floor measures potential capacity; it cannot establish that our response would win, at what size, or with what conditional selection bias. Shadow observations can validate data and decision mechanics before that execution evidence exists.

The immediate empirical priority is synchronized forward data and a frozen comparison, while extending historical validation to additional accessible slates. The current account's previously tested MLB historical request returned HTTP 403; free request accounting does not establish sport entitlement. No repeated MLB access probe or paid subscription change was made here.
