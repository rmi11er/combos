# MLB interim 15-date aggregate — September 9, 2026

The completion follow-through has finished the first 15 dates (July 1 through
July 31, every other day). This is an interim aggregation of the per-date
`partial_sizing/summary.json` files; the full 30-date certificate and pooled
chronological sweep are still running.

These are public-print counterfactual fills under the historical fee scenario.
They are useful for comparing capacity and model direction, but they are not a
fill forecast and do not validate Pinnacle: this cohort contains exchange-only
models.

| Sizing | Model | Dates | Fills | Trade-time P&L | Realized P&L | YES premium | Largest daily peak committed |
|---|---|---:|---:|---:|---:|---:|---:|
| Full | Equal exchange blend | 15 | 843 | -$139 | +$567 | $3,639 | $974 |
| Full | PM75 challenger | 15 | 1,047 | +$130 | +$729 | $4,663 | $1,085 |
| Full | Kalshi control | 15 | 751 | **+$379** | +$528 | $3,368 | $1,101 |
| Full | Polymarket control | 15 | 1,332 | +$441 | +$569 | $6,005 | $1,246 |
| Partial | Equal exchange blend | 15 | 596 | **+$724** | +$1,161 | $5,380 | $1,209 |
| Partial | PM75 challenger | 15 | 713 | +$510 | +$1,055 | $6,182 | $1,431 |
| Partial | Kalshi control | 15 | 580 | **+$747** | +$813 | $4,781 | $1,281 |
| Partial | Polymarket control | 15 | 844 | +$470 | +$603 | $7,480 | $1,551 |

The partial-size paths have fewer fills because one large affordable response can
consume shared underlying capacity and displace later prints. Within this
interim slice, partial sizing improves trade-time P&L for every model, but the
ranking is not stable enough to select a live fair or edge charge. Kalshi has
the strongest partial trade-time result, while the PM75 and equal-blend
results remain positive but lower.

The next valid comparison is the completed chronological 30-date run. It must
use one account ledger, preserve date order and settlement release, and report
drawdown and capital utilization. No risk limit or hurdle should be changed
from this interim table alone.
