# Volume-conditioned markouts and inventory-relief pricing

Status: experiment specification; no runtime changes or completed backtest claimed.

## Questions

1. Does time to kickoff retain explanatory power for seller-side markouts after controlling for observable volume, spread, premium, leg count, and quote freshness?
2. When fixture inventory is constrained, does admitting genuinely risk-reducing trades at a 0.10-cent net edge improve portfolio results versus a flat 0.30-cent hurdle?

Round-spend inference remains a retained candidate feature, with discount research tabled.

## Volume cuts

Report both ex-post full-day volume buckets (descriptive only) and causal activity buckets available at each decision. Use America/Chicago calendar days. Full-day labels must never determine historical admission decisions.

Keep contracts, principal dollars, and print counts separate. Primary causal activity measures are day-to-date contracts and trailing-60-minute contracts strictly before the decision. Exclude the current print and process simultaneous timestamps as a batch so tie ordering cannot leak volume. Compare day-to-date activity with earlier days at the same clock time, not with their full-day totals. Fit low/medium/high cutoffs on an earlier training period, freeze them for evaluation, and explicitly label insufficient history.

Calculate sports-combo tape activity and fixture-linked combo activity separately, deduplicating each print within each fixture. Where complete leg-trade data exist, add single-leg activity as a distinct measure; do not substitute candle volume or quote updates without labeling it. Missing capture periods are unknown volume, not zero; sampled retained dates cannot establish full-month volume quantiles. Report actual source coverage with each bucket.

Cross time-to-first-kickoff with volume bucket, then control for premium, leg count, spread, freshness, and pregame/live status. Kickoff is not assumed to be merely a volume proxy: information arrivals and settlement proximity may matter independently. Cluster uncertainty by slate/date rather than treating overlapping combos as independent.

Markout horizons: 1, 5, 15, and 60 minutes, plus the last valid pre-first-kickoff reference. Report seller net quote-minus-future-fair, fair-price movement, and markout availability separately. Decompose changing blended fair into price and weight effects using the existing attribution workflow. Freeze entry weights for an additional price-only sensitivity; a missing constituent stays missing rather than silently reweighting. Label right-censoring, stale references, and horizon crossings into live play. Candidate marks are not observed fills.

## Inventory experiment

Pricing convention: 0.10 cents = $0.001 per combo contract, net of modeled fees. This reduces only the discretionary edge hurdle; it does not waive freshness, uncertainty, mapping, cash, execution, or other safety guards. Do not alter the calibrated fair solely to absorb inventory: log fair, inventory concession, and final quote separately.

Use four controls to distinguish risk accounting from price selection:

| Arm | Risk treatment | Edge hurdle |
| --- | --- | --- |
| A | Existing gross limits | Flat 0.30c |
| B | Validated portfolio-aware fixture risk; gross cash unchanged | Flat 0.30c |
| C | Same as B | 0.10c only on certified reducing size when constrained; otherwise 0.30c |
| D | Same as B | Flat 0.10c, diagnostic only |

Run C with prespecified 80%, 90%, and 100% fixture-utilization triggers. Do not select the winning threshold and call the same sample a holdout. Include a 0.20c relief-hurdle sensitivity.

A closing trade must be evaluated against the inventory held immediately before that decision. An opposite team in one leg is not sufficient. A candidate can offset that fixture while adding a correlated liability through its other legs.

For fully mapped binary, distinct-fixture moneylines, enumerate feasible joint outcomes for tractable connected inventory components. Compute net portfolio scenario losses including trade cash flows and fees. Define fixture sensitivity as the maximum absolute change in portfolio loss when flipping that fixture while holding all other fixture outcomes fixed. A relief candidate must strictly reduce sensitivity of a constrained fixture, not increase positive worst-case portfolio loss, and keep all other fixture and instrument limits satisfied. Preserve gross cash reservations: economic offsets do not establish exchange collateral relief.

Use exact checks where tractable and reject relief certification where scenario enumeration or mapping is incomplete. A decrease in two separately loose risk upper bounds does not certify a decrease in true risk. Same-game structures require a separate validated feasible-outcome model and are excluded initially.

Determine the maximum certified reducing size before a trade crosses through neutrality or violates another limit. The 0.10c concession applies only to that size. Treat larger tickets as full-size reject/normal-price in the primary public-print replay; explicitly separate any resized-ticket experiment because original fees, acceptance, and partial-fill assumptions no longer transfer automatically. Recompute after each simulated fill or settlement, and include simultaneous outstanding reservations before any forward application.

## Outcomes and interpretation

Report settlement PnL, price-only markouts, accepted net edge, gross cash, maximum scenario loss, constrained-fixture sensitivity, time above utilization thresholds, and the count/edge/PnL of subsequently admitted ordinary trades. Compare C to B, not just A. An apparent benefit from changing risk accounting must not be credited to cheaper pricing.

Attribute the direct PnL of relief trades separately from downstream allocation effects. Use a paired chronological replay on the same opportunity stream, retaining rejected opportunities. Carry inventory across days and settle causally; future outcomes must not determine admission. Use date/slate-clustered uncertainty and later-period replication.

Historical prints can test whether lower-edge offsetting opportunities existed and whether accepting them would have improved portfolio allocation at observed prices. They cannot establish that quoting cheaper creates additional demand. A quote-repricing replay must recalculate premium, fees, risk, and budget-sized quantities, with acceptance explicitly scenario-based until observed exposure/response data exist.

## Inspection findings and implementation order

`analysis/offsetting_allocation_backtest.py` currently aggregates opposing moneyline liability using the larger side. Adding to the smaller side can leave this usage unchanged; it does not necessarily release headroom. Gross cash is retained. This is not a certified net-loss or marginal-risk-reduction gate and should not be reused as one without additional validation.

`research/NFL_MARKOUT_PRICE_WEIGHT_ATTRIBUTION_20260909.md` reports that all 2,309 observed marks in three short audited captures had zero venue-price contribution. These captures alone cannot establish price anticipation or volume-conditioned adverse selection.

Next implementation steps: audit historical timestamp/volume coverage; produce causal and descriptive volume labels; attach price-versus-weight markouts; validate exact small-portfolio inventory examples; then run the paired NFL inventory replay. No live configuration or inventory ledger is modified by this specification.
