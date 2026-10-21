# July 31 selected-cohort audit

All eight model/funding portfolios reconcile to native trade quantity, YES price, settlement and retained maker fees. Selected plus rejected results equal the common universe; fees are deducted once, and the hurdle is 0.3c per combo contract. All 207,232 model-point decisions reconstruct from the recorded source intervals. The raw-source audit matches 164,367 Kalshi states and 157,631 Polymarket as-of states across 777 raw files, with zero PM rounding discrepancies. Root rechecked source/input hashes and inspected both portfolio PNGs.

The common cohort contains 51,808 prints; selling every matched print has net P&L of $814,904.09 under the archived fee scenario. This is a public-print counterfactual, not achievable volume or RFQ fills.

| Model | Unlimited fills | Unlimited net | Minimum net after one fixture omission | Funded fills | Funded net | Funded peak cash |
|---|---:|---:|---:|---:|---:|---:|
| Kalshi | 49 | $4,584.81 | $2,276.73 | 22 | $20.97 | $426.28 |
| Equal blend | 71 | $31,164.83 | $1,715.90 | 22 | −$60.28 | $589.13 |
| PM75 | 112 | $32,025.51 | $2,479.17 | 32 | −$20.70 | $737.35 |
| Polymarket | 360 | $31,492.24 | −$3,092.53 | 68 | −$69.75 | $1,140.30 |

Funded starts with $10,000 and retains the existing $100 underlying/combo and $250 fixture caps. All four funded models have a negative minimum fixture-omission result. Unlimited PM/blend curves contain a substantial profit jump around 16:00 Chicago; this is a concentration feature, not a smoothly accruing model edge. Fixture omission deletes selected prints without reallocating capacity.

Quantity-weighted Brier scores are K 0.10275005, equal 0.10271700, PM75 0.10270331, PM 0.10269148. PM is slightly better on this quantity-weighted whole cohort; equal-print weighting instead slightly favors K. Neither establishes stable source superiority, and this audit does not yet calculate matched calibration fixture omissions.

With July 31 priced, the 15 priced July development dates total 467,583 common prints. July 13 remains an explicit identity gap. The complete continuous funded July replay is still pending; these daily results must not be summed into a funded monthly return.

Pinnacle is absent. These checks do not independently certify historical fee effective dates, exceptional cross-venue payoff parity, real publication latency or executable PM midpoint/depth. The audited point-entry model differs from the stressed live shadow quote basis.

[Native accounting verification](../runs/morning_research_20260908/july31_selected_audit/verification.json) · [Root verification](../runs/morning_research_20260908/july31_selected_audit/root_verification.json) · [Fair reconstruction](../runs/morning_research_20260908/july31_selected_audit/fair_point_audit.json) · [Source reconstruction](../runs/morning_research_20260908/july31_selected_audit/raw_source_audit.json)
