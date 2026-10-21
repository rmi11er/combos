# July25 margin and capacity review

All48entry-summary partitions reconcile to the same58,458print cohort and−$895,679.84sell-all result. All32risk outputs report independent integer-ledger reconciliation, and their four baseline portfolios match the entry sweep. Source/input hashes were rechecked. This review verifies retained summaries and audit flags, not a second full-ledger execution.

## Unlimited selection by minimum edge

Values are net dollars after archived scenario fees. The hurdle selects observed prints; it is not a new quote charged to customers or measured acceptance probability.

| Hurdle | Kalshi | Equal blend | PM75 | Polymarket |
|---|---:|---:|---:|---:|
| 0c/combo | 235 | 72,833 | 81,616 | 73,855 |
| 0.1c/combo | 9,820 | 30,908 | 77,946 | 84,701 |
| 0.3c/combo | 5,048 | −6,097 | −13,500 | 26,400 |
| 0.5c/combo | 2,935 | −2,464 | −10,001 | −15,177 |
| 0.3c/leg | 733 | 855 | 250 | −1,281 |

The blends lose at0.3c/combo but win at lower hurdles; Polymarket changes sign at0.5c. This nonmonotonic behavior could reflect selection and outcome concentration, so it must be evaluated across the pooled July sample before freezing any parameter. Prior losing days at low hurdles remain in the sample. Never equate zero required estimated edge with selling all prints: the latter also admits negative estimated edge and loses heavily here.

## Risk at the fixed0.3c/combo hurdle

| Scenario | Kalshi net / peak cash | Equal net / peak cash | PM75 net / peak cash | PM net / peak cash |
|---|---:|---:|---:|---:|
| Original baseline | −8 /679 | −282 /613 | −244 /878 | −286 /1,246 |
| Balanced1,000 | −658 /4,006 | −1,384 /4,988 | −1,141 /7,998 | −540 /9,759 |
| Capital only | +678 /9,332 | −4,820 /10,509 | −6,092 /11,097 | −7,179 /11,183 |

Higher capacity worsens every model in the balanced1,000case. Removing concentration limits leaves only Kalshi profitable. Cash may exceed the initial$10k in the capital-only simulation because actual-settlement profits can be reused; eventual P&L attribution at trade time is not the spendable cash balance. These paths do not justify scaling until full-sample chronological replay and concentration tests support it. No live limits changed.

Priority remains a joint study of margin, size and event/underlying exposure, including partial sizing where feasible. Optimizing a threshold on unlimited results and then applying unrelated risk caps can produce a materially different selected portfolio. These remain exchange-only public-print counterfactuals; Pinnacle availability, historical fee applicability and actual quote capture are separate unresolved questions.

[Verification](../runs/morning_research_20260908/july25_entry_risk_review/verification.json) · [Entry results](../runs/mlb_historical_20260907/dated_fee_primary/2026-07-25/entry_sweep/summary.json) · [Risk results](../runs/mlb_historical_20260907/dated_fee_primary/2026-07-25/risk_capacity/summary.json)
