# NFL point selection versus shadow reserve

The January 5–18 matched NFL replay has the same pricing-rule mismatch as July MLB: historical selection uses point fair, while shadow quoting uses stressed upper plus margin and fees. Applying the recorded stress bound to the identical 23,809 prints retains only 3.4–5.0% of point-qualified prints. Every retained print has two legs; no three- or four-leg print qualifies.

| Model | Point-qualified | Stress-qualified | Point-selected net | Stress-selected net | Stress net excluding PHI–SF |
|---|---:|---:|---:|---:|---:|
| Kalshi | 1,307 | 45 | $62,749.36 | $12,321.03 | −$56.66 |
| Equal blend | 1,252 | 63 | $46,846.83 | $12,765.67 | −$405.23 |
| PM75 | 1,560 | 73 | $48,835.59 | $13,242.75 | −$405.23 |
| Polymarket | 2,034 | 90 | $43,529.08 | $13,419.90 | −$486.14 |

The retained profits remain concentrated in PHI–SF. Removing prints touching that game makes all four stressed subsets negative, without reallocating trades. Every K/equal stressed selection also touches LAC–NE. These are fixture influence checks, not confidence intervals.

Quantity-weighted reserve above point fair ranges across models from 1.634–3.269c for two legs, 8.188–9.777c for three legs, and 10.971–12.539c for four legs. The reserve greatly exceeds the 0.3c/combo minimum edge hurdle. Adjusting that small margin alone will not make the current three- and four-leg quote rule competitive with this historical tape.

The reusable reserve workflow was run through a lossless NFL ledger adapter. All four point-selection counts and P&Ls reconcile to the original portfolio summaries. A separate read of the original portfolio independently reproduces stress selection counts, P&L, leg counts and fixture omissions. Input and workflow hashes were verified; original data is unchanged.

This is an unlimited historical subset comparison at observed prices and quantities, with the unverified January .035 maker-fee scenario and exchange-only fair values. It omits live price-grid rounding, dynamic reserves, capital reallocation and customer acceptance. Positive subset P&L does not establish executable edge. No live parameters changed.

Next compare marginal uncertainty and coherent joint-distribution assumptions on the same data, retain the worst-case bound as a benchmark, and replay candidate quote rules under actual sizing/capital constraints. NFL source weights remain separate from MLB; Pinnacle and live depth still require prospective validation.

[Results](../runs/morning_research_20260908/nfl_quote_reserve_diagnostic/results.json) · [Independent verification](../runs/morning_research_20260908/nfl_quote_reserve_diagnostic/root_verification.json) · [Reproduction script](../runs/morning_research_20260908/nfl_quote_reserve_diagnostic/run.py)

## Marginal uncertainty and dependence decomposition

Using independent legs at their selected-side upper marginal endpoints gives the following intermediate scenario. NO legs use one minus the lower YES endpoint. This is an explicit independence assumption, not a dependence-robust guarantee.

| Model | Point-qualified | Marginal-upper qualified | Marginal-upper net | Full-stress qualified |
|---|---:|---:|---:|---:|
| Kalshi | 1,307 | 122 | $14,180.18 | 45 |
| Equal blend | 1,252 | 202 | $6,434.40 | 63 |
| PM75 | 1,560 | 289 | $5,700.91 | 73 |
| Polymarket | 2,034 | 414 | $22,521.48 | 90 |

Across models the mean marginal reserve is 0.511–2.124c for two legs, 0.384–1.616c for three, and 0.260–1.100c for four. The additional joint reserve is respectively 1.123–1.146c, 7.804–8.161c, and 10.711–11.439c. The dependence allowance dominates the three- and four-leg surcharge, but full marginal endpoints also remove most point-qualified prints.

Marginal-upper selections include three- and four-leg prints, but their profits remain concentrated: excluding PHI–SF gives K −$385.49, equal −$512.53, PM75 −$585.15 and PM −$67.98. Removing the extra joint allowance therefore does not resolve this sample's outcome concentration.

All 95,236 recorded model points were independently reconstructed from leg-side probabilities and the documented fixed exchange blends. Component sums and both endpoint selections reconcile to the original diagnostic. Source and input hashes were verified. This checks arithmetic and isolates assumptions; it does not certify historical source quality, probability calibration, or Pinnacle blending. The different selected cohorts cannot rank forecasting accuracy by their profits.

[Component results](../runs/morning_research_20260908/nfl_quote_reserve_diagnostic/components.json) · [Concentration checks](../runs/morning_research_20260908/nfl_quote_reserve_diagnostic/components_verification.json) · [Reproduction](../runs/morning_research_20260908/nfl_quote_reserve_diagnostic/components.py)
