# Parlay preferences: bounded evidence and tests

## Decision

Prioritize broader request coverage and verified spend sizing before adding a nonlinear edge schedule. The data support a substantial market for NFL props and same-game combinations in the captured request flow. They do **not** establish a reliable favorite-composition premium or price elasticity. Keep the flat-hurdle demand experiment as the prospective test; no quote policy or live execution has been changed here.

This is a completed first-pass hypothesis screen, not an estimate of the entire retail market. Requesters are not verified retail customers. Requests, traded prints, unique tickets, contracts and people are different denominators.

## Evidence populations

| Population | Size | What it supports |
|---|---:|---|
| Raw captured Kalshi RFQs | 47,937; 2,862 creator IDs | Requested contract structure, including requests excluded before pricing |
| RFQs containing NFL | 10,450; 780 creator IDs | NFL-containing versus mixed-sport request mix |
| NFL-only RFQs | 6,254; 504 creator IDs; 1,425 distinct tickets | Primary structural demand screen |
| Priceable NFL scenarios | 694 RFQs, including 617 spend-sized | Indicative fair and leg-probability composition; not customer acceptance |
| Priceable moneyline-only subset | 613 RFQs | Team-favorite composition without mixing spreads/totals |
| Historical NFL prints | 23,809; 13 active dates; 9 fixtures | Gross premium associations in January 5–18 retained data |
| Historical MLB prints | 415,673; 15 retained dates; 402 fixtures | Gross premium associations in July retained data |

The raw capture spans **119.8 seconds**, September 9, 2026, 08:17:50–08:19:49 UTC. Do not annualize it, interpret its RFQ rate as fill throughput, or treat it as a representative daily sample. The largest five NFL-only creator IDs supply 17.6% of requests. IDs need not identify distinct people; repeated requests can be automated, refreshed, or abandoned.

Historical samples are selected, priceable, pregame, distinct-fixture 2–4-leg moneyline YES-taker prints. Their benchmark is the product of selected Kalshi leg midpoints from prior candle books with the archived publication-delay convention. This is neither tick-synchronous executable fair nor a same-game joint model.

## 1. Same-game narratives and player propositions: useful coverage signal

| Share of NFL-only requests | Every RFQ | First request per creator–ticket | Equal weight per creator |
|---|---:|---:|---:|
| Contains recognized NFL player prop | 52.3% | 54.9% | 59.4% |
| Has multiple NFL legs in one fixture | 52.6% | 54.2% | 62.5% |

The first two indicators overlap: 47.2% of raw NFL-only requests contain both. Their union is **57.7%**, rising to **60.4%** when each creator–ticket is counted once. Deduplication leaves 2,409 creator–tickets. These are different estimands, not confidence bounds. Deduplication retains the first observed request and budget.

Of requests containing NFL, including mixed-sport tickets, 42.4% contain an NFL prop and 40.3% contain repeated legs from one NFL fixture. Keeping the sport denominator explicit materially changes the estimate.

The fixture classifier strips market family only for a date-and-matchup-shaped NFL key. It recognizes all NFL fixture shapes in this capture; futures would stay unknown. Recognized prop-family names are explicit in the script, including the native `KXNFLRSHYDS` abbreviation. Multiple alternate thresholds on the same player/game count as same-game legs; no claim is made that these are independent risks.

**Research implication:** widen descriptive reporting and mapping coverage for these structures. Pricing or hedging them is a separate project requiring payoff normalization, redundant-leg treatment and joint distributions. Do not multiply single-leg probabilities to manufacture same-game edges.

## 2. Favorites in long-payout tickets: raw tendency, weak conditional evidence

In the 613 priceable moneyline-only NFL RFQs:

- 74.2% of leg selections have selected-side probability above 50%.
- 52.0% of tickets consist entirely of such favorites.
- Median indicative gross payout multiple is 4.17x, computed as `1 / product_fair`.

The full 694-RFQ subset includes spreads and totals: its 72.3% figure means **likely-side selections**, not necessarily team favorites. Changing the archived source-conversion scenario from 0.1 to 1 to 10 leaves that classification unchanged, while the median implied multiple moves from 4.17x to 4.21x. This sensitivity is not independent source validation.

Favorite legs and a favorite combo are not synonymous: three 60% legs produce a 21.6% independent combo. Furthermore, combo probability and leg count mechanically constrain favorite composition.

To check that confound, enumerate complementary selections on each RFQ's same fixtures, retain hypothetical tickets within a fixed fair tolerance, and compare observed composition with a uniform average over those alternatives. Only RFQs with more than one matching alternative contribute:

| Fair tolerance | Moneyline RFQs with overlap | Creator IDs | Observed favorite-share mean | Matched uniform mean |
|---|---:|---:|---:|---:|
| ±1c | 83 / 613 | 24 | 45.3% | 47.4% |
| ±2.5c | 216 / 613 | 43 | 67.2% | 67.5% |
| ±5c | 298 / 613 | 55 | 64.3% | 64.2% |

These averages weight RFQs equally; the earlier 74.2% weights individual leg selections. Creator-balanced observed-minus-null differences are +0.36, +2.99 and +1.38 percentage points respectively. This weighting sensitivity and limited overlap prevent a strong conclusion. The hypothetical choice set is not proof that the platform offered every alternative, and uniform choice is a diagnostic null, not a utility model.

Historical favorite-leg shares also differ substantially: **55.5% NFL versus 79.0% MLB**. All-favorite tickets account for 25.3% of NFL prints and 60.1% of MLB prints, but only 19.3% and 54.2% of contracts respectively. These differences argue against importing one universal retail preference coefficient across sports, seasons and sampling mechanisms.

**Verdict:** likely legs in multi-leg tickets are common; excess preference conditional on payout is not convincingly established here.

## 3. Does composition improve the gross premium model? No useful validation win

Response: `100 * (trade YES price - product of selected Kalshi mids)`, in cents before fees. Base controls: cubic combo midpoint, sum of leg widths, log hours to first game, log maximum source age, log quantity and leg-count indicators. In-sample fits also include date indicators. Add favorite-leg share, weakest-leg probability and standard deviation of leg probabilities jointly.

| Sport | Extra partial R², print-weighted | Extra partial R², contract-weighted | Later-date contract-weighted MSE change from adding composition |
|---|---:|---:|---:|
| NFL | 1.85% | 0.30% | **23.3% worse** |
| MLB | 0.089% | 0.373% | **6.7% worse** |

Chronological training uses the first two-thirds of retained dates and scores the remaining dates. Forward models omit date indicators unavailable on new dates. Coefficients are fitted only on training rows; training and test date lists are saved. Leave-one-date-out refits are sensitivity checks, not confidence intervals.

NFL's later-date contract-weighted MSE is 0.1166 cents² for a learned constant, 0.5011 for the base model and 0.6178 for composition. The richer models are much worse than a learned constant here. All 7,122 later NFL prints contain training fixtures; strict fixture-disjoint forward validation leaves **zero** observations.

MLB retains 162,834 fixture-disjoint later prints. On those, contract-weighted MSE is 0.10255 for a learned constant, 0.10019 for the base and 0.10459 for composition: composition is still **4.4% worse** than the base. Contract-weighted MAE also worsens, from 0.1844c to 0.1954c. The learned constant has the lowest MAE, 0.1779c.

**Verdict:** do not promote these composition variables into the edge function from this evidence. They remain useful reporting strata. These tests predict observed gross premiums, not acceptance, execution-conditioned adverse selection, net PnL or an optimal hurdle.

## 4. Payout targets versus spend targets: distinguish observed from inferred

The retained RFQ messages specify spend or contract quantity, not a desired gross payout multiple. `1 / fair` is our calculation, and `1 / traded_price` conditions on execution. Neither is an observed customer payout target. Quote grids, leg combinations and product menus could create apparent round-multiple clustering. A credible round-payout-target test is therefore **not identified** with these fields.

There is direct evidence of spend denomination: **86.6%** of NFL-only RFQs are spend-sized. Among 5,416 positive spend-sized requests, **56.7% request exactly $10**. That rises to 73.7% across first creator–ticket observations; the median requested spend is $10 in all three leg-count bands.

A descriptive within-creator regression of log requested spend on log leg count has slope -0.152, versus -0.147 after first creator–ticket deduplication. It is consistent with modestly smaller requested budgets on longer tickets, but no significance or causal claim is warranted in this short window. UI defaults and repeat-request behavior are alternative explanations. This is not a price elasticity estimate.

**Research implication:** verify spend-sized quote construction before using the 77 fixed-size dry-run RFQs to generalize about demand. Budget heaping is worth a daily report; it does not establish customers' willingness to pay a larger edge.

## 5. Team/player concentration: measurable, star preference not yet isolated

The captured NE–SEA fixture appears in **78.3%** of NFL-only requests. This is a substantial slate-concentration confound before interpreting player rankings. The top player token occurs across 186 creator IDs and 261 distinct tickets, not only one repeating requester.

The raw player-token ranking is concentrated in the captured NE–SEA fixture. Leading NFL-only YES-side player tokens are `NEDMAYE10` (1,455 RFQs), `SEASDARNOLD14` (1,138), `NEABROWN1` (1,122), `NERSTEVENSON38` (1,079) and `SEAJSMITHNJIGBA11` (869). These are market identifiers, not an independently verified current roster or popularity ranking. A player is counted once per RFQ even if several thresholds are selected; NO selections remain separately labeled.

Historical selected-market rankings are also saved, with both print-weighted and first-unique-ticket views. For example, the January NE selection against LAC appears in 8,623 retained NFL prints. Those counts do not control for the opportunity to select that team, fixture timing, outright trading interest, favorites or available prop offerings.

**Verdict:** concentration is real in the retained requests, but “star players are over-demanded” is not established without a slate/offerings denominator and independent popularity features. Do not fit a star surcharge from names selected after inspecting the ranking.

## 6. Price sensitivity and markouts: unavailable, not negative results

The saved flat-arm demand dry run still reports zero observed customer exposures, and the response scorer requires frozen prospective assignments. No acceptance-by-feature or causal price-elasticity regression can be run from these artifacts. Simulated fills remain excluded. No new live quotes were sent.

Retain a small predefined set of prospective interactions: leg count, pre-treatment fair band and fixed-size versus verified spend-sized requests. Add props/same-game strata only after correct pricing and risk support exist. Measure assignment-to-exposure failures, acceptance, actual execution, fee-adjusted 10/30/60/300-second markouts and missing-mark coverage separately. Daily monitoring is descriptive; it is not repeated hypothesis testing until significance.

## External research register

1. **Newall et al., request-a-bet study (2020):** custom soccer requests favor long payouts and prominent players; median gross return £9 per £1 risked. This motivates composition and concentration tests, but the authors' selected UK custom-request sample is not a US retail census. [Primary paper](https://doi.org/10.1556/2006.2020.00054)
2. **Flutter Investor Day (2024), pricing discussion:** operator evidence links player-market expansion, same-game adoption and additional legs. Treat product availability and promotion as confounders, not merely customer taste. [Transcript, pp. 7–8](https://flutter.com/media/34ppqgc0/investor-day-2024-transcript.pdf)
3. **Levitt (2004):** foundational NFL price-and-quantity evidence on bettor favorite preferences and bookmaker behavior; historical spread betting, not a modern parlay acceptance estimate. [Published paper](https://pricetheory.uchicago.edu/levitt/Papers/LevittWhyAreGamblingMarkets2004.pdf)
4. **Rutgers / New Jersey DGE report, Table 16:** stronger additional source for leg counts, based on almost 18 million parlay records. It reports roughly 64% with 2–5 legs, 28% with 6–10, and 9% with 11+, with median four legs. Important bibliographic caveat: the linked report is titled calendar-year 2020, but this section and its methodology explicitly discuss 2019. Use it as an older benchmark, not a 2026 target distribution. [Report, printed pp. 17–18](https://socialwork.rutgers.edu/sites/default/files/2024-02/2020sportswagerreportrevised121523.pdf)

Local NFL-only shares are **54.7% / 28.7% / 16.6%** in those leg bands, versus **62.6% / 24.0% / 13.4%** after creator–ticket deduplication. The long-ticket tail remains worth measuring, but differences in year, product menu, requests versus purchases and capture window prohibit a clean cross-market preference claim. Very long same-game tickets may include redundant/nested thresholds, so leg count is not independent risk count.

A bounded alternative-site search found Substack discussion of favorite parlays and price sensitivity, and a Medium article proposing parlay insurance pricing. These provided no verified acceptance dataset or stronger preference test and were not used as empirical inputs. Further browsing was stopped once the regulator-based benchmark and local coverage findings supplied actionable leads.

## Next research priorities

1. **Coverage:** repeat the broad RFQ mix report across representative game windows, tracking same-game/props, leg count, source coverage, unique creator–tickets and observed spend. The current narrow pricing subset is not the whole opportunity set.
2. **Sizing and evidence:** verify spend-based sizing and prospective exposure capture before running an acceptance experiment. This is the immediate measurement dependency.
3. **Pricing restraint:** retain flat 0.3c as the benchmark, not a proven optimum. Do not deploy a composition curve or star premium on these results.

No additional broad literature search or model sweep is justified by this first pass. New data should address the specific missing denominators above.

## Reproduction and artifacts

```sh
.venv/bin/python scripts/parlay_preference_study.py --out runs/parlay_preference_study_20260909
.venv/bin/python scripts/parlay_preference_diagnostics.py --folder runs/parlay_preference_study_20260909
.venv/bin/python -m pytest -q tests/test_parlay_preference_study.py tests/test_demand_experiment.py tests/test_quote_policy.py
```

Outputs in `runs/parlay_preference_study_20260909/`:

- `results.json`: input SHA-256 hashes, raw/priceable population summaries, composition regressions, forward tests and limitations.
- `diagnostics.json`: creator-ticket/spend robustness, same-fixture hypothetical alternatives, player-token concentration and fixture-disjoint forward tests.
- `raw_rfq_features.jsonl.gz`, `priced_rfq_features.jsonl.gz`, `historical_features.csv.gz`: reproducible feature-level audit records; requester identifiers stay local.

Tests cover probability validity, favorite legs versus combo probability, same-game detection across market families, spend retention, creator balancing, exact hypothetical-choice overlap and recovery of known regression coefficients. The real-data run additionally verifies one-to-one historical joins, complete retained-row recovery and midpoint-product equality. Forty targeted tests passed.
