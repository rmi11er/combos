# July 23 full MLB universe audit

Independent Decimal checks pass all 269,995 native rows: 238,909 YES-taker prints and 31,086 excluded opposite-side prints. Native quantities, prices, settlements, fee calculations, classification and source hashes reconcile. Seven cohort outputs and 24 contiguous census partitions were separately verified.

Broad hypothetical seller net **$2,602,508.43**, after **$246,536.46** fees. Gross P&L is $2,849,044.88; YES premium $10,288,993.76; payout face $125,219,279.52. Historical .035 maker-fee applicability remains unverified.

All 64 single-fixture omissions retain positive P&L. Omitting the largest positive membership, 26JUL231715AZSTL, leaves $738,677.28. This is stronger within-day robustness than several earlier winning dates, but overlapping omissions are not confidence intervals or independent observations.

| Cut | Group | Net P&L |
|---|---|---:|
| legs | 4 | $381,564.04 |
| legs | 3 | $616,027.90 |
| legs | 5+ | $866,062.63 |
| legs | 2 | $738,853.86 |
| structure | same_game | $971,391.43 |
| structure | distinct | $1,631,117.00 |
| family | player_prop | $483,153.94 |
| family | core | $2,054,650.49 |
| family | other | $64,704.00 |
| phase | False | $1,168,779.00 |
| phase | True | $1,433,729.43 |
| premium | 10-50 | $585,083.89 |
| premium | <=10 | $259,825.78 |
| premium | 50-250 | $658,414.33 |
| premium | >250 | $1,099,184.43 |

All listed slices are profitable. This does not validate selling every RFQ: the full-print public tape supplies hypothetical execution prices, and adjacent losing dates remain part of the study. No capital, model-availability or strategy filter is applied here. Phase is a scheduled-time proxy. Eventual settlement P&L is attributed at trade time, without releasing spendable cash before settlement.

[Universe plot](../runs/morning_research_20260908/universe_july23/universe.png) · [Independent evidence](../runs/morning_research_20260908/universe_july23_audit/verification.json)
