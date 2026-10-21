# CFB combo coverage and leg counts, August 31–September 6, 2026

This extends the previous weekday study using exactly the same trades and sampling weights. There is no two-leg or pregame restriction. The universe remains all-CFB standard RFQ combos; mixed-sport parlays are excluded. Saturday is a complete census; the other six days use four random 15-second cells per hour. Approximate sampling intervals are preserved in the numerical output.

No individual-player prop legs were found in the analyzed all-CFB combos. Every recovered CFB leg belongs to a full-game moneyline/spread/total, team total, or first-half/first-quarter winner/spread/total series. Team totals and period outcomes are additional game markets, not individual-player props. Zero observed player-prop volume outside Saturday is not a full-week census claim.

| Coverage | YES premium | Payout notional |
|---|---:|---:|
| Full-game moneyline/spread/total only | $37.42m | $339.41m |
| Additional combos with team total or period leg | $12.85m | $38.88m |
| Combined | $50.27m | $378.29m |

Adding team-total and period coverage increases estimated traded premium by **34.3%** and payout notional by **11.5%**. The incremental cohort is disjoint from the full-game-only cohort. It accounts for 25.6% of combined premium and 10.3% of combined notional. Of its $12.85m premium, $11.33m contains period legs but no team-total leg, $1.26m contains team-total legs but no period leg, and $0.25m contains both.

The approximate 95% interval for incremental premium is $12.26m–$13.44m; for incremental notional it is $33.13m–$44.63m. These reflect stratified sampling uncertainty and can understate the effect of rare large prints.

| Legs | Full-game-only premium | Full-game-only notional | All observed no-player-prop premium | All observed no-player-prop notional |
|---|---:|---:|---:|---:|
| 2 | $17.21m | $61.43m | $27.35m | $75.40m |
| 3 | $5.91m | $49.21m | $7.08m | $52.90m |
| 4 | $5.31m | $25.51m | $5.71m | $27.94m |
| 5+ | $8.99m | $203.26m | $10.12m | $222.05m |

The broader columns include team totals and periods, and therefore reproduce the prior two-leg total ($27.35m premium / $75.40m payout notional). All four leg bins sum back to their corresponding coverage universe. All-CFB totals reconcile to the preceding weekday study.

Premium is sum(quantity × YES price), counted once per print. Payout notional is sum(quantity × $1). Five-plus-leg low-probability combinations can generate high payout notional relative to premium. These volume figures do not estimate attainable fills, profit, or pricing edge. Correlation, settlement equivalence, latency, fees and capital limits still determine quoteability.

Subscription implication for this CFB evidence: ask explicitly for exact alternate lines, team totals and first-half/quarter markets. This study provides no measured incremental volume from individual-player props. NFL player-prop demand must be evaluated separately; CFB cannot establish the right NFL player-prop subscription.

Implementation: `src/combos/cfb_market_scope.py` uses an explicit reviewed taxonomy and rejects unknown series. `scripts/cfb_prop_scope.py` rebuilds classifications, preserves input/code hashes, calculates daily/hourly estimates and leg bins, reconciles prior totals, and generates a chart. Three targeted classification tests passed.

[Chart](../runs/cfb_week_20260831/prop_scope_volume.png) · [Numerical output](../runs/cfb_week_20260831/prop_scope_summary.json) · [Daily CSV](../runs/cfb_week_20260831/prop_scope_daily.csv) · [Provenance manifest](../runs/cfb_week_20260831/prop_scope_manifest.json)
