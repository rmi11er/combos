# Expanded non-player payoff enumeration

The reusable score-grid review now covers full-game, first-half and first-quarter
moneylines, spreads, totals and team totals where exact selectors exist. Each
mapping is checked against all 10,201 integer home/away score pairs from 0 to 100.
Subperiod moneyline means winning that period: the selected team's -0.5 spread
has the matching binary payoff, including losing on a tie. Full-game two-way
moneyline voids remain a distinct unresolved basis.

| Conditional completed-period verification | Mappings |
|---|---:|
| Full-game spreads | 65 |
| Full-game totals | 87 |
| Full-game team totals | 2 |
| First-half moneyline / spread / total | 4 / 16 / 21 |
| First-quarter moneyline / spread / total | 16 / 18 / 6 |
| **Total verified** | **235** |
| Full-game moneyline requiring void/tie adjustment | 32 |
| Exact selector unavailable | 187 |

All 454 candidate mappings were accounted for. No payoff mismatch or malformed
mapping was found among available selectors. The 152 earlier full-game binary
checks reproduce exactly; 83 previously deferred mappings now pass the expanded
review. Eight tests cover home/away sides, opposing sides, team totals, period
mismatch and integer pushes. Integer pushes are explicitly void, not binary losses.

This verifies score/side/line arithmetic against the retained semantic mapping,
conditional on completion. It does not independently re-read every exchange rule,
certify current market activity, cover every imaginable score, or resolve differing
cancellation, postponement and suspension rules. No pricing blocks were removed,
and no provider requests or source-weight changes were made.

Outputs: `runs/nfl_all_payoff_enumeration_20260909/{summary,rows,verification}.json`.
The report pins runtime, snapshot, review module and runner hashes. The saved
Pinnacle snapshot is dated September 8; availability counts are not a live census.

Next express exceptional-state basis separately from completed-game probabilities
and quantify an explicit reserve/assumption for shadow comparison. Moneyline tie
adjustment and stake currency remain distinct unresolved inputs. These remaining
issues should not be conflated with score/line mapping errors.
