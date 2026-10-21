# Combined three-source demand-refresh capture

The requested 120-second shadow capture terminated after 69.94 seconds because
Polymarket exhausted its two-reconnect recovery budget. The runtime exited 1;
the supervisor interrupted Pinnacle and successfully drained workers, archived
inputs and exported decisions. This is a failed-duration capture, not a completed
soak. Three Pinnacle snapshots were saved; provider usage was reconciled at 38
before the run. No exchange quotes or orders were submitted.

The complete saved census contains 28,564 RFQs. Of 588 mapped candidates, 256
(43.54%) had usable three-source scenario inputs: 132 two-leg, 76 three-leg and
48 four-leg. The earlier rotation capture priced 167/545 (30.64%). These captures
differ in RFQ flow, duration, recovery behavior and market state; the difference
is descriptive, not a controlled estimate of demand prioritization's effect.

The new sample contains 1,657 mapped leg occurrences: 333 Kalshi old-timestamp
failures, 212 PM old-timestamp failures and 138 PM not-observed failures. Reconnects
clear PM state, so feed-wide recovery sacrifices coverage on otherwise healthy
books. There were six full-depth mismatch tokens, each seen once, plus ten
intervening-update verification rejections. Recovery stopped on its third mismatch
batch, despite no token recurring across the capture.

All 256 priced RFQs use the captured zero maker-fee series. Six RFQs had a published
watch state; none had a published block/cooldown. Across the three reserve policies,
all 768 rows have quotes and canonical risk identities. At point+0.3c/combo, original
caps admit 120 RFQs under no-fill 3s expiry, with $331 peak holds. $1k each admits
210, peak $1,972; $2k each admits 235, peak $3,172. Under all-admitted-fill retention,
those counts are 27/65/89 and peak holds $591/$3,487/$6,727. These are capacity
scenarios, not fills, profits or optimal limits. Standard workflow validation ran;
this capture has not yet received the previous capture's independent full-row audit.

Next prioritize per-token invalidation and recovery so isolated depth mismatches
cannot repeatedly reset all 454 books. Preserve immediate invalidation, exact
snapshot comparison, bounded retries and fail-closed pricing for the affected
market. Do not merely increase the whole-feed reconnect budget. Then rerun a
sustained combined capture and measure all-leg coverage and decision latency.

Artifacts: runs/nfl_demand_three_source_capture_20260909,
runs/nfl_demand_rfq_scenarios_20260909, runs/nfl_demand_rfq_terms_20260909,
runs/nfl_demand_rfq_coverage_20260909, runs/nfl_demand_rfq_capacity_20260909.
Research payoff, Pinnacle units, account precision and sampled-grid assumptions
remain explicit; production pricing blocks are retained.
