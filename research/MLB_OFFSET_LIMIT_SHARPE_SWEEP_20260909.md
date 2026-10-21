# MLB offset-aware limit sweep

Date: 2026-09-09  
Scope: saved MLB historical replay; exploratory sizing evidence

All policies use the exact moneyline-offset implementation and a **$50 maximum gross liability per ticket**. Cash remains gross collateral. The sweep changes only contract, combo, and fixture risk caps. Sharpe is computed from realized settlement P&L divided by the $10,000 starting capital, aggregated by UTC settlement day, over 24 active settlement days. The annualized column is shown for comparison but is unstable for this short sample.

## Joint looseness

| Policy | Contract / combo / fixture caps | Accepted | Peak committed cash | Ending P&L | Max drawdown | Daily Sharpe | Annualized Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline | $100 / $100 / $250 | 1,506 | $2,540 | $2,383 | -$467 | 0.503 | 7.98 |
| Balanced | $250 / $250 / $500 | 2,197 | $5,158 | $4,174 | -$977 | 0.507 | 8.05 |
| Loose | $500 / $500 / $1,000 | 2,743 | $8,379 | $5,798 | -$1,419 | **0.549** | **8.71** |
| Very loose | $1,000 / $1,000 / $2,000 | 3,253 | $10,000 | $6,598 | -$1,831 | 0.441 | 7.01 |
| Capital-only | $10,000 / $10,000 / $10,000 | 3,672 | $10,000 | $5,265 | -$2,283 | 0.317 | 5.03 |

Loosening limits increased deployment and retrospective P&L through the $500/$500/$1,000 tier, but the very-loose and capital-only portfolios gave back Sharpe while drawdown continued to rise. This is evidence of a capacity/concentration tradeoff, not evidence that the $500 tier is a live optimum.

## One-limit-at-a-time comparisons

The other two limits remain at the baseline values.

| Change | Caps | Accepted | Peak committed cash | Ending P&L | Max drawdown | Daily Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| Contract tight | $50 / $100 / $250 | 1,130 | $1,533 | $1,593 | -$283 | 0.440 |
| Baseline | $100 / $100 / $250 | 1,506 | $2,540 | $2,383 | -$467 | 0.503 |
| Contract loose | $250 / $100 / $250 | 1,921 | $4,763 | $3,762 | -$693 | **0.615** |
| Combo tight | $100 / $50 / $250 | 1,504 | $2,491 | $2,580 | -$422 | 0.539 |
| Combo loose | $100 / $250 / $250 | 1,506 | $2,540 | $2,383 | -$467 | 0.503 |
| Fixture tight | $100 / $100 / $100 | 1,241 | $2,245 | $1,753 | -$384 | 0.514 |
| Fixture loose | $100 / $100 / $500 | 1,647 | $2,928 | $3,375 | -$479 | 0.582 |

The contract cap was the most consequential single lever in this replay. Loosening the combo cap did nothing because other limits bound first. Loosening the fixture cap added capacity and improved this sample's Sharpe, but with larger drawdown.

## What this supports

- **Accepted as a research fixture:** use exact moneyline offset with a minimum $50 ticket-cap policy when comparing future sport portfolios. The offset applies only after exact fixture/team matching; it is not a blanket hedge credit.
- **Accepted mechanically:** larger limits deploy more capital and admit more tickets.
- **Not accepted as a live optimum:** the best observed Sharpe occurs at different points in joint and one-at-a-time sweeps, and all estimates use public-print hypothetical fills.
- **Not sufficient for annualized Sharpe claims:** 24 active settlement days, clustered outcomes, no queue/fill model, and no forward period make the annualized figures descriptive only.

The executable and machine-readable outputs are [`sweep_mlb_offset_limits.py`](../analysis/sweep_mlb_offset_limits.py), [`mlb_offset_limit_sweep.json`](../analysis/offsetting_allocation_v1/mlb_offset_limit_sweep.json), and [`mlb_offset_limit_sweep.csv`](../analysis/offsetting_allocation_v1/mlb_offset_limit_sweep.csv).
