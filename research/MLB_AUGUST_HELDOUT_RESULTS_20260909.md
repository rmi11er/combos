# MLB August held-out validation results

The frozen August replay and independent audit completed on September 9. The
cohort covers 15 validation dates (August 2–30), with the development fixture
exclusion manifest applied identically to all 28 policy/regime combinations.
The replay is a pregame, full-game, distinct-fixture, 2–4-leg moneyline scope;
props and the combo percentage-value restriction are excluded. It uses
historical fee scenarios explicitly marked unverified, and observed public
prints as counterfactual full-size fills. The audit passed all portfolio,
fee, settlement, exclusion and integer-admission checks; it does not establish
live RFQ acceptance or actual fills.

## Funded $10,000 regime

| Policy | Fills | Trade-time attributed P&L | Modeled net edge | Peak committed cash | Max trade-P&L drawdown |
|---|---:|---:|---:|---:|---:|
| Equal exchange blend (primary) | 1,365 | **+$2,533** | +$982 | $7,472 | $1,956 |
| 75% Polymarket challenger | 1,754 | **+$3,374** | +$1,111 | $8,190 | $1,790 |
| Polymarket quarter-reserve challenger | 896 | +$2,392 | +$1,222 | $5,630 | $2,246 |
| Kalshi control | 1,111 | +$1,941 | +$868 | $7,000 | $1,643 |
| Polymarket point control | 2,162 | **−$1,527** | +$1,126 | $8,500 | $3,667 |
| Sell every priced print | 4,207 | **−$1,824** | **−$233** | $9,347 | $2,863 |

The primary's realized P&L is larger than its modeled edge because the model
edge is the price-versus-fair compensation at trade time, while realized P&L
also contains eventual fair-versus-settlement residual. The gap is not a
repeatable-edge claim. The sell-all control confirms that selecting trades
matters in this held-out window, but it does not tell us whether public prints
would have filled our RFQs.

## Edge and risk sensitivities

For the equal blend in the funded regime, a 0.1¢ threshold produced $3,285 P&L
on 1,958 fills; 0.3¢ produced the primary $2,533 on 1,365; 0.5¢ produced
$2,000 on 820; and the per-leg threshold produced $1,878 on 509. Zero edge
produced $1,276 on 2,274 fills. This is a nonmonotone path over one held-out
window, not a chosen optimum.

The equal blend's risk diagnostics are more concerning than the point estimate:
the named $500 risk-control scenario earned $1,423 with $3,882 peak committed
cash, while the $2,000 scenario lost $2,701 with $8,113 peak cash. The original
configuration earned $550 with $1,378 peak cash. Increasing capacity does not
monotonically improve results.

Unlimited funding is not a realistic performance benchmark. The equal blend
lost $8,777, PM75 lost $66,486 and the sell-all control lost $973,958. The
Polymarket quarter-reserve challenger and Kalshi control were positive
(+$25,824 and +$30,543 respectively), illustrating substantial model and
concentration sensitivity. Unlimited paths require hundreds of thousands or
millions of dollars of committed cash and are not evidence that a $10,000
strategy should remove risk limits.

## Interpretation and deployment consequence

The data support a provisional funded research configuration around the equal
blend or PM75 challenger, with conservative risk limits and a low but positive
edge hurdle. They do not establish that PM is universally sharper, that a
particular risk cap is optimal, or that the 0.1¢ threshold should be promoted.
The public-print selection is an opportunity screen, not an execution model.
The primary model has no annualized IID Sharpe: dates share fixtures and the
study intentionally reports descriptive observed-date variance only. August
does not contain Pinnacle, so this validation cannot test the three-source
liquidity-weighted fair or the conditional Pinnacle/Polymarket anchor.

The next forward test should log proposed full-size RFQ prices, source ages,
depth/spread weights, acceptance/fill outcomes, creator identity and short
horizon markouts. Keep the three-source anchor as a shadow feature first. Do
not change risk limits or blacklist sanctions based on this single held-out
window.

## Reproducible artifacts

- [audited comparison CSV](../runs/mlb_august_frozen_validation_report_20260909/portfolios.csv)
- [funded plot](../runs/mlb_august_frozen_validation_report_20260909/funded.png)
- [unlimited plot](../runs/mlb_august_frozen_validation_report_20260909/unlimited.png)
- [report manifest](../runs/mlb_august_frozen_validation_report_20260909/manifest.json)
- [independent verification](../runs/mlb_august_frozen_validation_20260909/independent_verification.json)

The report plots P&L attributed at trade time, modeled edge, YES premium,
payout notional (face-value dollars, not customer winnings) and committed cash.
The supervisor completion receipt and the independent audit are separate from
the plotting script; the latter refuses to run if audited hashes or endpoints
change.
