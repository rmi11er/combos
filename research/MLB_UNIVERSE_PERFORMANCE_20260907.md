# MLB public-print seller benchmark

The complete September 5 census has **262,584 YES-taker MLB combo prints**.
Selling every one at its observed price would have produced **+$1,642,760.86**
on known settlements after modeled maker fees. Even assigning every unresolved
combo its worst seller outcome leaves **+$1,598,261.41**; assigning every one its
best outcome produces **+$1,648,847.15**. This positive reference therefore does
not depend on the 181 unknown outcomes resolving favorably.

This is an unlimited observed-price counterfactual, not an attainable RFQ fill
rate or a $10,000 portfolio return. It benchmarks whether a model selects a
better or worse subset of the available public print prices. It does not infer
what actual market makers held, hedged or paid in individualized fees.

![Complete-day MLB seller benchmark](../runs/mlb_historical_20260907/universe_report/census_sep5.png)

| September 5 cut | YES-taker prints | Known settlement net P&L |
|---|---:|---:|
| 2 legs | 50,778 | +$353,385 |
| 3 legs | 41,622 | +$302,488 |
| 4 legs | 28,699 | +$164,079 |
| 5+ legs | 141,485 | +$822,809 |
| Distinct games | 199,923 | +$1,682,221 |
| Contains same-game legs | 62,661 | −$39,460 |
| Full-game moneyline/spread/total only | 154,453 | +$1,390,540 |
| Before earliest native scheduled start | 154,045 | +$812,351 |
| After earliest native scheduled start | 108,539 | +$830,410 |
| Observed YES premium ≤$50 | 240,095 | +$904,454 |
| Observed YES premium >$50 | 22,489 | +$738,307 |

Each dimension partitions the same universe; rows across dimensions must not be
added together. Cut-level unknown positions and bounds are included in the
machine-readable summary. Pregame is a scheduled-clock proxy, not proof of
historically versioned first pitch. An observed print's premium is not the
parent RFQ ticket premium. Full-game core is explicitly defined; unreviewed
families are not silently called no-prop or player props.

The all-print volumes are **$8,303,769.83 YES premium** and **$272,856,823.29
payout face notional**. Face is contract quantity, not winnings. Modeled maker
fees total **$203,925.56** across all prints; the known-outcome P&L deducts fees
on those known-outcome prints. The unknown-outcome bounds include all remaining
fees, so unresolved positions are not treated as fee-free or risk-free.

## Concentration

The Milwaukee–Cincinnati fixture appears in **127,309 prints**, and those
prints collectively contribute **+$1,032,921**. Excluding every combo involving
that fixture leaves **+$609,840** known P&L. This is strong concentration even
though the reference remains positive after removing that game.

The ten largest profitable combo tickers contribute **+$330,761**, about 20% of
the total. Excluding the single largest profitable combo leaves **+$1,578,896**.
The ten largest individual profitable prints contribute **+$139,194**.

Fixture totals assign a print's whole P&L once to each distinct fixture it
contains, so they overlap and cannot be added. The leave-one-fixture-out figure
removes all associated prints once. Full top-15 profit/loss rankings by print,
combo and fixture are saved for inspection. Thousands of prints sharing a game
are not thousands of independent observations.

## Retained-week view

![Retained observations](../runs/mlb_historical_20260907/universe_report/retained_week.png)

The retained August 31–September 6 tape contains **293,752 YES-taker MLB prints**
with **+$1,822,268.55** known net P&L. Its 394 unknown positions bound full
outcomes between **+$1,547,085.03** and **+$1,839,810.92**.

Only September 5 is a complete day. The other six dates contain four fully
paginated 15-second sampled cells per hour. They are included at weight one.
The retained-week line accumulates observed prints only and does not estimate a
fully traded week. The shaded region marks the complete day.

Daily Sharpe and sample variance are **unavailable**, explicitly shown in the
legend: there is only one complete observed calendar day. Sampled days are not
filled with zeros or mixed into a complete-day return series. No annualization
or independent-print confidence interval is reported.

## Reuse and validation

`scripts/mlb_universe_report.py` creates both PNG/SVG figures, five-minute
right-labeled cumulative curves, a fee/settlement ledger, daily observed totals,
cut-level outcome bounds and concentration evidence. Eventual official
settlement P&L is attributed to the original trade time; chart bins are display
aggregation only. Raw timestamps remain in the ledger. No capital release,
fill, fair value or execution-selection assumptions are added by this report.

Artifacts live under `runs/mlb_historical_20260907/universe_report/`. The report
manifest includes the source cohort and script hashes. Reproduce with:

```sh
.venv/bin/python scripts/mlb_universe_report.py
```

Ten focused tests across the new MLB acquisition/cohort/report tooling cover
payoff bounds and fee inclusion, concentration overlap, schedule identity,
unknown-family classification, complete pagination and historical routing.
Both final plot layouts were visually inspected. These are the overall-universe
benchmarks for the separate constrained/unconstrained model-selection report;
Pinnacle's missing baseball entitlement remains a source-coverage limitation,
not a zero-edge model result.
