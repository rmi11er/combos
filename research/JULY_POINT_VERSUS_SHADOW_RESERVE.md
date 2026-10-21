# Historical point selection versus the shadow quote reserve

The historical point-entry results do not evaluate the price rule used by the current shadow engine. `ShadowEngine.apply` quotes from `stressed_upper` plus the required edge and maker fees; the historical reports select against `fair_point`. This distinction is a major competitiveness issue even if source mappings/feed availability are repaired.

The diagnostic compares both entry bases at identical observed prices, sizes, fees and recorded0.3c/combo hurdles across14currently priced July dates (July31pending, July13unpriced). It uses unlimited decision ledgers; no capital reallocation or actual customer acceptance is inferred. All point-selection totals reconcile to the corresponding daily unlimited summaries and all14input hashes were checked.

| Model | Point-qualified prints | Also clear stressed upper | Point-selected net | Stressed-subset net |
|---|---:|---:|---:|---:|
| Kalshi | 2,755 | 86 | $126,467 | −$664 |
| Equal blend | 4,569 | 98 | $236,781 | −$2,439 |
| PM75 | 10,216 | 105 | $411,035 | −$2,413 |
| Polymarket | 25,791 | 111 | $626,601 | −$2,504 |

These are retrospective unlimited sums over observed dates, not a continuous funded return. A stress-qualified subset is a different selection; its losses are not proof that charging more causes losses.

## Magnitude and source of the reserve

Quantity-weighted mean reserve above point fair across the full matched cohorts:

| Legs | Kalshi | Equal | PM75 | PM |
|---|---:|---:|---:|---:|
| 2 | 3.670c | 3.289c | 3.100c | 2.912c |
| 3 | 14.023c | 13.660c | 13.479c | 13.297c |
| 4 | 19.202c | 18.581c | 18.220c | 17.825c |

No four-leg print clears the stress hurdle; only3–4three-leg prints per model survive. The reserve combines marginal interval uncertainty and the joint moment bound; it is not solely an estimated correlation premium. It is much larger than the0.3c/combo margin being tuned.

The existing bound permits unrestricted higher-order dependence. Direct execution with exact50%leg probabilities, zero interval width and a zero pairwise rho ceiling gives:2legs point25%/upper25%;3legs point12.5%/upper25%;4legs point6.25%/upper16.6667% (plus tiny numerical safety). Thus reducing rho to zero does not recover independent pricing for3–4legs. This is a property of the conservative bound, not a discovered arithmetic bug.

## Required research before promoting a quote model

Keep the current worst-case bound as an explicit benchmark. Evaluate separately: independence plus a measured marginal uncertainty reserve; a coherent parametric joint distribution such as a factor/copula model; and the existing unrestricted moment bound. Compare actual proposed quotes, eligibility, empirical calibration, fixture concentration and capital use on the same cohorts. Any smaller reserve must be justified as a new model assumption with validation, not described as the same guarantee with a better parameter.

Prioritize this comparison alongside the three-source fair and risk/sizing study. A0.1cversus0.3cfee-aware margin adjustment cannot solve a13–19cjoint reserve. Historical exchange-only bounds are not a full three-source live simulation, and price-grid rounding/dynamic live reserves are omitted here. No live pricing source, reserve or correlation configuration changed. Two focused tests cover subset accounting and rejection of funded ledgers.

[Diagnostic results](../runs/morning_research_20260908/july_quote_reserve_diagnostic/results.json) · [Verification](../runs/morning_research_20260908/july_quote_reserve_diagnostic/verification.json) · [Reusable workflow](../scripts/quote_reserve_diagnostic.py)

## Marginal uncertainty versus joint dependence

A second completed diagnostic constructs the product of selected leg upper endpoints, using `1−lower` for NO legs. This is an independent-leg uncertainty scenario, not a dependence-robust bound. It exactly reconciles the previous point/stressed eligibility and reserve totals across all12model/leg groups;28input hashes were checked and two focused tests pass.

| Model | Point-qualified | Independent marginal-upper qualified | Full stress qualified | Marginal-upper subset net |
|---|---:|---:|---:|---:|
| Kalshi | 2,755 | 242 | 86 | −$6,529 |
| Equal blend | 4,569 | 357 | 98 | −$7,354 |
| PM75 | 10,216 | 421 | 105 | −$2,107 |
| Polymarket | 25,791 | 555 | 111 | +$50,998 |

Across models, mean marginal uncertainty reserve is1.694–2.450cfor2legs,1.366–1.979cfor3legs, and0.964–1.415cfor4legs. The additional joint reserve is1.218–1.221c,11.931–12.044c, and16.862–17.787crespectively. Thus the joint term dominates3–4legs, but full marginal endpoints alone still exclude most point opportunities. The PM marginal-upper subset contains209two-leg,196three-leg and150four-leg prints; its profit is not a funded or execution result.

The next candidate study must calibrate both marginal uncertainty and joint dependence. Treat partial use of the leg uncertainty interval as an explicit assumption to test, alongside fully priced interval uncertainty, rather than silently changing the meaning of fair. Data disagreement/freshness guards should remain separate from a price surcharge. These outputs do not justify merely removing the joint reserve or reducing fees; no quoting code/config changed.

[Component results](../runs/morning_research_20260908/july_quote_reserve_diagnostic/components.json) · [Independent reconciliation](../runs/morning_research_20260908/july_quote_reserve_diagnostic/components_verification.json) · [Reusable component workflow](../scripts/joint_reserve_components.py)
