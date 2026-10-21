# Edge-hurdle sweep: Kalshi and equal blend

Only the fair-value model and minimum after-fee edge hurdle vary. Every run uses the selected shadow policy: `$500 / $500 / $1,000` contract/combo/fixture limits, `$250` maximum gross ticket liability, exact full-game moneyline offsetting, $10,000 capital, and zero marginal reserve.

## MLB

| Model | Hurdle | Accepted | Peak committed | Ending P&L | Max drawdown | Daily Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| Kalshi | 0.00¢ | 3,083 | $10,000 | $4,482 | -$2,404 | 0.247 |
| Kalshi | 0.15¢ | 2,647 | $10,000 | **$6,766** | -$1,618 | **0.408** |
| Kalshi | 0.30¢ | 2,127 | $9,997 | $9,883 | -$1,649 | 0.645 |
| Kalshi | 0.50¢ | 1,757 | $7,075 | $8,760 | -$1,254 | 0.558 |
| Kalshi | 1.00¢ | 1,126 | $4,477 | $5,518 | -$934 | 0.452 |
| Equal blend | 0.00¢ | 2,530 | $10,000 | $321 | -$1,872 | 0.027 |
| Equal blend | 0.15¢ | 1,778 | $8,793 | $1,046 | -$2,113 | 0.084 |
| Equal blend | 0.30¢ | 1,161 | $7,753 | $2,027 | -$1,448 | 0.195 |
| Equal blend | 0.50¢ | 851 | $4,868 | $716 | -$1,429 | 0.095 |
| Equal blend | 1.00¢ | 537 | $3,709 | $1,198 | -$724 | 0.224 |

## NFL

| Model | Hurdle | Accepted | Ending P&L | Max drawdown | Daily Sharpe |
|---|---:|---:|---:|---:|---:|
| Kalshi | 0.00¢ | 55 | -$498 | -$611 | -0.806 |
| Kalshi | 0.15¢ | 51 | -$49 | -$141 | -0.097 |
| Kalshi | 0.30¢ | 59 | $266 | -$295 | 0.346 |
| Kalshi | 0.50¢ | 50 | $396 | -$327 | 0.407 |
| Kalshi | 1.00¢ | 33 | $473 | -$138 | 0.487 |
| Equal blend | 0.00¢ | 61 | -$446 | -$539 | -0.666 |
| Equal blend | 0.15¢ | 74 | -$130 | -$230 | -0.254 |
| Equal blend | 0.30¢ | 37 | -$116 | -$489 | -0.079 |
| Equal blend | 0.50¢ | 55 | $397 | -$336 | 0.391 |
| Equal blend | 1.00¢ | 29 | $239 | -$185 | 0.252 |

## Read-through

- **MLB Kalshi:** the 0.30¢ hurdle is strongest on this sample by both ending P&L and Sharpe. The 0.15¢ setting deploys more capital but admits lower-quality flow and gives up risk-adjusted performance.
- **MLB equal blend:** all hurdles are positive, but performance is weaker and less monotonic. The 1.00¢ hurdle has the best Sharpe, while 0.30¢ has the highest ending P&L.
- **NFL:** the sample is too small for a stable selection. Higher hurdles improve the Kalshi curve monotonically in this slice; equal blend is mixed and all accepted counts are small.
- The earlier 0.15¢ choice is therefore **not supported as a universal hurdle**. A reasonable shadow default is 0.30¢ for Kalshi and a separate challenger hurdle sweep for equal blend until the three-source model is available.

Machine-readable output: [`edge_hurdle_fixed_models.csv`](../analysis/offsetting_allocation_v1/edge_hurdle_fixed_models.csv). Executable: [`sweep_edge_hurdles_fixed_models.py`](../analysis/sweep_edge_hurdles_fixed_models.py).
