# NFL January 5–18 capital-hours audit

All **16 replay ledgers / 64 model measurements** reconcile committed-cash curve integration with the independent sum of per-fill NO cash × elapsed holding hours. Reporting windows are 336 hours, including nights and idle periods. Existing ledgers and the workflow are unchanged.

The full-window common dataset has **nine canonical underlying moneyline risk buckets**, not six. Every eligible combo uses at least two distinct buckets. At $100 per underlying, a loose necessary upper bound on simultaneously committed cash is therefore **9 × $100 / 2 = $450**, only 4.5% of the $10k base. The earlier $300 six-bucket statement describes the shorter first-week window and is stale for the full window. $450 is not an achievable-capacity forecast: fixture timing, per-combo caps, existing positions and full-print quantities tighten it. These are dollar-risk caps, not a cap of 100 contracts in quantity.

The nine common moneyline fixtures exclude SF–SEA, whose exact paired pricing availability is not part of this common cohort. The complementary team outcomes share one canonical underlying risk bucket per fixture. Fixture caps of $250 cannot expand the tighter $100 underlying cap in this moneyline-only scope. Larger trade counts alone therefore cannot consume $10k under these constraints.

## Baseline .035 fee scenario

| Regime | Model | Average committed cash | Peak committed cash | Eventual P&L | Capital cycle complete? |
|---|---|---:|---:|---:|---|
| funded_selection | exchange_blend_equal | $71.06 | $118.02 | $37.38 | True |
| funded_selection | exchange_blend_pm75 | $88.05 | $174.50 | $-26.73 | False |
| funded_selection | kalshi | $86.84 | $139.07 | $-29.40 | False |
| funded_selection | polymarket | $103.49 | $208.57 | $-73.66 | False |
| funded_sell_all | exchange_blend_equal | $135.14 | $227.17 | $-38.32 | False |
| funded_sell_all | exchange_blend_pm75 | $135.14 | $227.17 | $-38.32 | False |
| funded_sell_all | kalshi | $135.14 | $227.17 | $-38.32 | False |
| funded_sell_all | polymarket | $135.14 | $227.17 | $-38.32 | False |
| unlimited_selection | exchange_blend_equal | $19,954.92 | $202,764.13 | $46,846.83 | False |
| unlimited_selection | exchange_blend_pm75 | $24,639.84 | $222,782.38 | $48,835.59 | False |
| unlimited_selection | kalshi | $18,602.84 | $214,844.57 | $62,749.36 | False |
| unlimited_selection | polymarket | $35,581.01 | $253,789.98 | $43,529.08 | False |
| unlimited_sell_all | exchange_blend_equal | $348,796.86 | $2,465,915.48 | $-300,290.32 | False |
| unlimited_sell_all | exchange_blend_pm75 | $348,796.86 | $2,465,915.48 | $-300,290.32 | False |
| unlimited_sell_all | kalshi | $348,796.86 | $2,465,915.48 | $-300,290.32 | False |
| unlimited_sell_all | polymarket | $348,796.86 | $2,465,915.48 | $-300,290.32 | False |

The funded model-selection accounts average only $71–$103 committed and peak at $118–$209. Funded sell-all averages $135 and peaks at $227, despite attempting every eligible print. Unlimited results need vastly greater funding; they cannot be extrapolated onto a $10k account.

## Boundary and interpretation

All supplied outcomes are retrospectively available for P&L, but some actual settlements occur after the January 18 reporting boundary. Those open capital cycles have incomplete holding-time denominators. The workflow correctly withholds eventual P&L per capital-hour whenever any accepted fill remains open at the boundary; it does not assume capital was released at trade time or extrapolate future occupancy. At .035, only funded equal-blend selection has a completed capital cycle: $1.56564 net per $1,000 committed-dollar-hours. This is descriptive occupied-cash efficiency, not an annualized return, scalable yield or RFQ fill forecast.

Raising risk caps would require fixed-policy evaluation on the wider dataset and shared-fixture concentration analysis. This audit explains low occupancy mechanically; it does not authorize larger live risk. Historical fee coefficients and payoff assumptions remain those explicitly unverified replay scenarios.

## Evidence

`runs/morning_research_20260908/nfl_capital_hours_jan5_18/` contains one hashed result per ledger plus `verification.json`, all 64 metrics and the nine canonical bucket identifiers. Each existing `scripts/replay_capital_hours.py` run checks its input hash before/after and compares curve and fill integrals with `rel_tol=1e-10`, `abs_tol=1e-6`. Unlimited sell-all appears under four model names with identical portfolios; do not add those duplicates together.

There are 9 complete and 55 incomplete model capital cycles across all fee scenarios. Maximum absolute curve/fill integral difference is 0.000004053 dollar-hours (all passed the combined absolute/relative tolerance). No provider calls, August data, source changes or surviving background jobs.
