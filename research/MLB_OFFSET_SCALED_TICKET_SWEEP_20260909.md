# MLB offset-aware limits with scaled ticket liability

This is the follow-up to the fixed-$50-ticket sweep. Exact moneyline offset remains enabled, but both portfolio limits and maximum individual ticket liability rise together.

| Tier | Contract / combo / fixture caps | Ticket cap | Accepted | Peak committed cash | Ending P&L | Max drawdown | Daily Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline | $100 / $100 / $250 | $50 | 1,506 | $2,540 | $2,383 | -$467 | 0.503 |
| Balanced | $250 / $250 / $500 | $100 | 1,928 | $5,574 | $5,644 | -$916 | 0.608 |
| Loose | $500 / $500 / $1,000 | $250 | 2,127 | $9,997 | $9,883 | -$1,649 | **0.645** |
| Very loose | $1,000 / $1,000 / $2,000 | $500 | 1,980 | $10,000 | $13,566 | -$3,304 | 0.519 |
| Capital-only | $10,000 / $10,000 / $10,000 | $1,000 | 1,481 | $10,000 | $17,898 | -$4,234 | 0.523 |

## Interpretation

Allowing tickets to become larger changes the answer materially. The loose tier ($500/$500/$1,000 limits with a $250 ticket cap) has the highest observed settlement-day Sharpe and nearly fills the $10,000 capital pool. The very-loose and capital-only tiers produce larger retrospective P&L because they take larger concentrated positions, but drawdown rises sharply and Sharpe falls.

This supports a **research candidate** around the loose tier, not a live limit recommendation. The result is still based on public-print hypothetical fills, 24 active settlement days, gross cash collateral, linear fee scaling, and exact moneyline offset only. Annualized Sharpe is descriptive and should not be treated as stable.

Machine-readable output: [`mlb_offset_scaled_ticket_sweep.csv`](../analysis/offsetting_allocation_v1/mlb_offset_scaled_ticket_sweep.csv). Executable: [`sweep_mlb_offset_scaled_tickets.py`](../analysis/sweep_mlb_offset_scaled_tickets.py).
