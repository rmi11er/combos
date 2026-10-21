# July 7 MLB common-model selected-ledger audit

All eight portfolios pass the independent accounting audit. July 7 favors Kalshi over Polymarket on both paired calibration and observed-price selection. PM's additional selections lose money, reversing July 5's overall favorable PM result. This remains development evidence, not a production source-weight decision.

## Completed artifacts and checks

The July 7 cohort, replay and common report were complete with exit code 0 before reading report artifacts. All **14 recorded completion hashes** matched disk. Full checks cover **20,386 common prints per model**, four models and two regimes: **163,088 decisions**, without sampling.

Native joins verify YES-taker direction, quantity, traded price, retained maker fee and settlement value. All prints are 2–4 legs and pregame under the retained schedule proxy. July 7 is the trade date; some underlying fixtures occur later. Selection requires `q×(YES price−fair)−fee >= q×.003`, **0.3 cents per combo contract**, not per leg. Unlimited decisions match this threshold and quote guards. Selected fill IDs uniquely match accepted decisions; terms, timestamps, attributed P&L and fees reconcile. Selected plus rejected totals equal the common universe. No fee is charged twice in P&L or edge.

Funded risk checks obey their stored cash and bucket limits; this validates retained checks, not a second chronological risk engine. The known conservative float/cash-ceiling effect appears in **27 of 173 funded accepted records**: each reserves $0.0001 extra, $0.0027 across separate portfolios. It cannot explain the P&L differences. No frozen code was changed.

## Portfolio results

| Model | Funded fills | Funded net | Unlimited fills | Unlimited net | Unlimited model edge |
|---|---:|---:|---:|---:|---:|
| Kalshi | 32 | +$69.27 | 64 | +$2,535.18 | $301.87 |
| Equal blend | 33 | −$242.16 | 72 | +$1,304.94 | $294.26 |
| PM75 | 46 | −$233.62 | 149 | −$2,958.69 | $372.75 |
| Polymarket | 62 | −$200.19 | 573 | −$16,907.64 | $1,117.93 |

Selling every print in this same common intersection loses **$313,202.35**. That denominator differs from the broad native all-family benchmark. These are hypothetical full fills at observed prices, not measured RFQ acceptance. Pinnacle is absent and historical maker-fee applicability remains an explicit scenario assumption.

## Fixture concentration

Removing the largest positive fixture membership from unlimited accepted fills produces:

| Model | Fixture removed | Net after omission |
|---|---|---:|
| Kalshi | July 8 LAA–TEX | +$243.07 |
| Equal blend | July 8 LAA–TEX | −$765.38 |
| PM75 | July 8 LAA–TEX | −$5,038.11 |
| Polymarket | July 8 SEA–MIA | −$22,208.68 |

Kalshi's selected profit survives any one positive-fixture omission, though only 64 unlimited prints qualify. Equal blend does not. Omitting memberships removes already accepted trades without admitting replacements, and overlapping memberships cannot be added. Funded Kalshi retains +$28.27 after its largest positive fixture omission; all three other funded portfolios were already negative.

## Paired calibration and disagreement

Identical prints, quantities and native outcomes underpin every model score; lower Brier is better.

| Model | Equal-print Brier | Quantity-weighted Brier | Weighted fair minus outcome |
|---|---:|---:|---:|
| Kalshi | 0.20909193 | 0.17773634 | −0.06170226 |
| Equal blend | 0.20994011 | 0.17816176 | −0.06220686 |
| PM75 | 0.21036818 | 0.17837783 | −0.06245893 |
| Polymarket | 0.21079889 | 0.17859614 | −0.06271086 |

PM−Kalshi quantity-weighted Brier is **+0.00085980**, favoring Kalshi. It remains positive in **all 43 single-fixture omissions**, ranging **+0.00025726 to +0.00115383**. July 5 instead favored PM overall but reversed after deleting SD–LAD. July 7 therefore provides a useful contrary observation to a universal PM-sharpness heuristic. Shared fixtures/repeated combos mean omission ranges are influence diagnostics, not confidence intervals or independent tests.

| Selection subset | Prints | Net seller P&L |
|---|---:|---:|
| Both K and PM | 49 | +$1,352.35 |
| Kalshi only | 15 | +$1,182.83 |
| PM only | 524 | −$18,259.99 |
| Neither | 19,798 | −$297,477.54 |

Positive modeled edge does not ensure realized profit: PM's selected expected compensation is +$1,117.93 yet realized net is −$16,907.64. Fair-error residuals and shared outcomes dominate this difference. Do not infer a new risk limit or source weight from one date; preserve fixed models, compare across development dates, and validate on fixture-purged held-out data.

Evidence: [verification](../runs/morning_research_20260908/july7_selected_audit/verification.json), [paired disagreement](../runs/morning_research_20260908/july7_selected_audit/disagreement.json), [four-model calibration](../runs/morning_research_20260908/july7_selected_audit/four_model_calibration.json), [certified hashes](../runs/morning_research_20260908/july7_selected_audit/certified_hashes.json). Audit scripts are retained beside these files. No provider requests, August outcomes, raw-data mutations or frozen source changes were involved.
