# July 21 full MLB universe audit

Independent Decimal audit passes all 390,702 native prints: 346,450 YES-taker prints and 44,252 excluded opposite-side prints. Seven cohort outputs and 24 contiguous hourly census manifests are verified. Native quantities, prices, settlement values, fees and structural classification reconcile.

Broad hypothetical seller net **−$1,857,884.48**, including **$294,773.65** maker fees. Gross loss is $1,563,110.83. YES premium is $12,089,401.74; payout face notional is $266,284,537.66. Fee applicability remains the unverified historical .035 scenario.

All 65 single-fixture omissions remain negative, ranging from $-2,730,053.53 to $-851,279.27. Removing the largest losing fixture membership, 26JUL211840LADPHI, still leaves $-851,279.27. This day's broad loss is not explained by a single game alone. Memberships overlap; these are influence diagnostics, not independent observations or additive attribution.

| Cut | Group | Net P&L |
|---|---|---:|
| legs | 2 | $-861,278.40 |
| legs | 4 | $-234,674.46 |
| legs | 5+ | $-314,013.81 |
| legs | 3 | $-447,917.80 |
| structure | distinct | $-1,468,326.48 |
| structure | same_game | $-389,558.00 |
| family | core | $-1,592,854.88 |
| family | player_prop | $-193,513.86 |
| family | other | $-71,515.74 |
| phase | True | $-312,297.16 |
| phase | False | $-1,545,587.32 |
| premium | <=10 | $157,767.32 |
| premium | >250 | $-1,187,835.11 |
| premium | 10-50 | $-215,742.12 |
| premium | 50-250 | $-612,074.56 |

The at-most-$10 premium group remains profitable despite larger-ticket losses. This is a descriptive cut on the broad universe, not a validated ticket rule for model-selected pregame trades. No premium cap is introduced. All leg-count groups, both structural groups, all families and both scheduled-phase groups lose overall.

This includes every pure-MLB YES-taker print at full observed size without fair-value, capital or strategy filtering. No own quote execution or RFQ acceptance is inferred. Eventual settlement P&L is attributed at trade time; it does not fund positions before settlement. Phase follows scheduled start, not verified first pitch. Source-model and constrained selection comparison is pending.

[Full-universe plot](../runs/morning_research_20260908/universe_july21/universe.png) · [Independent audit](../runs/morning_research_20260908/universe_july21_audit/verification.json)
