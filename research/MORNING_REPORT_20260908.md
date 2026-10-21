# Morning research report — September 8, 2026

For the shorter findings and next-days plan, read the [morning brief](MORNING_BRIEF_20260908.md).

Interim evidence snapshot updated September 08, 2026 03:21 CDT. This is an evolving report: 9 of 31 planned July/August MLB dates have completed model processing. The results below cover seven inspected July dates, with continuous funded results still limited to the explicitly named three-Wednesday subset; completed August 12 and 26 outcomes remain unread pending the July candidate freeze. The existing September 5 reference is separate. The first five raw tapes are complete and the separate 26-date expansion collector is live. Remaining collection and analysis stay in scope. July 11 cohort collection is live. The complete January 5–18 NFL study, calibration and capital-hours reviews are finished; older NFL subsets below remain explicitly historical checkpoints. No live orders are running.

Historical September 7 collection-timing checkpoint: measured remaining tape work was approximately 247,000 public GETs. Even allocating the entire shared 5.56 requests/second cap would take about 12.4 hours for tape alone; current concurrent throughput implies longer. Full 31-date completion by morning is therefore not expected. This interim report will be refreshed with completed coverage while the full collection continues; missing dates will not be replaced by a smaller sample.

The [throughput audit](MLB_COLLECTION_THROUGHPUT_AUDIT.md) supports continuing the current collectors. Available disk space was approximately 40 GiB at the September 7 21:47 Chicago check. The original additional-storage estimate omitted cumulative replay retention and is superseded by the correction below; the [updated final-snapshot forecast](MLB_FINAL_STORAGE_FORECAST.md) estimates 48.3–65.1 GiB of additional work against 39.84 GiB free, a possible 8.5–25.3 GiB shortfall. This includes the final input database as well as all 48 policy outputs. The layout is not yet proven to fit; a more compact representation or verified archival and a final launch reserve are required. A first exact-byte database compression pass recovered 0.772 GiB; a local size probe shows native compression refusing a 520 MiB file despite compressing an equivalent 480 MiB file, so multi-gigabyte savings cannot be assumed. A further completed-catalog pass recovered 0.329 GiB. Lossless codec benchmarks suggest about 3 GiB additional final-output savings with Zstandard, or 5.5 GiB with substantially slower XZ; these estimates do not close the full projected gap. Additional space or another volume has been requested while collectors continue. The storage watcher monitors free space, with review at 20 GiB and urgent review at 15 GiB. Raw data and the full date scope remain intact.

A subsequent retention audit found that saving every growing cumulative replay would exceed available disk space. The idle cumulative watcher is intentionally stopped after its complete three-date result; collectors and daily processing continue. Exact-byte deduplication has processed 30 completed gzip artifacts, and transparent filesystem compression saved approximately 1.13 GiB across 11 completed JSON artifacts without changing their contents or paths. The new disk-backed replay has completed all 48 policies in a fresh immutable snapshot in 310.68 seconds, with peak memory of 838,402,048 bytes including plotting. Both the first run and the finalized wrapper match every decoded decision, fill and curve row and all summary metrics against the retained three-date oracle: 3,482,928 decisions, 364,804 fills and 3,545,353 curve rows, with zero summary rounding exceptions. All four PNGs are byte-identical. This validates implementation parity on three dates, not full-period performance. See the [implementation and scheduling report](MLB_STREAMING_LONGITUDINAL_IMPLEMENTATION.md).

MLB remains worth testing, but the evidence does not yet establish repeatable deployable edge. The broad positive seller outcome is concentrated in individual games; model-selected funded returns are much smaller. Wednesday should currently be planned as a diagnostic shadow session. A live launch additionally requires reviewed pricing mappings and execution/reconciliation implementation.

## 1. Universe profitability

**New first-Friday checkpoint — July 3:** the [completed native-universe plot](../runs/morning_research_20260908/universe_july3/universe.png) shows 178,933 YES-taker prints, $6,793,116.38 YES premium, $109,232,721.32 payout face and **−$2,884,545.06 eventual net P&L** after $165,656.66 scenario maker fees. All native outcomes are known. Combo metadata recovered all 520,945 tape tickers and underlying metadata all 718 requested markets. The [independent full-row audit](../runs/morning_research_20260908/universe_july3_audit/verification.json) passes; exchange histories and model selections are still processing.

Distinct fixtures contribute −$2,953,514.99 versus same-game +$68,969.93. Full-game core contributes −$2,965,489.72; known-prop-containing +$30,878.65 and other markets +$50,066.01. Every leg-count and premium band is negative, including at-most-$10 prints (−$190,165.32). Pregame schedule proxy contributes −$1,627,674.54. These cuts overlap. The broad loss is already approximately $2.72m before fees; fee omission would not reverse its sign. No claim about Friday model selection is available yet.

The [recomputed four-date universe](../runs/morning_research_20260908/universe_july1_3_15_29/universe.png) contains 806,175 YES-taker prints, $32.24m YES premium and $484.10m payout face, with +$701,724 net under scenario fees. Distinct-fixture prints now lose $487,307, while same-game structures earn $1,189,032. Removing July 29 NYY–CWS turns the pooled result into **−$1,423,523**. Friday’s loss also survives removing its largest losing fixture, MIL–AZ (remaining −$903,905). These are overlapping fixture-membership diagnostics, not new outcome filters. The earlier three-Wednesday conclusions below describe that narrower subset only; their fixture-omission positivity no longer holds for the four-date sample.

The complete July 1, July 15 and July 29 pure-MLB YES-taker universes contain 627,242 prints, $25.449 m YES premium and $374.865 m payout notional. Hypothetically selling all these prints at observed prices produces $3,586,269 eventual net P&L after $618,850 in scenario maker fees. All outcomes are known. Payout notional means maximum customer payout if YES wins; it is not actual winnings. These totals include props, same-game structures, more than four legs and post-start trades. All three inspected July dates are Wednesdays. The current results cannot establish weekday allocation advantages; the frozen 31-date expansion covers other weekdays.

Daily contributions are July 1+$1,704,235, July 15+$91,249 and July 29+$1,790,785. With three dates pooled, removing any single fixture leaves positive net P&L; the minimum is +$1,461,022 after removing July 29 NYY–CWS. That is stronger cross-date evidence than the original two-date result. Individual-day outcome concentration remains substantial: July 29's NYY–CWS contribution exceeds that day's total profit, so excluding it makes the day negative, just as removing LAD–ATH makes July 1 negative. Overlapping fixture contributions must not be added as independent bets.

Across these dates, full-game-core prints contribute +$2.756 m; known-player-prop combos +$688 k; distinct-fixture structures +$2.466 m; pregame scheduled-time proxy +$2.367 m. All four leg-count groups and all four premium bands are positive. These are overlapping alternative cuts, not additive separate strategies, and remain unlimited public-print benchmarks.

[Full-universe plot](../runs/morning_research_20260908/universe_july1_15_29/universe.png) · [Underlying results and provenance](../runs/morning_research_20260908/universe_july1_15_29/summary.json). Connections across unobserved dates must not be read as intermediate trading with zero returns. Unlimited exposure has no defensible funded-return Sharpe denominator. July 29 fair-value replay is now complete; its separate results are below. The continuous funded table now uses all three dates.

## 2. Model selection and calibration

Common primary eligibility is 2–4 legs, distinct fixtures and pregame, with compatible source histories. July 1 has 31,263 common priced prints; July 15 has 392. July 15 coverage is only 392/1,202 primary eligible prints. The [mapping audit](JULY15_MAPPING_AUDIT.md) found that MLB advanced NYM–PHI by one hour on July 16, explaining conflicting native and PM clocks. A reviewed separate mapping overlay could recover up to 343 additional prints, raising common coverage to 61.1%, but price histories still need acquisition and the archived sources do not establish when the revised schedule became known on July 15. TB–BOS game 1 remains unmatched. Treat coverage as selective, not a random sample of missing trades. Baseline matching has not been relaxed.

The pooled opposite-moneyline spread decomposition now covers 56,286 common moneyline prints across July 1, 15 and 29. Per $1 payout contract, quantity-weighted compensation after fees is negative for every model: Kalshi −0.4389 c, Polymarket −0.2307 c, equal blend −0.3346 c and PM75 −0.2826 c. Realized seller P&L is +5.0716 c for all four because this is the same unfiltered cohort. The positive fair-minus-outcome residual may reflect miscalibration or favorable realized games; it is not compensation that we successfully charged.

[Three-date spread decomposition and regression output](../runs/morning_research_20260908/pooled_spread_july1_15_29/REPORT.md). Exact pooled quantity-weighted fits are used rather than averaging daily regressions. August 12 has now completed processing, but its outcome summaries have not been inspected; July development is still incomplete.

The Kalshi raw realized-P&L slope is −0.186 c per additional cent of summed spread; controlling for combo price and leg count changes it to +0.318 c. Removing one fixture at a time yields an adjusted range of −0.908 to +1.775. The compensation slope changes from +0.102 c raw to −0.025 c adjusted; its adjusted deletion range is −0.058 to −0.010. Wider spreads therefore do not yet justify a calibrated surcharge or hard filter on this evidence. Price and leg-count controls materially change the conclusion, and the overlapping fixture-deletion ranges remain descriptive influence checks.

The [three-date paired source-selection audit](../runs/morning_research_20260908/disagreement_july1_15_29/REPORT.md) gives a specific positive PM result. At 0.3 c/combo contract, PM-only selections contain 3,477 prints and +$175,539 unlimited net P&L, versus 84 Kalshi-only prints and +$3,137. Pooled PM-only P&L remains positive after deleting each individual fixture (minimum +$52,957), and PM's quantity-weighted Brier improvement remains negative in every deletion (−0.002641 to −0.001077). Kalshi-only profit changes sign under deletion. This supports continuing the PM-disagreement hypothesis, but July 29 alone remains concentrated as discussed below. It does not test Pinnacle-and-PM consensus because Pinnacle is absent, and selection itself mechanically favors particular disagreements.

The separate [July 15 mapping-revision replay](../runs/july15_mapping_overlay_20260907/REPORT.md) has now recovered 342 genuinely priced prints from 7 public history requests: expanded common coverage 734/1,202 (61.1%). One additional mapping-complete print still lacks prior PM price history. The original 392 common rows have identical prices, fees and risk identities. Expanded July 15 unlimited Kalshi selection changes from −$3,049 to +$736; PM changes from −$2,281 to −$3,038. The expanded sell-all result is −$705. Funded expanded Kalshi returns −$37 and PM +$77, with peak cash below $600. This reversal in unlimited model rankings is a concrete coverage-sensitivity warning. The three-date baseline tables below exclude this retrospective mapping overlay; do not silently combine versions or add independently funded subset P&Ls.

July 29 now adds 40,906 common model-priced prints out of 43,830 eligible (93.3%). All moneylines mapped; 112 unmatched legs are exact spread/total outcomes absent from saved markets. Missing-line occurrences affect 1,633 unique prints; another 1,291 prints fail solely for missing prior PM history. No timestamp repair is justified by the current audit.

At 0.3 c/combo contract, July 29 unlimited selection results are Kalshi +$1,244, PM +$37,636, equal −$448 and PM75−$7,187. Funded results are −$12,+$126,−$3 and +$298 respectively, with peak cash $566–$1,229. Common sell-all is +$419,463. However, [selected-fixture omissions](../runs/morning_research_20260908/july29_selected_fixture_audit.json) turn PM's unlimited result as low as −$29,825; Kalshi's much smaller profit remains positive under each omission (minimum +$621). The [paired Brier comparison](../runs/morning_research_20260908/disagreement_july29.json) is essentially tied overall (PM minus K −0.00000215 quantity-weighted), with equal-print Brier slightly favoring Kalshi. July 29 therefore gives a more mixed picture than simply trusting the PM-selected equity curve.

## 3. Continuous funded replay

One $10 k ledger across July 1, 15 and 29, actual settlement cash release, $100 underlying/$100 combo/$250 fixture limits, no ticket cap. P&L below is eventual outcome attributed to trade time; it is not spendable cash before settlement. These are full observed-ticket sizing results on 72,561 common prints per model.

| Model | Net point-edge hurdle | Fills | Eventual net P&L | Peak committed cash |
|---|---|---:|---:|---:|
| kalshi | 0.3 c/combo contract | 118 | $26.60 | $565.96 |
| kalshi | 0.3 c/leg | 86 | $-20.59 | $541.81 |
| polymarket | 0.3 c/combo contract | 236 | $433.77 | $1,229.31 |
| polymarket | 0.3 c/leg | 130 | $726.51 | $743.06 |
| exchange_blend_equal | 0.3 c/combo contract | 144 | $89.37 | $667.96 |
| exchange_blend_equal | 0.3 c/leg | 82 | $320.73 | $516.77 |
| exchange_blend_pm75 | 0.3 c/combo contract | 179 | $492.35 | $942.16 |
| exchange_blend_pm75 | 0.3 c/leg | 96 | $367.69 | $516.77 |

The existing 0.3 c default is per combo contract. The separate per-leg policy multiplies the hurdle by leg count: 0.6 c for two legs through 1.2 c for four. Prior conversational shorthand must not collapse these units. Both variants are retained for comparison, without choosing a winner from these three dates.

[Continuous funded/unlimited comparisons](../runs/mlb_historical_20260907/longitudinal/versions/99747429892956068fe7/summary.json). Partial sizing is also implemented and tested. On July 1, PM peak cash rises from $840 to $1,228 but P&L falls from $302 to $262, because earlier partial fills can consume shared risk capacity and displace later trades. Low utilization is not automatically repaired by increasing fill count or removing pricing discipline. Risk calibration awaits the larger dataset.

On July 29, [partial sizing](../runs/morning_research_20260908/completion/2026-07-29/partial_sizing/REPORT.md) raises PM peak cash from $1,229 to $1,376 but reduces net P&L from $126 to $75. Equal blend improves from −$3 to +$89; Kalshi declines from −$12 to −$51. These separate daily experiments again show that increased participation is not equivalent to improved performance.

## Source-timing sensitivity

The [July 1 timing study](../runs/mlb_timing_sensitivity_20260907/july1/REPORT.md) and [July 15 study](../runs/mlb_timing_sensitivity_20260907/july15/REPORT.md) add 30/60/120 seconds of information delay to both archived exchanges, beyond the baseline 60-second publication allowance. Actual trade prices, timestamps, fee-effective dates, outcomes and settlement cash release are unchanged. Zero-added-lag reconstruction exactly matches all 129,026 July 1 model rows and 2,378 July 15 rows. The four-model/four-lag common cohorts contain 31,194 and 375 prints respectively; coverage losses are reported separately.

On July 1, an extra 30 seconds moves the quantity-weighted absolute combo fair by only 0.0032–0.0040 c. PM common unlimited P&L changes from +$154,575 to +$152,612; funded PM changes from +$245 to +$242. At 120 seconds, unlimited PM remains +$149,802 and funded PM +$257. Other models also retain the broad July 1 profit pattern. July 15's 30 second mean fair moves are larger,0.0176–0.0318 c, but funded results remain unchanged at that lag.

This provides no evidence that modest extra archived exchange lag explains the large earlier losses or gains on these pregame cohorts. It supports treating source coverage, calibration and fixture concentration as higher-priority questions in the current evidence. It does not establish that a 30 second Pinnacle feed is harmless: Pinnacle is absent, history is minute resolution, and public prints do not identify the RFQs we would win during rapid moves. The tail distribution and live response selection still need observation. Four causal/fee-clock tests pass.

## 4. NFL cross-check

[Broad NFL equity and volume plot](../runs/nfl_native_universe_20260908_jan5_12/plots/native_universe.png) · [Plot verification and workflow](NFL_NATIVE_UNIVERSE_PLOTTING.md). All 396,085 timestamps are retained, with daily P&L variance and four explicit fee scenarios.

The [broad native NFL seller benchmark](NFL_NATIVE_UNIVERSE_JAN5_12.md) now covers all 457,147 YES-taker prints from January 5–12, without pricing, leg-count, phase, capital or concentration filters. YES premium is $13,968,262.37 and payout face is $186,655,696. At the unverified 0.035 maker coefficient, net P&L is **−$388,155.61**, comprising **−$33,263.93 before fees** and $354,891.68 modeled fees. This is a public-print seller counterfactual, not observed industry maker P&L or an executable strategy.

Same-game structures contribute +$655,754.50 and distinct fixtures −$1,043,910.12; full-game core contributes −$1,183,835.43 and known-prop-containing trades +$795,679.82. These are overlapping cuts. January 10 loses $1.85m, followed by approximately +$0.94m and +$1.03m on January 11 and 12. The completed [SF–SEA identity overlay](NFL_SFSEA_SEMANTIC_FIXTURE_OVERLAY.md) merges two native date tokens into one semantic game: ten games replace eleven tokens. Its 3,839 unique prints contribute −$843.46; summing the two token contributions would incorrectly count 528 shared prints twice. Root independently reconciled the union against all 457,147 ledger rows. Total P&L and the baseline 2,140 unknown-schedule labels are unchanged. The structure cuts above retain native-token definitions; 186 prints change from distinct to same-game under the retrospective identity overlay, moving +$2,737.26 between those cuts. The corrected semantic same-game result is +$658,491.77 and distinct-fixture result −$1,046,647.38.

[Full native verification](../runs/nfl_native_universe_20260908_jan5_12/verification.json) reconciles every source row and all 396,085 curve timestamps across four fee scenarios, preserving 27 fractional settlements and separating 2,140 unknown schedules. The common model-priced comparison below is a narrower cohort; do not substitute broad-universe profits for model-selection results. NFL cohorts are now complete through January 15; the remaining dates through January 18 are still collecting.

January 5–11 now supplies **16,219 common priced moneyline prints**, including 7,768 newly priced January 11 prints. All four models use the same cohort; all selected outcomes are known. Pinnacle is absent. The January 5–18 collection remains in progress.

January 12 tape and cohort processing have also completed, but add no commonly priced trades. Its 265 eligible moneyline prints all include a divisional-round fixture whose matched Polymarket market was created on January 13 according to cached catalog metadata. The saved history queries requested earlier dates, so the initial evidence supports a genuine availability gap rather than an accidentally shortened query. These excluded prints total $9,811.27 YES premium and $46,980 payout face. They are not modeled as zero demand, and later PM prices are not backfilled into earlier decisions. The [completed mapping and coverage audit](NFL_JAN12_COVERAGE_AUDIT.md) found no join or query-bound error. A separate Kalshi-only diagnostic could price 264 of these prints; it must not be substituted into the paired comparison.

The [January 12 window-extension verification](../runs/morning_research_20260908/nfl_jan12_window_extension.json) confirms all 64,876 model rows, decisions, fills and trade-time economics are identical to the January 5–11 replay across all 16 ledgers. Extending the window releases the remaining settlement cash; it does not add trading profits or independent observations. The existing January 5–11 plots therefore remain the primary economic comparison.

At the explicitly unverified .035 maker-fee scenario, unlimited sell-every-print produces **−$298,835** with **$2,465,915 peak committed cash**. This benchmark covers the common 2–4-leg, distinct-fixture, pregame moneyline cohort, not every NFL combo. Model selections at 0.3 cents net per combo contract compare as follows:

| Model | Unlimited selected P&L | Funded selected P&L | Funded fills / evaluations | Funded peak cash |
|---|---:|---:|---:|---:|
| Kalshi | $61,245.81 | −$2.12 | 15 / 16,219 | $139.07 |
| Polymarket | $22,536.35 | −$111.69 | 29 / 16,219 | $208.57 |
| Equal blend | $41,225.18 | $6.74 | 14 / 16,219 | $118.02 |
| PM 75% | $38,663.27 | −$50.91 | 12 / 16,219 | $174.50 |

Removing the largest winning print ($19,504) now leaves all four unlimited selections positive: Kalshi +$41,742, PM +$3,032, equal +$21,721 and PM75 +$19,159. However, removing all selected prints involving PHI–SF makes every model negative: Kalshi −$3,181, PM −$26,402, equal −$14,403 and PM75 −$19,325. The larger sample strengthens selection versus sell-all on these realized games, but still does not establish independent, repeatable NFL edge. Kalshi leads the unlimited selection result here; the MLB PM-disagreement hypothesis must remain sport-specific.

[Expanded replay and fee scenarios](../runs/nfl_moneyline_replay_20260907/jan5_11/REPORT.md), [unlimited comparison plot](../runs/nfl_moneyline_replay_20260907/jan5_11/plots_final/unlimited.png), and [funded comparison plot](../runs/nfl_moneyline_replay_20260907/jan5_11/plots_final/funded.png). The new plots reuse existing ledgers without changing any decision, show equity/P&L, net point edge, YES premium/payout face and committed cash, and display daily P&L variance in USD². Sharpe is withheld because seven observed dates share few underlying games. The raw replay's annualized short-sample statistic is not used as launch evidence.

The [independent accounting audit](NFL_JAN5_11_INDEPENDENT_AUDIT.md) reconciles all 16 ledgers, 64 model portfolios and 204 source/input hashes, including decimal fees, outcome P&L and settlement-clock cash; no fee double charging was found.

All unlimited model selections remain positive in the four maker-fee scenarios (0/.0175/.035/.07), but these change both fees and the set of qualifying prints. They are not four independent tests, and their historical effective dates are unverified. The earlier January 5–10 snapshot is retained separately; no independently funded subsets were added together.

The [updated structural capacity audit](../runs/morning_research_20260908/nfl_capacity_ceiling_jan5_11.json) still finds six moneyline risk buckets, at least two per trade. With each bucket capped at $100 and each position's entire rounded NO cost charged to every bucket, the **absolute risk-only ceiling remains $300**. PM's $209 peak is about 70% of that loose ceiling. Lower edge hurdles alone cannot make $10k deployable under these constraints.

For the separate MLB common daily cohorts, analogous loose ceilings are $4,625 on July 1, $1,100 on July 15 and $5,375 on July 29. Bucket universes cover the whole input window, so actual concurrent capacity can be lower. Risk limits should be calibrated from the broader loss/concentration evidence; committed capital remains a ceiling rather than a utilization target.

## 5. Sequence into NFL opening week

- Tuesday: finish available-date audits, resolve mapping discrepancies through reviewed evidence, freeze the research candidate before examining held-out outcomes, and certify live source freshness/depth and payoff equivalence. Retain historical fee and Pinnacle coverage limitations explicitly.
- Wednesday: diagnostic shadow before the opener. Record incoming RFQs, all leg mappings, source receipt/provider timestamps, two-sided books, fee-expanded fair intervals, point fair, uncertainty/edge charge, executable size, canonical exposure, every skip and proposed response. A session that only skips is a capture test, not a successful pricing shadow.
- Thursday: review Wednesday's coverage, response latency, source disagreements, hypothetical fill assumptions and creator behavior. Correct implementation faults before changing pricing parameters.
- Friday through Sunday: if the data supports an MLB candidate, compare opportunity per committed dollar and hour against football demand. Friday/Saturday need not be exclusive MLB days; future NFL games and CFB can generate competing RFQs. A live pilot needs a working execution state machine, reconciliation/restart tests and explicit readiness evidence first.

The official schedule evidence and exact remaining implementation gaps are in [launch-readiness audit](MORNING_LAUNCH_READINESS.md). Current historical PM/K results do not establish a sharp-heavy three-source fair or confirm live MLB feed entitlement. A 30-second Pinnacle delay remains a testable design constraint; it should not be asserted to explain losses without timing evidence.

## Remaining completion work

Complete all 31 dates and NFL January 5–18; rerun full universe, common model selection and source-disagreement comparisons; finish pooled spread regressions; assess untouched validation with shared-fixture purge; conduct fee/timing sensitivities; calibrate capacity on the broader sample; and update this report with a concrete candidate or reasons no candidate survives. Two-date Sharpe and weekday ranking are not sufficient evidence for risk allocation.

Verification for recent additions: 13 targeted pooled-calibration/NFL tests pass. Pooled July 1 coefficients agree with the original row-level implementation within 6.2 e-11; retained parity evidence also checks bins, R² and fixture-deletion slopes. Latest full repository suite passed 531 tests in 7.86 seconds after the streaming replay, timing, capacity and storage additions. These tests do not certify historical fee effective dates, exceptional settlement equivalence or live fills.

The [completion handoff](MLB_COMPLETION_HANDOFF.md) records the July candidate freeze, August validation boundary, capacity evaluation and final replay scheduling requirements.


## Capital-hours measurement

The [new reusable cash-occupancy workflow](REPLAY_CAPITAL_HOURS.md) independently reconciles curve integrals to fill holding periods across all 16 January 5–12 NFL portfolios. Funded selections occupy approximately $65–$113 on average over the eight-day window. Equal blend earns $0.542 per 1,000 committed dollar-hours; Kalshi −$0.124, PM75 −$3.054 and PM −$5.136. This is descriptive capital efficiency, not annualized return or a scalable live yield. Complete MLB comparison remains pending the full continuous replay.


## Wednesday lifecycle implementation update

A [separate sustained shadow supervisor](SUSTAINED_SHADOW_SUPERVISOR.md) now supports reviewed shadow configurations without modifying the blocked 90–120-second smoke wrapper. Root independently passed all 18 focused tests, including actual offline runtime initialization, synthetic RFQ processing, drainage, archive and export. The supervisor checks source/configuration hashes, directly supervises collectors/workers, reconciles each RFQ source sequence, and validates quote-context depth/latency before reporting guarded pricing observed. No feeds or orders were started. Reviewed mappings and actual healthy-input soak evidence remain pending; this does not change the live-execution readiness conclusion.


## Lossless final-replay storage update

The [optional Zstandard integration](MLB_STREAMING_ZSTD_INTEGRATION.md) has passed exact full-policy parity on the retained three July dates: all 144 decoded row artifacts and four PNGs match, with no summary rounding exceptions. It reduces row-artifact bytes by 23.39% (about 170 MiB on this sample) and leaves the default gzip mode available. Full-period input/index capacity still needs monitoring; this gain alone does not establish that the remaining workload fits. No raw data or date scope was removed.


## July 3 common-model replay checkpoint

The baseline report now contains 26,176 common priced prints out of 29,594 eligible (88.5%); Pinnacle is absent. Selling every common print loses $1,198,875.69 after scenario fees. At the unchanged 0.3¢ per combo contract hurdle, results are:

| Model | Unlimited selected P&L | Unlimited fills | Funded selected P&L | Funded fills | Funded peak cash |
|---|---:|---:|---:|---:|---:|
| Kalshi | −$30,638.35 | 228 | −$24.13 | 60 | $1,100.69 |
| Polymarket | −$129,950.09 | 2,295 | +$53.36 | 80 | $1,208.98 |
| Equal blend | −$22,867.89 | 299 | +$45.72 | 60 | $931.83 |
| PM 75% | −$50,843.02 | 756 | −$15.25 | 66 | $1,084.63 |

[Funded plot](../runs/mlb_historical_20260907/dated_fee_primary/2026-07-03/common_model_report/constrained.png) · [Unlimited plot](../runs/mlb_historical_20260907/dated_fee_primary/2026-07-03/common_model_report/unconstrained.png). These are one-day portfolios with actual settlement-time cash release and eventual P&L attributed to trade time, not additions to a continuous four-date funded ledger. All selected outcomes are known, including settlements after the reporting endpoint. The [independent selected-ledger audit](MLB_JULY3_SELECTED_LEDGER_AUDIT.md) passes all eight portfolios and 209,408 decisions. The [entry, spread and capacity review](MLB_JULY3_SPREAD_CAPACITY_REVIEW.md) is also complete. Smaller selected losses reflect substantially less exposure and do not by themselves prove improved probability calibration.


### July 3 selection and calibration audit

Native outcome joins, once-only fees, and the 0.3¢ per combo selection hurdle reconcile independently. Removing each unlimited model’s worst print still leaves it negative. PM-only selections lose $127,531.35 across 2,154 prints; K-only selections lose $28,219.62 across 87. The quantity-weighted PM-minus-K Brier difference is +0.00079734 (lower is better), and each of 44 fixture omissions still favors K. This reverses the direction seen in portions of the earlier Wednesday sample; it is a reason to preserve direction-conditioned disagreement tests across all development dates, not to retune weights on Friday. Pinnacle agreement remains untested.

A conservative cash-reservation precision issue adds $0.0001 on 61 funded fills, totaling $0.0061 across four separate portfolios. It does not affect the recorded P&L and cannot explain losses. Exact-cash cleanup is recorded for a later reviewed change; the active batch source remains frozen. See the [audit and reproducible evidence](MLB_JULY3_SELECTED_LEDGER_AUDIT.md).


### July 3 unique-print coverage reconciliation

A separate [context-presence audit](../runs/morning_research_20260908/july3_coverage_audit/verification.json) reconciles all 29,594 eligible IDs without duplicates: 29,401 have complete Kalshi context and 26,176 have common exchange context. The 3,418 exclusions are unique prints, unlike the overlapping leg-error counts in the pricing report. There are 758 prints with only unmatched PM mappings, 1,715 with only matched PM legs lacking usable context, 752 with both, and 193 additionally missing Kalshi context. Within the latter group, 59 have both PM gap types, 92 have matched-PM context gaps, and 42 have unmatched mappings. These disjoint categories sum exactly to 3,418. A matched mapping without usable context does not by itself prove a provider outage: prior-history availability and the historical K spread proxy still need to be distinguished. No missing depth or future price was imputed in this audit.


### July 3 spread and capacity implications

The [completed review](MLB_JULY3_SPREAD_CAPACITY_REVIEW.md) separates compensation from settlement residual on 20,660 moneyline prints. Raw spread width has a +5.190¢ net-return slope per 1¢ of width, but only approximately +0.079¢ comes from compensation. Controlling for traded price and leg count reduces the net slope to +3.198¢, with a fixture-omission range crossing zero. This is not a measured optimal surcharge, and shared outcomes can dominate a single date's residuals.

The 0.3¢ per-leg hurdle produces small positive unlimited results for Kalshi/equal/PM75 ($274/$175/$162) while PM loses $24,557. Equal and PM75 turn negative under fixture omissions; the smaller samples do not validate a winning policy. At the baseline 0.3¢ per-combo hurdle, balanced $1,000 contract/combo and $2,000 fixture limits raise peak cash to $6,086–$8,527, but all four portfolios lose. Capital-only portfolios lose $2,636–$7,488. Capacity should be calibrated on broader loss evidence, not increased merely to consume $10k. These are full-size historical-print scenarios; partial sizing and actual quote acceptance are separate questions.


### January 17 NFL collection checkpoint

January 17 cohort completed with exit 0: 224,178 pure-NFL prints, 170,548 target-fixture prints and 4,560 primary candidates. Root independently verified all six certified output hashes and the 24 contiguous hourly tape manifests; [completion evidence](../runs/morning_research_20260908/nfl_jan17_completion_check.json). January 18 remains pending. These are coverage counts, not new profitability results; the final cumulative replay still awaits the complete January 5–18 window.


### July 5 Sunday native-universe checkpoint

The new Sunday cohort is certified: all 453,790 combo definitions recovered, with no metadata budget exhaustion, and 24 contiguous census manifests independently verified. Its 207,677 pure-MLB prints include 187,774 YES-taker seller-proxy prints and 19,903 excluded NO-taker prints. The broad seller benchmark earns **$1,931,852.34 after scenario fees**, on $7,527,404.52 YES premium and $107,227,109.43 payout face. Modeled fees total $184,001.65; native settlement obligation is $5,411,550.53. The [independent native-row and concentration audit](MLB_JULY5_UNIVERSE_AUDIT.md) passes. All 63 native-token fixture-omission portfolios remain positive; removing the largest contributor, July 5 SD–LAD, leaves +$618,549.68.

All major plotted leg-count, family, structure, phase and premium cuts are positive on this date. [Sunday universe plot](../runs/morning_research_20260908/universe_july5/universe.png) has been visually inspected by root. This adds a positive Sunday alongside a losing Friday, not evidence of a stable weekday allocation rule. The model replay and daily sweeps have since completed; their separate cohort results appear below. Unlimited public-print P&L is not achievable earnings on $10k. Fee effective dates remain scenario assumptions, and August outcomes remain withheld.


### July 5 model replay checkpoint

The common exchange cohort contains 22,487 of 26,530 eligible prints (84.8%); Pinnacle is absent. The 0.3¢ per combo hurdle and baseline risk limits are unchanged. The [independent selected-ledger/calibration audit](MLB_JULY5_SELECTED_LEDGER_AUDIT.md) verifies all eight portfolios and 179,896 decisions, with no duplicated fees.

| Model | Unlimited P&L | Unlimited fills | Funded P&L | Funded fills | Funded peak cash |
|---|---:|---:|---:|---:|---:|
| kalshi | $69,809.36 | 603 | $38.16 | 91 | $907.54 |
| polymarket | $190,862.75 | 5,582 | $-7.39 | 114 | $1,049.74 |
| exchange_blend_equal | $158,971.65 | 1,748 | $49.43 | 105 | $970.62 |
| exchange_blend_pm75 | $211,519.49 | 2,997 | $-61.40 | 120 | $940.91 |

The unlimited gains require approximately $300k–$1m peak committed cash. The funded portfolios stay near flat and below $1,050 peak cash. Neither daily funded result should be added to earlier daily portfolios as if it were one continuous account. Actual settlement releases cash; eventual outcomes remain attributed to trade time. The [independent spread and capacity review](MLB_JULY5_SPREAD_CAPACITY_REVIEW.md) is complete, including 12 artifact/hash checks.


### July 5 calibration and selected concentration

Selling every print in the 22,487-print common cohort earns $396,446.09 under scenario fees. All unlimited selections are positive, but removing July 5 SD–LAD makes PM −$4,158.42; Kalshi/equal/PM75 remain +$12,467/+31,352/+47,553 after that omission. PM has the better quantity-weighted Brier score overall (PM minus K −0.00073687), yet the same fixture omission flips the difference to +0.00025350. The apparent pricing advantage and selected profit share fixture dependence.

PM-only selections earn $116,307.11 on 5,105 prints; K-only loses $4,746.28 on 126. Directional disagreement findings reverse those on July 3. Both sources overpredict Sunday's quantity-weighted realized settlement frequency after underpredicting Friday's. Preserve fixed directional comparisons across the remaining development dates; switching source preference after seeing each day's outcomes would not validate a live rule. The [full audit](MLB_JULY5_SELECTED_LEDGER_AUDIT.md) retains exact arithmetic and all omissions. Conservative float reservation noise totals $0.0093 across funded portfolios and does not explain performance.


### July 5 spread and capacity review

The spread-covered moneyline subset contains 18,372 prints and earns $304,654.91 (7.049¢ per contract). Raw-width net slope is −3.150¢ per additional 1¢ summed width, opposite July 3's +5.190¢; price/leg-adjusted slope is −4.381¢ with fixture-deletion range [−9.064, −0.363]. Compensation slopes are much smaller and model-dependent. These date reversals do not identify a stable liquidity surcharge or causal toxicity effect; settlement residuals dominate both days.

At 0.3¢ per leg, all four unlimited selections remain positive under every single-fixture omission on July 5. Larger risk budgets also profit on Sunday: balanced $1,000 scenarios deploy $8.1k–$10k and earn $1.1k–$1.9k. Capital-only profits of $2.9k–$6.2k contrast with Friday's $2.6k–$7.5k losses. A higher utilization target magnifies outcome dependence; the complete development/held-out risk comparison is still required. Peak committed cash may exceed initial $10k after actual settlement gains are recycled; these scenarios model starting capital, not a permanent $10k commitment ceiling. Full details: [July 5 review](MLB_JULY5_SPREAD_CAPACITY_REVIEW.md).

### NFL tape completion

All 336 January 5–18 hourly partitions are collected. Root polled the retained collector session and confirmed exit code 0. January 18 cohort worker 94367 is live; the final model/universe replay awaits its completed census and output certification. Tape completion alone is not final research completion.


### Full January 5–18 NFL native benchmark checkpoint

All 14 cohorts are now certified, with 84 output hashes and 336 contiguous hourly source manifests checked. The full native benchmark completed successfully: 1,016,915 pure-NFL prints, including 982,703 YES-taker seller-proxy prints. Under the primary .035 maker scenario, net P&L is **+$3,111,351.38**, on $29,091,651.79 YES premium and $396,423,283 payout face, after $742,676.53 fees. All outcomes are known. Fee scenarios 0/.0175/.035/.07 produce net +$3.854m/+$3.483m/+$3.111m/+$2.369m. Historical effective-date applicability remains unverified.

This supersedes the January 5–12 broad benchmark as the full-window result; the earlier negative subset remains explicitly labeled above. Independent full-window native/curve verification, concentration and plot review are underway. The paired moneyline replay has started separately and may cover a much smaller priced cohort. No live profitability or attainable $10k return is inferred from the broad unlimited benchmark.


### Full NFL native audit: scope and concentration

Independent verification passes all 982,703 seller rows, 819,658 cumulative curve timestamps across four fee scenarios and 84 input hashes. It preserves 65 fractional settlements and 87,048 unknown schedules. Under the separately labeled retrospective SF–SEA identity merge, that fixture's 186,876 prints contribute $2,786,432.32; omitting them leaves $324,919.06. The total is unchanged by the alias overlay.

Semantic same-game structures earn $3,749,364.54 across 863,612 prints, while 119,091 distinct-fixture prints lose $638,013.16. The overlay reclassifies 9,990 prints and does not repair historical pricing eligibility or kickoff knowledge. Native full-game core loses $371,597.44; the 39,278-print primary structural scope loses $182,661.27. Consequently the profitable broad universe does not directly support the current distinct-game pregame no-prop strategy. The paired model results remain a separate comparison.


## Full NFL paired replay completed — September 8

All 14 January 5–18 cohorts and 336 hourly partitions are certified. The completed replay has 23,809 common prints and 95,236 model rows. The independent audit passes all 16 ledgers/64 portfolios, 246 source/input hashes and native outcome/price/quantity/time matches. Primary .035 scenario: common sell-all −$300,290.32; unlimited selected K/equal/PM75/PM +$62,749.36/+$46,846.83/+$48,835.59/+$43,529.08. Funded selected −$29.40/+$37.38/−$26.73/−$73.66, with peak cash $139.07/$118.02/$174.50/$208.57. All four unlimited results turn negative when PHI–SF is omitted. This supersedes partial-window NFL headline results; earlier subset analyses remain historical checkpoints.

The complete native universe earns +$3,111,351.38 over 982,703 YES-taker prints, but native primary structural scope loses $182,661.27; same-game/prop gains are not evidence for the intended independent-leg model. Historical Pinnacle and actual quote acceptance remain unvalidated. See [full paired audit](NFL_JAN5_18_INDEPENDENT_AUDIT.md) and [full native audit](NFL_NATIVE_UNIVERSE_JAN5_18.md). MLB collection remains live, July 7 metadata is progressing, and the full 31-date development/held-out workflow is unfinished.

Full-window plots (rendered and visually checked): [funded](../runs/nfl_moneyline_replay_20260907/jan5_18/plots_final/funded.png) · [unlimited](../runs/nfl_moneyline_replay_20260907/jan5_18/plots_final/unlimited.png). Legends include daily P&L variance; Sharpe is withheld because the short sample shares few fixtures, and the unlimited portfolio has no fixed capital denominator.


## Full NFL capital occupancy

The [capital-hours audit](NFL_JAN5_18_CAPITAL_HOURS.md) reconciles 16 ledgers/64 portfolios. Nine common canonical moneyline buckets imply a loose $450 simultaneous-cash ceiling at $100 each and at least two distinct buckets per combo. Funded selected average occupancy is only $71–$103 over 336 hours. This is a structural constraint, not evidence that lowering the entry charge can deploy $10k. 55 of 64 portfolio capital cycles extend beyond the reporting boundary; eventual P&L per capital-hour is withheld for those incomplete denominators. A separately labeled full-liquidation sensitivity subsequently completed using retained actual settlement timestamps; see the completed settlement-tail section and its linked report.


## Full NFL calibration and selection disagreement

[Calibration review](NFL_JAN5_18_CALIBRATION_REVIEW.md): all 23,809 common prints and 4,897,161 payout contracts are retained. Quantity-weighted Brier K/equal/PM75/PM is .16276233/.16282138/.16285307/.16288621. PM minus K is +.00012388, but fixture omissions range −.00067104 to +.00072148. This does not establish stable source superiority. Both models accept 804 prints earning $41,142.64; K-only 503 earn $21,606.72; PM-only 1,230 earn $2,386.43; neither 21,272 lose $365,426.12.

Selected modeled compensation is only $5,438.80/$5,250.87/$5,465.97/$5,996.15 (K/equal/PM75/PM), versus realized $62,749.36/$46,846.83/$48,835.59/$43,529.08. Favorable settlement residuals dominate realized selected profit. The public traded prices are observed selection opportunities, not quotes we actually charged; the fixed hurdle remains 0.3 cents per combo contract. These findings reinforce separate sport models and prospective validation rather than extrapolation of realized profit.


## NFL settlement-tail analysis complete

The [full-liquidation capital-hours sensitivity](NFL_JAN5_18_FULL_LIQUIDATION_CAPITAL_HOURS.md) closes all 64 portfolio denominators using retained actual settlement times; maximum tail 2.29684 hours. No unknown timestamps/outcomes, repricing or new trades. Event-sweep and fill-duration integrals reconcile and all final exposures are zero. Primary 336-hour reporting is preserved. Under .035, funded efficiency per $1,000 committed-dollar-hours is K −1.00559/equal +1.56564/PM75 −.90140/PM −2.11207; unlimited selected +10.03840/+6.98433/+5.89291/+3.63546. These are realized, concentration-sensitive occupied-cash ratios, not scalable expected yields.


## July 7 cohort and native universe complete

Cohort exited 0; root verified 7 output hashes and 24 contiguous hourly census manifests. All 386,896 combo definitions recovered; 259,101 pure MLB prints, 70,332 full-game pregame proxy candidates. Native benchmark completed, with 226,760 YES-taker prints and no unknown outcomes: net +$225,986.8117, fees $215,906.38554, gross +$441,893.19724. Independent full-row audit passes. Scheduled-pregame −$581,259.1239; after-start +$807,245.9356; distinct −$189,939.1082; core −$4,610.586. COL–LAD membership +$1,913,985.1156; omission leaves −$1,687,998.3039. Three of 65 fixture omissions reverse total sign. These are influence diagnostics.

Root visually inspected [July 7 universe plot](../runs/morning_research_20260908/universe_july7/universe.png). Exchange acquisition and paired model replay remain pending; seven dates are fully processed, with July 7 the eighth completed native cohort rather than an eighth completed full research pipeline. August outcomes remain unread.

July 7 full-row evidence: [native universe audit](MLB_JULY7_UNIVERSE_AUDIT.md).


## July 7 paired audit complete; eight dates processed

All July 7 pipeline stages, including entry/risk sweeps, have completed. The [selected audit](MLB_JULY7_SELECTED_LEDGER_AUDIT.md) checks all 8 portfolios / 163,088 decisions and native joins without sampling. The common 20,386 prints lose $313,202.35 under sell-all. Unlimited K/equal/PM75/PM results are +$2,535.18/+$1,304.94/−$2,958.69/−$16,907.64; funded results are +$69.27/−$242.16/−$233.62/−$200.19.

PM−K quantity-weighted Brier is +.00085980, positive across all 43 fixture omissions [.00025726, .00115383]. K-only 15 prints earn $1,182.83; PM-only 524 lose $18,259.99. Kalshi unlimited remains +$243.07 after its largest positive-fixture omission; equal flips to −$765.38. Conservative extra reservation totals $.0027 across 27 accepted records, with no economic discrepancy. Root visually checked funded/unlimited plots and completed stage/source hashes. At this checkpoint, spread/capacity interpretation remains under review and full 31-date validation is still pending.


## July 7 spread/capacity review complete

The [review](MLB_JULY7_SPREAD_CAPACITY_REVIEW.md) verifies 14 hashes and component identities. The common spread cohort contains 15,586 moneyline prints: net −$232,838.07 on $3,229,788.84 face. The raw-width net slope is +6.080; the price/leg-adjusted slope is +9.327 c/c, positive through 31 fixture deletions. The fee-expanded adjusted slope is +1.134, with range [−.819, +2.857]. Compensation slopes are much smaller than residual slopes. Prior July 5 raw slopes were −3.150/−4.381, so no stable daily surcharge is inferred.

All zero-edge and .3c/leg unlimited selections lose. The .3c/leg K/equal/PM75/PM results are −$1,136/−$1,163/−$1,672/−$2,416. At .3c/combo, K remains positive across fixture omissions. Balanced1000 K/equal/PM75/PM net is +$59/−$898/−$889/−$1,208; capital-only net is −$288/−$1,302/−$2,812/−$5,611. Cash deployment increases without stable profit. These runs do not use partial sizing. Keep fixed scenarios for pooled development and held-out evaluation. At this checkpoint, July 9 cohort worker 95893 is live; the full 31-date scope remains pending.


## July 9 native cohort and audit completed

The cohort is certified: 360349/360349 definitions, 24 contiguous census manifests and 7 output hashes; 314083 pure MLB rows and 99718 full-game pregame proxy prints. The native report completed and root visually inspected it. The [independent full-row audit](MLB_JULY9_UNIVERSE_AUDIT.md) verifies 275489 YES prints: net −$1,575,735.269, gross −$1,319,182.23561, fees $256,553.03339, premium $10,657,183.44209 and face $157,788,651.3. All 72 native-fixture omissions remain negative; removing PHI–CIN leaves −$66,565.29. Pregame net is −$332,066.49; distinct-fixture net is −$1,860,860.58; core net is −$1,714,778.07. All premium buckets are negative.

The CHC–BAL 13:35/18:35 market/event clock alias affects 2266 YES prints, totaling +$1,926.0102. A narrow retrospective identity overlay reclassifies 193 prints, with +$2,663.1795, as SGP; the total is unchanged. Semantic distinct-fixture net is −$1,863,523.7585; SGP net is +$287,788.4895. No schedule, payoff or pricing repair was made. At this checkpoint, exchange acquisition is complete and the paired replay is processing. The full 31-date and held-out scope remains unfinished.


## July 9 selected audit complete

The [full selected audit](MLB_JULY9_SELECTED_LEDGER_AUDIT.md) passes 8 portfolios / 285144 decisions / 14 completion hashes. The common 35643 prints lose $800774.48 under sell-all. Unlimited K/equal/PM75/PM results are +$13485.26/+$11057.52/+$24219.66/+$64769.27; funded results are +$68.22/−$35.79/+$33.17/+$35.07.

PM−K quantity-weighted Brier is −.00020991 overall, but omitting NYY–TB changes it to +.00012829; 44 of 45 other retained-key influence comparisons favor PM. Omitting NYY–TB leaves selected K/equal at +$3911.11/+$397.40 and PM75/PM at −$6987.66/−$3837.77. PM-only 1716 prints earn +$57064.68, contrary to July 7. Model edge for K/equal/PM75/PM is $512.80/$748.11/$1546.40/$3737.76, much smaller than realized profit. Root report-hash and visual checks are complete; the native clock-alias caveat is retained without repricing.


## July 9 spread/capacity review complete

The [review](MLB_JULY9_SPREAD_CAPACITY_REVIEW.md) verifies recorded hashes and component identities. The common spread cohort has 30329 prints and $6847764.74 face, with net −$897265.1829; the broader entry cohort has 35643 prints and net −$800774.4799. Raw net-width slopes are +6.469/+6.829 c/c, with unadjusted omission range [−1.809, +8.920] and adjusted range [+.760, +8.811]. Fee-expanded slopes are +1.748/+6.455, with unadjusted range [−.913, +2.496]. Residuals dominate compensation.

All zero-edge unlimited selections are negative; all .3c/combo selections are positive. K/equal remain positive under every fixture omission, while PM-heavy selections can flip. All .3c/leg selections are positive, but each can flip after an omission. The .3c/leg K/equal/PM75/PM results are +$38/+$9469/+$9675/+$11235.

Balanced1000 net for K/equal/PM75/PM is −$77/+$524/−$162/−$689; capital-only net is −$2124/+$1932/−$959/+$7473. PM peak cash of $15123 reflects reinvestment of actual settled gains, not early release of trade-attributed P&L. There is no partial sizing. Root's 14 hash checks and report-link verification are retained. At this checkpoint, July 11 worker 96927 is live; 9 dates are processed, and the full 31-date July development / August held-out workflow remains unfinished.

