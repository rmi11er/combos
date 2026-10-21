# NFL January 5–18 full-liquidation capital-hours sensitivity

All 64 portfolios have sufficient retained actual settlement timestamps and known outcomes to close their cash-occupancy denominators. This separate sensitivity keeps **the original 336-hour window primary**, stops all new trades at the existing January 18 cutoff, and carries only previously accepted positions until their actual settlement. No repricing, new allocation or changed accept/reject decisions occurs.

Each portfolio's exact NO cash is integrated in two independent ways: summing each fill's cost × its holding duration, and sweeping timestamped cash-in/cash-out events. The active-window integral also reconciles against the existing 336-hour workflow. All fills settle, final event-sweep exposure is zero, and P&L matches the original ledger. The computation uses 50-digit Decimal precision; original float display comparisons use the existing tolerance.

The longest tail is **2.29684 hours**, ending 2026-01-19T02:17:48.615473-06:00. Thus the earlier withheld ratios needed a short real settlement tail, not an unknown assumed future. No missing timestamp or outcome exists in any portfolio.

## .035 maker-fee scenario

Efficiency units are net P&L dollars per $1,000 committed-dollar-hours. These are descriptive occupied-cash efficiencies, not annualized yields, expected future returns or RFQ acceptance forecasts.

| Regime/model | Extra hours | Active average cash | Full-horizon average cash | Tail dollar-hours | Full-liquidation efficiency |
|---|---:|---:|---:|---:|---:|
| funded_selection/exchange_blend_equal | 0.00000 | $71.06 | $71.06 | 0.00 | 1.56564 |
| funded_selection/exchange_blend_pm75 | 1.36415 | $88.05 | $87.91 | 70.99 | -0.90140 |
| funded_selection/kalshi | 1.54754 | $86.84 | $86.62 | 60.21 | -1.00559 |
| funded_selection/polymarket | 1.54754 | $103.49 | $103.32 | 102.09 | -2.11207 |
| funded_sell_all/exchange_blend_equal | 2.29684 | $135.14 | $134.26 | 11.01 | -0.84374 |
| funded_sell_all/exchange_blend_pm75 | 2.29684 | $135.14 | $134.26 | 11.01 | -0.84374 |
| funded_sell_all/kalshi | 2.29684 | $135.14 | $134.26 | 11.01 | -0.84374 |
| funded_sell_all/polymarket | 2.29684 | $135.14 | $134.26 | 11.01 | -0.84374 |
| unlimited_selection/exchange_blend_equal | 2.29684 | $19,954.92 | $19,827.03 | 2,570.58 | 6.98433 |
| unlimited_selection/exchange_blend_pm75 | 2.29684 | $24,639.84 | $24,496.76 | 8,191.33 | 5.89291 |
| unlimited_selection/kalshi | 2.29684 | $18,602.84 | $18,477.66 | 381.30 | 10.03840 |
| unlimited_selection/polymarket | 2.29684 | $35,581.01 | $35,393.42 | 18,263.07 | 3.63546 |
| unlimited_sell_all/exchange_blend_equal | 2.29684 | $348,796.86 | $347,847.78 | 480,059.87 | -2.55184 |
| unlimited_sell_all/exchange_blend_pm75 | 2.29684 | $348,796.86 | $347,847.78 | 480,059.87 | -2.55184 |
| unlimited_sell_all/kalshi | 2.29684 | $348,796.86 | $347,847.78 | 480,059.87 | -2.55184 |
| unlimited_sell_all/polymarket | 2.29684 | $348,796.86 | $347,847.78 | 480,059.87 | -2.55184 |

The full-horizon average divides occupied-dollar-hours by the original 336 hours plus any required liquidation tail. For portfolios already flat at cutoff it keeps 336 hours; it does not shorten the denominator to their earlier last fill or remove idle periods. The full-liquidation efficiency divides the unchanged eventual P&L by all actual occupied-dollar-hours, including the tail. It is therefore now available for every portfolio rather than dropping terminal positions.

The four sell-all model labels duplicate identical accepted portfolios and must not be added together. Historical fee and payoff assumptions remain unverified replay scenarios. Full liquidation changes only the denominator's observation horizon, not risk, fair values, fill quantities, P&L or the nine-bucket/$450 loose structural ceiling discussed in the primary report.

## Reproducible evidence

`runs/morning_research_20260908/nfl_capital_hours_jan5_18_liquidation/measure.py` is a separate offline workflow. `verification.json` contains all 64 per-fee/model/regime measurements, input hashes, active/tail/full dollar-hours, end timestamps, boundary cash, both averages and efficiencies. All source ledgers retain their hashes. Existing helpers and primary outputs were not modified. No provider calls, new trades, August data or surviving background jobs.
