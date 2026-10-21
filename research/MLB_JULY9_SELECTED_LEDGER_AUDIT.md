# July 9 MLB common-model selected-ledger audit

All eight portfolios pass the accounting audit. Every unlimited model selects profitable prints from a losing common universe, with Polymarket reporting the largest profit. However, **July 9 NYY–TB drives both PM's selected profit and its paired Brier advantage**: removing that fixture reverses both. This mirrors July 5's concentrated PM advantage, while July 7 favored Kalshi.

## Completion and independent verification

Cohort, replay and common report were certified complete/exit 0 before report reads. All **14 recorded completion hashes** matched. Audited every decision across four models and funded/unlimited regimes: **35,643 common prints per model; 285,144 decisions**. Native joins check YES-taker direction, quantities, prices, archived maker fees and settlements. All prints are 2–4 legs, pregame under the retained schedule proxy. July 9 is the trade date, not necessarily each fixture date.

The hurdle is net point edge ≥quantity×$0.003: **0.3c per combo contract**, not per leg. Unlimited decisions match the threshold/quote guard. Selected fills uniquely match accepted decisions with identical economics and timestamps. Fees are deducted once in net P&L and separately once in model edge, not twice in either. Selected/rejected totals reconcile exactly to the common universe.

Funded checks satisfy recorded available cash and risk buckets; this is not a second chronological risk-engine replay. The known conservative float/cash-ceiling artifact recurs in **71 of 307 funded accepted records**, reserving $0.0001 extra each ($0.0071 across separate portfolios). It cannot explain the profit differences. No frozen code or pricing model was changed.

## Results

| Model | Funded fills | Funded net | Unlimited fills | Unlimited net | Unlimited model edge |
|---|---:|---:|---:|---:|---:|
| Kalshi | 62 | +$68.22 | 197 | +$13,485.26 | $512.80 |
| Equal blend | 67 | −$35.79 | 292 | +$11,057.52 | $748.11 |
| PM75 | 80 | +$33.17 | 664 | +$24,219.66 | $1,546.40 |
| Polymarket | 98 | +$35.07 | 1,870 | +$64,769.27 | $3,737.76 |

Selling every print in the common intersection loses **$800,774.48**. This is a narrower denominator than the separately audited broad native 275,489-YES-print benchmark (~−$1.576m). These are observed-price, full-size counterfactual fills, not demonstrated RFQ execution. Pinnacle is absent; historical fee applicability remains an explicit scenario assumption.

## Fixture omissions

Removing July 9 NYY–TB, the largest positive fixture membership for each unlimited selection, leaves:

| Model | Net after omission |
|---|---:|
| Kalshi | +$3,911.11 |
| Equal blend | +$397.40 |
| PM75 | −$6,987.66 |
| Polymarket | −$3,837.77 |

These omissions remove already accepted trades without reallocating capacity or admitting replacements. Memberships overlap and cannot be summed. Native clock-based fixture keys are inherited unchanged: root's broader native audit identified CHC–BAL clock aliases affecting 193 structure classifications. This review does not claim those aliases were repaired; robust concentration research should also consolidate verified same-game aliases without repricing or conflating distinct games. The dominant NYY–TB omission above is unaffected by that separate CHC–BAL caveat.

## Paired calibration and disagreement

Identical native prints/outcomes/quantities underpin the scores; lower Brier is better.

| Model | Equal-print Brier | Quantity-weighted Brier | Weighted fair minus outcome |
|---|---:|---:|---:|
| Kalshi | 0.21944395 | 0.18417471 | −0.08829651 |
| Equal blend | 0.21931870 | 0.18406334 | −0.08902937 |
| PM75 | 0.21926151 | 0.18401248 | −0.08939417 |
| Polymarket | 0.21920790 | 0.18396480 | −0.08975788 |

PM−Kalshi quantity-weighted Brier is **−0.00020991**, favoring PM. It stays negative in 44 of 45 retained-key omissions; deleting NYY–TB changes it to **+0.00012829**, favoring Kalshi. The full range is [−0.00044688,+0.00012829]. These overlapping fixture influence ranges are not confidence intervals; prints are not independent observations.

| Selection subset | Prints | Seller net |
|---|---:|---:|
| Both | 154 | +$7,704.58 |
| Kalshi only | 43 | +$5,780.68 |
| PM only | 1,716 | +$57,064.68 |
| Neither | 33,730 | −$871,324.43 |

PM-only selections make substantial money on July 9, reversing July 7's −$18,259.99 PM-only loss. Most July 9 profit exceeds modeled compensation by a wide margin; e.g. PM modeled edge is $3,737.76 versus realized $64,769.27. Favorable settlement residuals, not demonstrated extra quote charges, explain the difference.

## Research implication and evidence

Retain source-weight and hurdle comparisons across the larger development set and purged held-out fixtures. Neither July 9's PM advantage nor July 7's Kalshi advantage should select the production model alone. Consolidate verified fixture aliases in a separate sensitivity view and preserve original ledger accounting. Do not interpret increased observed participation as proven quote capture or independently repeatable edge.

[Ledger verification](../runs/morning_research_20260908/july9_selected_audit/verification.json) · [Disagreement](../runs/morning_research_20260908/july9_selected_audit/disagreement.json) · [Four-model calibration](../runs/morning_research_20260908/july9_selected_audit/four_model_calibration.json) · [Certified hashes](../runs/morning_research_20260908/july9_selected_audit/certified_hashes.json). Audit scripts are retained alongside the evidence. No partial reports, providers, August outcomes or frozen source edits were used.
