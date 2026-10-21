# Full priced July source comparison

The 15 priced July development dates support the hypothesis that Polymarket supplies useful incremental information for MLB combos. On the identical 467,583 prints and 124,747,722.65 payout contracts, PM has a lower Brier score than K under both quantity and equal-print weighting. Pinnacle is absent, so this is not validation of the intended three-source fair.

| Model | Quantity-weighted Brier | Equal-print Brier |
|---|---:|---:|
| Kalshi | 0.13061091 | 0.14973273 |
| Equal blend | 0.13052627 | 0.14967941 |
| PM75 | 0.13048792 | 0.14965722 |
| Polymarket | 0.13045219 | 0.14963797 |

Lower is better. PM−K quantity-weighted Brier is approximately −0.00015872, a relative improvement of about 0.12%. Removing every print involving one canonical fixture preserves PM's advantage for all 392 fixture omissions; the difference ranges from −0.00020390 to −0.00011867. These overlapping deletions measure influence, not statistical significance, and do not substitute for date/block holdouts. Scores combine calibration and discrimination; they do not directly quantify executable trading profit.

Selling the entire matched cohort at observed prices has net P&L of $332,448.53 after archived modeled fees. Against point fair, aggregate modeled compensation is negative for every source model: K −$523,785.90, equal −$410,710.81, PM75 −$354,374.24 and PM −$298,171.25. Favorable realized settlement residuals account for the positive sell-all result. This is another reason not to translate a rising broad equity curve directly into expected edge.

The source comparison is consistent with the full-July point-selected results favoring PM, but those selections concern different trades and do not themselves rank forecast quality. The intended PM/Pinnacle agreement heuristic, liquidity weights and delayed-feed behavior still require corresponding data and validation. January NFL does not show the same source ordering and remains a separate model-development problem.

## Verification and next step

The streaming workflow checks identical economics and all four source models for every print, rejects duplicate model rows and duplicate print IDs across inputs, and verifies unchanged input hashes. Fifteen input hashes and the workflow hash were independently rechecked; the small fixture-omission test passes. July 13 is an unpriced gap and contributes no synthetic observations.

Preserve PM-heavy MLB pricing as a candidate hypothesis. Evaluate date-level stability, source-disagreement direction, margins/reserves and continuous funded performance before freezing the candidate and testing August. Do not promote 100% PM or a specific blend solely from this inspected development result. Historical PM point semantics, missing historical depth, fee applicability and exceptional payoff parity remain limitations inherited from the source data.

[Scores and all fixture omissions](../runs/morning_research_20260908/july_pooled_calibration/results.json) · [Verification](../runs/morning_research_20260908/july_pooled_calibration/verification.json) · [Reusable workflow](../scripts/pooled_source_calibration.py)

## Date stability

PM's quantity-weighted score is better on 11 of 15 individual dates; K is better on July 3, 7, 15 and 17. Removing any one date still leaves PM ahead: pooled PM−K Brier ranges from −0.00021491 to −0.00010225. Through July 25, excluding the final three observed dates, the difference remains −0.00012271; on those final three dates alone it is −0.00024286.

Thus the source-scoring advantage does not depend entirely on the late-July profit reversal in the broad universe. It is nevertheless small, not uniform across slates, and still measured on inspected development data. Date omissions are not fresh OOS, and shared fixtures/time-correlated flow remain relevant.

Each day's scores was recomputed from its full matched decision ledger. All daily counts reconcile to 467,583 common prints, all four weighted pooled scores reproduce, and a separate pooled-minus-day calculation reproduces each of the 15 date omissions. All input hashes were rechecked.

[Date results](../runs/morning_research_20260908/july_pooled_calibration/date_stability.json) · [Date verification](../runs/morning_research_20260908/july_pooled_calibration/date_stability_verification.json)
