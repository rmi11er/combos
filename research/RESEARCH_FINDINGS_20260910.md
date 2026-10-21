# Combo opportunity research: findings

Study date: September 10, 2026. Historical-only research; no live quotes, risk limits, or scope filters changed. Round-spend remains a retained feature, with discount testing tabled as requested.

Open the [20-chart research atlas](../visualizations/07-research-program/index.html). Each chart has expandable exact values and sample counts. Full machine-readable results are in `runs/research_program_20260910/`.

## Findings at a glance

| Study | Finding | Research decision |
| --- | --- | --- |
| NFL markouts | Positive selected edge mostly survives an hour against leg mids, but changing horizon cohorts exaggerates the apparent decay. | Track balanced-cohort and available-cohort curves together. Do not equate midpoint marks with executable profit. |
| Volume-conditioned marks | Busy-day selected prints look better descriptively; causal volume adds little predictive accuracy in the later period. | Retain volume and kickoff separately; no volume-based edge change justified yet. |
| Volume clock | MLB has strong, repeatable late acceleration; the trained clock improves August forecasts. NFL shape is less stable. | Useful for MLB opportunity pacing, with wide uncertainty; not a promise of offsetting flow. |
| Hedge economics | Crossing into leg delta hedges consumes the mean later-period selected edge even before leg fees. | Do not assume a 0.3c combo edge can fund routine aggressive leg hedging. |
| Inventory relief | A 0.1c reducing-only hurdle helps the later NFL sample but underperforms the full period at the main fee scenario. Results change with fees and triggers. | Keep as a research candidate, not a deployment conclusion. Settlement-aware risk is necessary. |
| Same-game opportunity | Same-game-containing tickets are 57.1% of the scoped historical prints; observed single-game portfolios demonstrate meaningful but selection-sensitive offsets. | Material opportunity set, but volume alone does not justify removing the same-game pricing guard. |

## Data and design

NFL: January 5–18, 2026, 14 hash-verified complete daily censuses. The moneyline volume study uses **25,107** 2–4-leg distinct-fixture pregame combo prints on both taker sides, before applying price coverage. Price/hedge/inventory studies use **23,809** common-priced YES-taker prints, nine fixtures, and the saved Kalshi leg histories. The volume clock has eight observed first-kickoff groups, five earlier and three later. Same-game analysis uses the wider pure-NFL universe and explicitly filters full-game moneyline/spread/total combinations.

MLB volume replication: **31 retained complete cohort dates** across July/August, not complete months. There are **585,691** prints in **290** fully observed same-day final-six-hour first-start groups. July 13 and July 15 have no qualifying six-hour group; those dates are not silently called zero-volume games. August evaluation has 144 active groups over 15 dates. Unlike the earlier priced MLB replay, the tape study can retain July 13's cohort even though no comparable priced replay exists.

All periods were already accessible to earlier research. “Train/test” denotes a chronological fit/evaluation split, not an untouched holdout. Trades share games; neither print counts nor nominal day bootstraps establish thousands of independent observations. Fee coefficients are research scenarios, not certified January effective schedules.

## 1. Price-based NFL markouts

The panel reconstructs every entry fair exactly from its archived selected leg sides. Future marks use Kalshi minute-candle states available under a 60-second publication-delay assumption. There is no changing source blend, so these are actual underlying-reference price changes rather than the weight-only movement found in earlier short captures.

Seller net markout is observed combo premium minus future independent leg-mid product minus the archived combo maker fee per contract. Positive means favorable for the hypothetical YES seller. It is not a combo exit price or realized hedged return.

| Horizon | Available pregame marks / 23,809 |
| --- | ---: |
| 1 minute | 23,809 |
| 5 minutes | 23,085 |
| 15 minutes | 21,509 |
| 60 minutes | 18,210 |
| Pregame close | 23,809 |

Later horizons crossing first kickoff are excluded rather than filled with an in-play or settlement price. Close is the last available reference evaluated 60 seconds before conservative scheduled first kickoff; it is not the literal last exchange quote. Freshness is raw source age, not verified feed heartbeat. Sensitivities use unrestricted, 180-second, and 600-second ages at both entry and mark.

### Cohort-composition follow-up

Require entry net edge at least 0.3c and all five future marks to exist with age at most 180 seconds. This leaves 314 earlier-period and 53 later-period prints. Requiring future coverage is a retrospective diagnostic, not an entry rule.

| Mean cents per combo | Jan 5–11 | Jan 12–18 |
| --- | ---: | ---: |
| Entry net edge | 0.506 | 0.494 |
| 1-minute mark | 0.500 | 0.480 |
| 5-minute mark | 0.489 | 0.468 |
| 15-minute mark | 0.464 | 0.448 |
| 60-minute mark | 0.429 | 0.409 |
| Close mark | 0.507 | 0.789 |

The favorable one-hour midpoint edge survives in both periods. However, the earlier period's unbalanced fresh selected sample goes from 1.081c at one minute to 0.432c at an hour, while the balanced sample declines only from 0.500c to 0.429c. Much of the apparent steep decay in the first comparison is different prints entering the averages, not a price path experienced by the same trades. The excluded late-pregame prints may be economically important; this result does not establish their missing post-kickoff marks.

Artifacts: `extraction.json`, `nfl_panel.jsonl.gz`, `volume_markouts.json`, `hedge_followup.json`.

## 2. Day volume, causal intensity, and time to kickoff

Final-day contract volume defines descriptive low/medium/high buckets using earlier-period cutpoints. Prior-hour volume excludes the current print and every print at the same timestamp, with earlier-period cutpoints frozen for later evaluation. Day-to-date volume is also computed causally. The tape denominator includes unpriced prints; future price availability does not define the volume series.

For later-period edge-selected, fresh 60-minute marks:

| Volume cut | Prints | Mean markout, cents |
| --- | ---: | ---: |
| Final-day low | 19 | 0.303 |
| Final-day medium | 10 | 0.288 |
| Final-day high | 24 | 0.544 |
| Prior-hour low | 31 | 0.311 |
| Prior-hour medium | 22 | 0.547 |
| Prior-hour high | 0 | unavailable |

This is suggestive segmentation, not a monotonic causal volume effect. The highest causal bucket has no later-period selected observations. The atlas also shows premium, leg spread, leg count, and kickoff cuts, with missing cells explicit. The machine-readable file contains all-print and selected-print summaries across three freshness specifications and both periods.

### Predictive follow-up

Fit on Jan 5–11 and evaluate Jan 12–18. Controls include initial net edge, premium and premium squared, leg count, mean leg spread, and log source age. Add log prior-hour/day-to-date volume, log time to kickoff, or both. Initial edge is controlled so the study does not mistake larger starting markup for better subsequent movement.

| Later-period MAE, cents | Controls | + volume | + kickoff time | + both |
| --- | ---: | ---: | ---: | ---: |
| 5-minute mark | 0.0405 | 0.0403 | 0.0410 | 0.0407 |
| 60-minute mark | 0.2079 | 0.2075 | 0.2072 | 0.2098 |
| Close mark | 0.7350 | 0.7322 | 0.7132 | 0.7201 |

Volume's incremental accuracy is tiny in this split. Time to kickoff is not demonstrated to be merely a volume proxy: it adds more at close, where the elapsed price horizon itself differs. No significance or causal claim is made from these small dependent slates, and no fitted pricing curve is deployed.

## 3. Calibrating volume time

Group trades by the first scheduled game in their combo. Report contracts, principal dollars, and print counts separately. NFL uses a fully observed 120-hour window; both sports also have comparable six-hour views. MLB curves use only groups whose entire six-hour window lies within a retained complete day. Curves condition on observed active groups, not every listed or potentially constructible combo. Native schedule proxies do not certify actual kickoff/first pitch or listing-time-adjusted intensity.

### MLB replication

Equal-day average intensity per first-start group rises from **609 contracts/minute at 6–3 hours** to **6,531 contracts/minute at 15–1 minutes** in August: approximately **10.7 times**. July shows the same shape, 646 to 6,460. Print intensity likewise rises from 2.67 to 19.64 per minute in August, so the finding is not solely larger ticket sizes.

At one hour remaining, August still has **49.9%** of final-six-hour contracts ahead on an equal-day basis, or **45.0%** contract-weighted. The comparison matters: a few large groups should not define a universal clock. NFL's later-period equivalents are 24.4% and 34.5%, a materially different shape on only three kickoff groups.

### Remaining-volume forecasting follow-up

Fit elapsed-volume fractions on earlier groups, then infer remaining volume from the group's volume already observed at the cutoff. No final evaluation-period totals enter predictions. Compare with carrying forward constant average pace. Error below is sum of absolute errors divided by sum of actual remaining contracts (WAPE).

| MLB August lead time | Trained clock error | Constant-pace error |
| --- | ---: | ---: |
| 15 minutes | 50.4% | 80.3% |
| 1 hour | 51.3% | 76.0% |
| 3 hours | 50.8% | 75.2% |
| 5 hours | 55.9% | 73.7% |

At one hour the clock beats constant pace in 116/144 groups. The equal-date error difference is -23.2 percentage points; its descriptive 15-date bootstrap interval is approximately [-31.8, -15.1] points. The forecast still overpredicts aggregate remaining volume by 18.9% and retains large absolute errors. This supports pacing, not precision sizing or assured risk-offsetting demand.

NFL is not similarly established: on three later groups, clock versus constant WAPE is 115.3% versus 96.3% at one hour and 75.0% versus 95.4% at six hours. Date weighting and contract weighting disagree, and uncertainty is broad. Do not transfer the MLB calibration to NFL.

Artifacts: `mlb_volume_clock.json`, `volume_markouts.json`, `final_analysis.json`.

## 4. Leg-hedge economics

Use independent-product deltas: each leg's hedge quantity per combo is the product of the other selected leg probabilities. Charge entry ask-minus-mid and modeled leg fees. A second experiment crosses into those leg positions and back out at future bids, leaving the combo marked to its future fair. This is an approximate, continuously sized static delta hedge—not exact conjunction replication, a depth-verified execution, or a realized combo roundtrip.

| Later-period selected cohort, n=53 | Mean cents per combo |
| --- | ---: |
| Entry net edge before leg hedging | +0.494 |
| After entry spread, zero leg fees | -0.036 |
| After entry spread and coefficient 0.035 leg fees | -0.870 |
| After entry spread and coefficient 0.07 leg fees | -1.703 |

The one-hour delta roundtrip mark is approximately -3.90c at coefficient 0.07 versus +0.409c unhedged. Even the zero-fee roundtrip is negative. This unfavorable cost result does not depend solely on the larger fee scenario.

As an alternative check, buying one full unit of any selected binary leg superhedges one conjunction unit. No selected print in either period pays enough to cover the cheapest such leg at the archived ask, even with zero leg fees. This is a sufficient hedge, not proof of the globally cheapest possible replication.

Archived candles contain no executable sizes. Thus this study can test historical price economics and rule out attractive averages under the stated assumptions, but cannot certify historical executable capacity. Venue-specific live hedging, passive fills, fee rounding, order size increments, and exceptional settlements are not imputed. Cross-venue PM bid/ask depth is not fabricated from midpoint history.

## 5. Inventory-conditioned 0.1c pricing

Replay public YES-taker prints chronologically with actual recorded settlement cash flows, original full print sizes/prices, and no daily cash reset. Starting capital is $10,000. A candidate qualifies for the lower hurdle only when it strictly reduces sensitivity of a constrained fixture, does not increase current positive worst-case portfolio loss, and passes all remaining limits. Sensitivity is the maximum loss change when flipping that fixture while holding other unresolved fixture outcomes fixed. Enumerate all 512 binary states of nine NFL fixtures; no probability model is needed for this risk calculation.

The default $100 contract/$100 combo limits reproduce the earlier 21-fill, -$29.40 baseline. They bind before fixture sensitivity reaches the relief triggers: no discounted fills occur. This is not evidence that relief is ineffective when genuinely fixture constrained.

### Capacity sensitivity and settlement correction

To exercise that condition, a research-only sensitivity uses $1,000 per contract, $250 per combo, and $250 fixture sensitivity. Gross collateral is still reserved and is never netted by economic offsets. These limits are not proposed live changes.

The outcome-aware follow-up fixes fixture sides revealed by settled winning binary combos, only from the earliest corresponding historical settlement timestamp. NO combo settlements do not identify individual winners and are not used for that inference. Public observation latency and all exceptional settlement semantics remain assumptions. Keeping both outcomes indefinitely is retained as a conservative comparison, not treated as reality.

| Policy | Full Jan 5–18 PnL | Later Jan 12–18 PnL |
| --- | ---: | ---: |
| Net-risk flat 0.3c | $156.52 | $42.65 |
| 0.1c relief at 80% utilization | $108.69 | $114.06 |
| 0.1c relief at 90% utilization | $41.71 | $56.30 |
| 0.1c relief at 100% utilization | $103.74 | $42.65 |
| Net-risk flat 0.1c, diagnostic | $0.24 | $102.02 |

At the 90% trigger, the full-period rule admits 12 discounted prints with -$113.80 settlement PnL. Added normal-price fills contribute +$70.68, while displaced baseline fills would have contributed +$71.69. The net change is -$114.81. In the later period, three discounted prints contribute +$13.58 and the overall improvement is +$13.65. The requested capacity effect exists, but its profitability is not consistent.

### Fee and trigger follow-ups

| Combo maker coefficient | Full flat 0.3c | Full 90%-trigger 0.1c relief | Later flat 0.3c | Later relief |
| --- | ---: | ---: | ---: | ---: |
| 0 | $42.20 | $175.24 | $47.77 | $158.58 |
| 0.0175 | -$3.62 | -$10.23 | $87.78 | $109.84 |
| 0.035 | $156.52 | $41.71 | $42.65 | $56.30 |
| 0.07 | $36.53 | $19.87 | $1.73 | $1.73 |

Fee changes alter which prints enter a constrained book, not just PnL on a fixed set. Zero-fee relief is favorable; the main scenario is not. The 0.2c relief and 80/90/100% trigger sweeps are retained, including unfavorable arms, rather than selecting the best result after the fact.

A final entry-freshness follow-up requires source age at most 180 seconds under the 0.035 maker scenario. Full-period flat 0.3c earns $109.14 versus -$2.11 for 90%-trigger 0.1c relief (80%-trigger relief earns $58.53). The later-period comparison is unchanged. Stale entries therefore do not explain away the full-period underperformance.

Every net-risk entry obeys the fixture limit, but later settlement removal can increase the still-conservative residual scenario sensitivity. For example, the full net baseline peaks at 250 immediately after entries and 318 after settlement transitions; outcome revelation is sometimes delayed relative to other ticket settlements. The replay now logs these transitions explicitly. Entry gating alone therefore does not prove continuously safe inventory, and this is not a production-certified risk engine.

### Quoting at the actual hurdle: final follow-up

Lower-edge admission at observed prices is not actually lowering quotes. To check the concession itself, a further replay quotes at fair plus the chosen net hurdle and recomputed 0.035 maker fee, rounded up to a 0.1c price grid. It retains original contract quantities and permits a hypothetical fill only when that quote does not exceed the historical executed premium. Cash, fees, risk, marks, and settlement PnL are recomputed at the new quote. Discount certification uses the discounted quote's own risk, not the more favorable original price.

| Repriced quote policy | Full-period PnL | Later-period PnL |
| --- | ---: | ---: |
| Flat 0.3c | $154.13 | $41.98 |
| 0.1c relief at 80% | $95.91 | $113.06 |
| 0.1c relief at 90% | $22.79 | $55.53 |
| Flat 0.1c, diagnostic | -$6.32 | $99.96 |

The qualitative conclusion survives repricing: later-period benefits, full-period underperformance at the main fee assumption. This is an explicit historical-price acceptance proxy, not observed RFQ acceptance: it does not identify new demand, queue priority, or budget-sized quantity changes. No inferred causal elasticity, collateral release, or automatic filter relaxation is claimed.

Artifacts: `inventory_relief.json`, `inventory_relief_fixture_constrained.json`, `inventory_relief_conditioned.json`, `inventory_fee_followup.json`, `inventory_repricing.json`, and their fill ledgers.

## 6. Same-game opportunity and naturally offsetting flow

Across the 14-day historical tape, same-game-containing tickets account for **53,670 of 93,952 (57.1%)** scoped 2–4-leg full-game pregame prints. This is executed-tape evidence, not the earlier RFQ-only share. It excludes player props, longer combos, live trades, and non-target fixtures.

For **47,929** single-game YES-taker prints across ten fixtures, aggregate actual observed contract quantities into hypothetical seller portfolios. A scalar-safe linear-program upper bound uses only YES/NO complement relationships on identical native markets. It does not assume independent same-game legs or unverified score relationships. If the bound is loose, it withholds offset credit rather than claiming a false hedge.

Pooled certified gross-payout reduction is **37.2%** at the full sample, with fixture-level reductions around 29–45%. This establishes that some historical flow really can offset under the stated native-market payoff assumptions. It does not establish accurate combo fair values or expected profit.

Two follow-ups matter:

- At the first quarter of chronological prints, pooled reduction is already 38.1%; the full sample is 37.2%. Six of ten fixtures improve individually, four do not. More volume does not monotonically improve diversification.
- Restricting the hypothetical fills to tickets whose legs are all YES reduces the certified offset to **zero** under these constraints. Flow selection matters at least as much as aggregate volume.

Gross cash remains fully reserved. A portfolio payout bound is not exchange collateral credit. No same-game independent-product pricing backtest is presented: that would supply misleading precision without a calibrated joint model. The completed study establishes opportunity size and conservative offset potential; it does not support lifting the live same-game guard.

## What to retain for daily research

Retain kickoff time, prior-hour/day-to-date contracts, final-day volume labels for retrospective reports, first-start volume-clock estimates with forecast errors, exact portfolio risk changes, and separate price/fee/hedge-cost components. Keep source age, missing-horizon rates, and sample counts beside every aggregate. Keep round-spend as a candidate feature without a discount policy.

The clearest practical finding is a useful MLB pacing curve. The weakest deployment cases are routine aggressive leg hedging at 0.3c and a universal 0.1c inventory-relief rule. Same-game flow is worth a joint-pricing development effort, but its size should not substitute for risk or execution evidence.

## Reproduction and verification

Run the offline pipeline from the repository root:

```sh
.venv/bin/python scripts/run_research_program.py --out runs/research_program_20260910
```

The pipeline requires the retained historical archives and installed project dependencies; it does not download new market data or change live settings. Optional browser QA is a separate command, because it requires local Chrome permissions:

```sh
.venv/bin/python scripts/verify_research_atlas.py --out runs/research_program_20260910
.venv/bin/python scripts/audit_research_program.py --out runs/research_program_20260910
```

The 20 plots were rendered at 736px and 320px widths, checked for missing/invalid paths and horizontal overflow, and their exact-value disclosures exercised. The standalone wrapper was also rendered. Unit tests cover leg orientation, source-time guards, simultaneous-print volume exclusion, scenario offsets, outcome revelation, settlement cash recycling, hedge derivatives, and forecast-error denominators. The final audit independently checks result identities, selected-fill edge rules, cap compliance at entry, cash/PnL reconciliation, and input/output hashes. Details and evidence are retained in `audit.json`, `visual_qa.json`, and `reproducibility_manifest.json`.
