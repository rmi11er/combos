# July 19 full MLB universe audit

Independent Decimal checks pass for all 236,372 native rows: 212,879 YES-taker prints and 23,493 excluded opposite-side prints. All 24 source partitions are contiguous and hashed; native outcomes, quantities, fees, classification and source hashes reconcile.

Broad hypothetical seller net is $947,911.27, after $216,282.70 maker fees. YES premium is $9,236,476.43; maximum payout notional is $154,292,798.91. These are observed-price, unlimited-size counterfactuals, not own fills or funded returns. Historical .035 maker-fee applicability remains unverified.

Largest positive fixture membership: 26JUL191607DETLAA. Removing every print involving it leaves $-743,017.09. Fixture memberships overlap; this is an influence diagnostic, not additive attribution.

| Cut | Group | Net seller P&L |
|---|---|---:|
| legs | 2 | $214,725.57 |
| legs | 5+ | $150,064.69 |
| legs | 4 | $296,686.35 |
| legs | 3 | $286,434.66 |
| structure | same_game | $702,311.25 |
| structure | distinct | $245,600.02 |
| family | player_prop | $432,278.76 |
| family | other | $103,827.58 |
| family | core | $411,804.94 |
| phase | True | $416,574.98 |
| phase | False | $531,336.29 |
| premium | <=10 | $98,947.54 |
| premium | 10-50 | $87,016.01 |
| premium | >250 | $573,924.69 |
| premium | 50-250 | $188,023.02 |

Phase uses scheduled-start proxy, not verified first pitch. Eventual P&L is attributed at trade time; cash is not released then. No model filtering is applied. Shared outcomes reduce statistical independence. This daily benchmark does not yet establish common-model selection results.

[Universe plot](../runs/morning_research_20260908/universe_july19/universe.png) · [Independent verification](../runs/morning_research_20260908/universe_july19_audit/verification.json)
