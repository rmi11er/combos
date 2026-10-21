# NFL markout price-versus-weight attribution

Added optional `record_venue_components` logging to the research RFQ consumer.
Each selected leg can retain every venue's selected-side probability, final
weight, effective depth, fee-expanded spread, freshness/age, score and source
references. This flag changes logging only and requires a boolean. It remains
off by default; a trace-enabled next-capture input is saved at
runs/fair_attribution_setup_20260909/runtime_input.json.

Added a symmetric algebraic decomposition. For a leg's weighted probability,
the price term is sum((w0+w1)/2 * (p1-p0)); the weight term is
sum((p0+p1)/2 * (w1-w0)). Their sum exactly recovers the leg-fair change.
For an independent 2–4-leg product, average the marginal product contribution
over all leg-update orders, applying that same contribution multiplier to both
terms. This assigns product interactions symmetrically and reconciles to the
combo change. It is descriptive accounting, not a causal intervention: liquidity
and freshness weights can themselves depend on market prices.

Three completed captures were enriched and replayed at their original decision
and horizon source cutoffs:

| Capture | Exact baseline pricing records | Observed marks | Zero price component |
|---|---:|---:|---:|
| Three-minute markout run | 65,995 | 1,348 | 1,348 |
| Two-minute creator ingestion | 44,988 | 678 | 678 |
| Ninety-second shutdown fix | 33,562 | 283 | 283 |

The 21 explicit lag-guard exclusions in the two-minute capture are not repriced
as eligible decisions. All other 144,545 pricing records reproduce exactly after
removing only the new trace field. All 2,309 observed future-fair records and their
total markout changes reconcile to the stored outputs. Every observed markout
has zero attributed venue-price contribution; changes are assigned to weights.

This confirms that these tiny quiet-window markouts are not evidence of creator
price anticipation. They reflect changes in model mixture, with depth/freshness
and verification availability among its inputs. It does not show that delayed
Pinnacle is safe or unsafe during news, or that the fair is calibrated. Missing
marks still select the observed sample. Do not use these raw model marks alone
to infer creator toxicity or justify blacklist PnL benefits.

Five focused tests passed, including pure weight movement, mixed price/weight
changes, reversal symmetry and the logging flag. Three real replay comparisons
provide exact baseline and markout parity. Full historical study pins were not
modified; prior research-consumer source is archived in the setup directory.

Workflows: scripts/fair_change_attribution.py and scripts/replay_fair_change_attribution.py.
Artifacts: runs/nfl_three_minute_fair_attribution_20260909,
runs/nfl_two_minute_fair_attribution_20260909 and
runs/nfl_fair_change_attribution_20260909.
