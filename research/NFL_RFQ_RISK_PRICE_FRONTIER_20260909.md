# Full-size RFQ risk-price frontier

Correction to the suggested live partial-sizing direction: current official RFQ
documentation says quotes cover the full RFQ size. The create-quote endpoint
accepts prices but no maker-selected quantity. Historical partial-print sizing
remains a sensitivity study, not a directly deployable RFQ response mechanism.

Sources checked September 9, 2026:
- https://docs.kalshi.com/getting_started/rfqs
- https://docs.kalshi.com/api-reference/communications/create-quote

Implemented a fixed-portfolio-state diagnostic that finds the lowest allowable
YES ask satisfying both the existing edge floor and remaining cash/canonical
risk capacity. Fixed-contract RFQs retain their full size. Target-cost requests
retain their requested dollar cost and use the existing conservative quantity
bound. Exact single-fill fees and the conservative fragmentation cash bound are
recomputed for each price. No acceptance probability is assumed.

All 687 recorded baseline capacity admissions/rejections reproduce exactly.
For the 609 rejected candidates:

| Maximum additional ask | Candidates fitting their original remaining capacity |
|---|---:|
| 0.1 cents | 0 |
| 0.3 cents | 0 |
| 1 cent | 2 |
| 2 cents | 2 |
| 5 cents | 13 |
| 10 cents | 15 |

481 fit at some allowable price below one dollar, but this is not evidence that
those prices are competitive. 128 do not fit anywhere on the permitted grid
under the conservative quantity/fragmentation bounds. All have some positive
remaining capacity; insufficient room for the full RFQ is the issue.

Every rejection hits a fixture/event limit; 458 also hit underlying limits, 41
combo limits and three capital (overlapping). Each alternative uses its original
baseline portfolio state. These candidate counts cannot be added as a portfolio
of additional fills: taking one changes capacity available to later requests.

Interpretation: minor quote widening will not unlock much capacity in this
concentrated overnight slate. Lowering the edge charge is also not a capacity
solution: a cheaper YES sale increases seller liability, holding size fixed, and
can increase target-cost quantity. Event diversity, allocation across requests,
and justified risk-limit changes need evaluation on broader data. No risk limits
or quoting policy were changed from these results.

Four parameterized tests compare the binary risk search to exhaustive price/edge
enumeration for fixed and target-cost sizing, zero and nonzero fees, and different
available budgets. All pass. Existing quote fee/hold/quantity outputs reproduce
at the original price for every rejected row.

Workflow: scripts/rfq_risk_price_frontier.py.
Artifacts: runs/nfl_risk_price_frontier_20260909/{summary,rows}.json.
