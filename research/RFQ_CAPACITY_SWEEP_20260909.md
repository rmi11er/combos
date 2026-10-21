# NFL full-RFQ capacity replay

Thirty portfolios apply three quote references and five cap sets under two explicit
execution assumptions. All use $10k cash, captured zero maker fees, 0.3c/combo edge,
full fixed sizes or conservative target-cost bounds. All 5,010 decisions were
independently reconciled for admission, every binding risk limit, cash and expiry;
three focused tests cover retained fills versus expiry, shared underlying keys,
multiple simultaneous limits, duplicates and causal time.

Point-pricing results out of 167 RFQs:

| Limits: underlying/combo/event | No-fill 3s expiry admissions | Peak holds | All-admitted-fill admissions | Peak holds |
|---|---:|---:|---:|---:|
| $100/$100/$250 | 87 | $287 | 30 | $466 |
| $500 each | 147 | $642 | 55 | $1,314 |
| $1,000 each | 160 | $1,247 | 70 | $2,941 |
| $2,000 each | 161 | $2,687 | 94 | $6,045 |
| Cash ceiling only | 166 | $9,270 | 107 | $9,997 |

The no-fill scenario releases holds exactly three seconds after hypothetical quote
submission. This is a capacity experiment, not permission to release dispatched
live holds without exchange reconciliation. The all-fill scenario retains every
admitted hold throughout the short capture, with no settlement releases. Neither
is a fill forecast or a bound on every possible acceptance pattern.

Each reservation's full conservative cash liability is charged to every unique
canonical underlying and fixture; opposite orientations receive no hedge credit
across different combos. Signed payoff sensitivities are retained upstream. These
cash-at-risk caps are distinct from payout quantity or derivative-delta limits.

The original per-underlying cap dominates admissions. Moving to $1k admits most
of this priceable short sample under no-fill expiry; doubling again adds only one
RFQ. That is not evidence $1k is optimal or safe. Outcome risk must be assessed on
the larger historical partitions and sustained shadow capture before promotion.
The 167 are the three-source-priced subset of 43,003 RFQs, not the full universe.

Workflow: scripts/rfq_capacity_sweep.py. Outputs:
runs/nfl_rfq_capacity_20260909/{summary,decisions,verification}.json.
Upstream payoff, Pinnacle unit, account precision and sampled-grid assumptions
remain. Creator publication policy excludes none of this subset. No live orders,
acceptance probabilities, realized P&L or blacklist profits are inferred.
