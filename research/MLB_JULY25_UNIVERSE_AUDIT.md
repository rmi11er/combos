# July 25 full MLB universe audit

Independent Decimal checks pass all414143native rows:370942YES-taker prints and43201excluded opposite-side prints. Native prices, sizes, outcomes (including scalar settlements), fee arithmetic, classifications and source hashes reconcile. Root separately rechecked all retained audit input hashes and visually inspected the plot.

Broad hypothetical seller net is **−$2,736,934.97**, after **$354,583.05** archived scenario fees. Gross is−$2,382,351.92, YES premium$14,742,049.16, payout face$260,687,153.61 and settlement obligation$17,124,401.08. This is an unconstrained public-print counterfactual, not our portfolio or evidence of RFQ capture. Historical .035 maker-fee applicability remains unverified.

| Cut | Net seller P&L |
|---|---:|
| 2 legs | −$987,120.62 |
| 3 legs | −$385,273.32 |
| 4 legs | −$448,465.29 |
| 5+ legs | −$916,075.74 |
| Distinct fixtures | −$2,888,547.24 |
| Contains same-game legs | +$151,612.27 |
| Core markets | −$2,805,147.72 |
| Contains player props | +$142,886.51 |
| Other family | −$74,673.76 |
| Pregame schedule proxy | −$750,985.22 |
| After scheduled start | −$1,985,949.75 |
| YES premium ≤$10 | +$67,050.64 |
| YES premium $10–50 | −$440,325.02 |
| YES premium $50–250 | −$976,883.89 |
| YES premium >$250 | −$1,386,776.70 |

Removing every print involving LAD–NYM (`26JUL251915LADNYM`) changes net to+$43,415.80. Single-fixture omission results range from−$3,419,162.52 to+$43,415.80. Fixture memberships overlap, so their contributions cannot be added or treated as independent observations. This date strongly illustrates why hundreds of thousands of prints can still have substantial shared outcome risk.

Next compare the matched model cohort and its selected/rejected partitions once pricing completes. The profitable small-premium or same-game slices are descriptive; they do not justify new filters or same-game deployment without pooled validation. August remains held out. Eventual outcome P&L is attributed at trade time and does not release spendable capital early.

[Universe plot](../runs/morning_research_20260908/universe_july25/universe.png) · [Independent audit](../runs/morning_research_20260908/universe_july25_audit/verification.json) · [Root verification](../runs/morning_research_20260908/universe_july25_audit/root_verification.json)
