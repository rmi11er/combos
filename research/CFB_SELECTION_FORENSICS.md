# Common-cohort blend selection forensics — September 7, 2026

The selected trades performed worse on this week, including after simple exposure controls. But **−$48k selected versus +$80k rejected is not a clean comparison of our pricing rule**. Nearly all the rejected profit comes from large tickets, and the rejected group has a different price and payoff distribution. Reversing the selection rule would not establish a profitable small-ticket strategy.

This analysis uses all **9,511** frozen common-cohort blend evaluations and their exact saved unlimited point-entry decisions. All rejected rows failed the **0.3-cent per-contract net-edge threshold**; none were rejected by the divergence guard. P&L uses official known combo settlements, including those reported after the trading window. Unknown outcomes remain excluded from realized-performance numerators and denominators.

| Group | Prints / known outcomes | Known net P&L | P&L / total NO cash committed | Mean individual-print NO-cash return |
|---|---:|---:|---:|---:|
| Selected, all sizes | 1,880 / 1,780 | −$48,128.06 | −19.82% | −32.74% |
| Rejected, all sizes | 7,631 / 7,488 | +$80,265.02 | +3.61% | −8.69% |
| Selected, YES premium ≤$50 | 1,601 / 1,512 | −$7,143.97 | −13.42% | −31.09% |
| Rejected, YES premium ≤$50 | 6,694 / 6,572 | −$2,973.31 | −0.28% | −9.17% |

NO cash is `q*(1-pYES)+maker_fee`. The fourth column weights prints by this cash amount; the final column gives every known-outcome print equal weight. Neither is a funded portfolio return or a Sharpe estimate.

## Large tickets and payoff mix explain much of the headline

The **937 rejected tickets above $50 YES premium** contribute **+$83,238.33**; the smaller rejected tickets lose money. Just **274 rejected tickets above $200** contribute **+$78,839.35**, approximately **98%** of the rejected group's net profit. Of these, 22 tickets above $1,000 contribute +$34,534.05. The 103 selected tickets above $200 contribute −$36,689.75. Large-print capacity is therefore central to both raw-dollar headlines.

Selected versus rejected median YES prices are **35.05 versus 23.60 cents**; median modeled probabilities are **33.67% versus 23.17%**. Median YES premiums are similar, **$9.77 versus $9.52**, but median quantities are **37.625 versus 68 contracts**, and median NO cash is **$25.04 versus $53.02**. Equal customer premium does not imply equal maker risk or equal payoff skew. Distributions for price, fair, size, premium, liability, hour, and leg count are exported in full.

Using a descriptive **$100 NO-cash exposure per known print**, scaling each print's P&L and fee linearly, both groups lose: selected −$58,273.62 and rejected −$65,064.77. The group totals differ in print count; the relevant comparable means are −32.74% and −8.69%. This deliberately changes the experiment, does not round new order quantities/fees, and does not simulate capital availability or fills.

## Concentration is substantial, but not one combo or one upset

The ten most profitable rejected combos contribute **+$61,701.19**, about 77% of rejected net profit. Removing the single largest leaves **+$71,420.53**. Removing every rejected trade involving the most profitable fixture, **Oklahoma State–Tulsa**, leaves **+$50,671.95**. Central Michigan–New Mexico and Boise State–Oregon each also appear in approximately $23.8k of rejected net profit. Fixture subsets overlap and their contributions must not be added.

The ten worst selected combos contribute **−$40,208.32**. Removing the worst single combo still leaves **−$38,844.92**. Removing all selected exposure to Wisconsin–Notre Dame, the most costly fixture, still leaves **−$29,201.33**. No single combo or fixture reverses the observed selection comparison.

Keeping only the **earliest observed print per combo across the whole common cohort** leaves selected **−$18,545.72** and rejected **+$44,526.11**. Under the ≤$50 scope, this becomes **−$3,852.73 versus +$3,410.21**. These are changed exposure experiments, with selection attached to the earliest print; subsequent quote changes and repeated demand are deliberately removed. The script also exports an explicitly separate earliest-print-within-selection-group calculation.

## Comparisons on overlapping observable strata

We formed cells by leg count, YES-price band, and YES-premium band, retaining only cells with at least five known selected and five known rejected prints. Each group's mean individual-print NO-cash return was then weighted by the same pooled cell counts.

| Scope and matching dimensions | Selected / rejected prints on overlap | Standardized selected / rejected mean |
|---|---:|---:|
| All sizes: legs + price + premium | 1,596 / 5,994 | −18.00% / −14.04% |
| All sizes: add trade day | 1,564 / 5,856 | −18.49% / −13.61% |
| ≤$50: legs + price + premium | 1,437 / 5,304 | −18.50% / −14.71% |
| ≤$50: add trade day | 1,415 / 5,190 | −19.38% / −14.38% |

The gap shrinks considerably from the unstandardized −32.74% versus −8.69%, but it does not disappear. This is **descriptive reweighting**, not causal identification: fixture mix, correlated outcomes, information timing, and within-band differences remain. The reduced overlap populations differ from the full cohort. Choosing strata after seeing results is also not a forward validation design.

As a related calibration diagnostic, quantity-weighted modeled versus realized YES probabilities are **42.45% versus 54.49%** for selected fills and **12.59% versus 9.32%** for rejected fills. In the ≤$50 groups they are **26.84% versus 37.14%** and **7.47% versus 7.64%**. Selection identifies a serious conditional underpricing symptom in this sample. Many tickets reuse the same outcomes, so these figures do not establish independent statistical significance or tell us whether the cause is a persistent pricing defect or this week's result pattern.

## Native evidence behind the largest rejected profits

We checked the top **20 accepted losses and 20 rejected profits**, retaining their full price contexts and native underlying definitions. All 40 had saved contexts; all 40 native binary leg products agreed with the official combo settlement. No sign, complement, or settlement mismatch was found in these checks.

- **+$4,797.26, Oklahoma State YES × Duke YES:** 8,054.12 contracts at 60.4 cents, modeled fair 61.745% and net expected edge about **−2.18 cents/contract**. Oklahoma State's native book was 82/83 cents, blended leg fair about 82.16%; its official outcome was NO. Duke settled YES. An eventual profitable rejection is consistent with an initially negative model edge when a favored leg loses; its outcome alone does not prove that quoting was favorable beforehand.
- **+$4,529.04 and +$3,623.23, Auburn −7.5 × Oregon −24.5:** two large prints at 24.4 cents against approximately 23.48-cent joint fair. Net modeled edge was approximately **+0.267 cents/contract**, just below the 0.3-cent gate. Both native spread legs settled NO. This is a threshold-sensitive missed winner, not evidence that every rejected trade had negative estimated edge.
- **+$4,487.59, Jacksonville State −21.5 × NO Virginia Tech −54.5:** 17,250 contracts at 26.7 cents, fair approximately 26.18 cents, but net edge about **−0.17 cents** after maker fees. Virginia Tech covered the spread, so the selected NO leg failed and the combo seller won. The complement is handled correctly.
- **+$4,477.64, Cincinnati game over 51.5 × Oklahoma State game over 58.5:** 18,695.15 contracts at 24.6 cents, modeled fair approximately 23.76 cents. Net edge about **+0.185 cents** fell below the gate; both totals settled NO.

The largest accepted loss remains **−$7,740.31** on Ole Miss YES × Notre Dame YES, with 22,123 contracts at 65.8 cents against approximately 63.35-cent modeled fair. Both legs settled YES. Full evidence includes raw state ages and source hashes. A long Pinnacle last-change age is not, by itself, proof of a feed outage; this audit does not assign losses to the 30-second delay without a contemporaneous quote comparison.

## What this supports next

The evidence supports investigating **conditional calibration where the combo price exceeds our estimated fair**, especially by probability, size, market type, and repeated fixture exposure. Test candidate corrections on held-out fixture/date clusters with predetermined sizing and realistic quote-capture assumptions. Keep rejected opportunities in shadow logs so we can distinguish threshold misses, model errors, and favorable realized surprises. Do not invert the rule or lower the threshold solely because rejected historical trades won.

Reproduce with `.venv/bin/python scripts/cfb_selection_forensics.py`. Artifacts in `runs/cfb_selection_research_20260907/forensics/` include `summary.json`, `distributions.csv`, `strata.csv`, full `unit_groups.csv`, `leave_one_out.csv`, `normalizations.csv`, `matched_strata.json`, `top_print_evidence.json.gz`, and an input/code hash manifest. No prices, shared pricing code, or live configuration were changed.
