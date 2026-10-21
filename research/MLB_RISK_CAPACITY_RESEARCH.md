# MLB risk capacity sensitivity — September 7, 2026

The current limits explain low cash utilization. Relaxing them makes more capital deployable, but this one-day experiment does not establish that deployment improves performance. No live limits changed.

The reusable [sweep](../scripts/mlb_risk_capacity.py) evaluates a fixed grid on the September 5 complete common Kalshi/Polymarket cohort: 21,880 YES-taker prints per model, 2–4 distinct-game legs, full-game markets, at least 60 seconds before the original scheduled start. Pricing, the 0.3-cent net point-entry threshold, observed price and full printed quantity are held constant. Each scenario/model starts its own $10,000 portfolio. The grid was specified before calculating its outcomes; there is no P&L-based parameter selection.

![Capacity and concentration sensitivity](../runs/mlb_historical_20260907/risk_capacity/risk_capacity.png)

| Underlying / combo / fixture caps | Peak cash: Kalshi / Polymarket | Known P&L: Kalshi / Polymarket |
|---|---:|---:|
| $100 / $100 / $250 (current) | $1,334 / $1,522 | +$149 / −$45 |
| $100 / $100 / $1,000 | $1,523 / $2,013 | +$282 / −$4 |
| $500 / $100 / $250 | $1,828 / $2,312 | −$22 / −$238 |
| $100 / $500 / $250 | $1,334 / $1,522 | +$149 / −$45 |
| $250 / $250 / $500 | $3,089 / $3,183 | +$553 / −$99 |
| $500 / $500 / $1,000 | $5,505 / $6,002 | +$957 / −$476 |
| $1,000 / $1,000 / $2,000 | $9,725 / $9,999 | +$788 / −$1,294 |
| $10,000 / $10,000 / $10,000 | $11,734 / $10,282 | +$100 / +$1,040 |

Known P&L excludes unresolved outcomes. In the $1,000/$1,000/$2,000 row, loose final P&L bounds are **−$708 to +$1,282** for Kalshi and **−$2,442 to −$974** for Polymarket. Baseline bounds are −$124 to +$257 and −$315 to +$53. Unrestricted concentration in the final row changes which early tickets consume capital; it is not an exposure-scaled copy of another portfolio.

The last row can exceed $10,000 committed cash because the existing backtester treats $10,000 as **starting capital**, allowing actually settled gains to be reinvested. It does not impose a separate fixed $10,000 maximum-open-cash ceiling. This is an existing policy distinction to resolve before launch if “10k top” is intended as a hard limit. The row does not use trade-attributed future gains to fund positions. Expected edge likewise cannot finance new trades.

## What binds

The current Kalshi model has 755 prints clearing the price test; 96 fit risk. An independent audit finds underlying caps bind on 651 of these decisions, fixture caps on 382, combo caps on 231, and available capital on 6. For Polymarket, 2,183 clear price and 128 fit risk; underlying binds on 2,017, fixture on 1,240, combo on 671 and capital on 7. These are **nonexclusive counts**: a single print can fail several controls. The ordinary decision log reports only the first failure, so its reason counts differ.

Raising the combo cap alone has no effect here: every combo's full cost also goes into each constituent underlying bucket, whose $100 limit still applies. Raising only one of the underlying/fixture limits runs into the other. “Capital exhausted” at baseline usually describes a large individual printed ticket exceeding currently available cash; it does not establish that the portfolio reached its cash ceiling. Full-size print rejection leaves capacity fragments unused. A separately labeled capacity-aware quote-sizing experiment is a useful next step; resizing public prints is not evidence of actual RFQ fills.

## Risk accounting and concentration

For a hypothetical maker buying the NO side, cash at risk is `quantity × (1 − YES price) + maker fee`. The ledger charges this **once to portfolio cash** and in full to **every distinct underlying and fixture bucket** in the combo. This duplicates risk incidence deliberately; it does not charge cash repeatedly. Opposing moneyline contracts and YES/NO choices share one canonical winner-risk bucket, so using the opposite team ticker cannot bypass the underlying cap. Exact run-line thresholds share canonical score-difference keys; doubleheaders retain separate fixture identities. The ledger takes no offsetting hedge credit across combo tickets. A complementary single leg does not make two arbitrary multi-leg positions fungible as whole portfolios.

Combo identifiers currently hash native ticker/side combinations. Economically equivalent alternate representations may have distinct combo buckets, but their shared underlying/fixture limits still aggregate. A future payoff-aware portfolio engine should canonicalize whole-combo payoff identity before granting any netting credit; no such credit is assumed here.

For N fixture buckets and at least k distinct fixtures per open combo, full-cost fixture charging implies:

`committed cash ≤ N × per-fixture cap / k`.

Across the complete common cohort there are 46 fixture identities, including games on later dates. At the current $250 fixture cap and minimum two games per combo, even this loose static ceiling is only **$5,750**. The real bound is tighter when fewer fixtures are available, some fixtures dominate demand, and the $100 underlying limits bind. For an isolated 16-game NFL universe the same ceiling is **$2,000**, before considering other controls. Merely permitting $10,000 with 16 fixtures would require at least a $1,250 fixture cap for all-two-leg positions, $1,875 for all-three-leg, or $2,500 for all-four-leg positions, with balanced exposure across all fixtures. These are necessary arithmetic conditions, not recommended loss limits or attainable quote volume.

The audit saves the number of previously observed priceable fixtures still pregame at peak cash, separately from fixtures in held positions. These are historical original-schedule proxies, not a live inventory measurement. Games that have started can still hold capital until settlement, so “currently pregame fixtures” alone is not a bound on all held positions.

At peak cash, the largest shared fixture accounts for 18.6%/16.4% of the baseline Kalshi/Polymarket portfolio. With $1,000/$1,000/$2,000 limits this becomes 20.5%/20.0%; in the final near-capital-only scenario it reaches 39.5%/44.4%. These gross incident fractions overlap across fixtures. The audit also saves an equal-split fixture cash attribution and HHI for comparison, which are descriptive allocations and never replace the full-cost risk checks.

## Drawdown and next decisions

Both drawdown conventions are saved. Baseline trade-attributed drawdowns are $101/$172, versus $16/$90 on the settlement-recognized curve during the reporting window. The $1,000/$1,000/$2,000 scenario has trade-attributed drawdowns of $759/$2,250 and within-window settlement-recognized drawdowns of $336/$768. Settlement accounting omits later outcome recognition from this one-day cash window; trade attribution uses eventual known outcomes at entry time. Neither series is a mark-to-market liquidity or full future drawdown estimate. Daily Sharpe and variance remain unavailable from one complete day.

Treat $10,000 as a financing ceiling to define, not a utilization target to force. Next, carry the same predeclared grid into independent MLB slates, compare calibration and source disagreement at matched exposure, and assess grouped fixture loss scenarios and drawdowns before selecting limits. Choose acceptable single-game loss budgets first, then assess feasible capital deployment and capacity-aware quote sizes. MLB and NFL should share accounting infrastructure while retaining separate concentration and pricing parameters. Nothing in this sweep requires abandoning the 30-second Pinnacle anchor; MLB Pinnacle history is still unavailable, so these are exchange-only comparisons.

## Reproduce and verify

```sh
.venv/bin/python scripts/mlb_risk_capacity.py
.venv/bin/python -m pytest tests/test_mlb_risk_capacity.py tests/test_backtest.py tests/test_fees_and_payoff_risk.py -q
```

[Machine-readable summaries](../runs/mlb_historical_20260907/risk_capacity/summary.json), [input/code manifest](../runs/mlb_historical_20260907/risk_capacity/manifest.json), and compressed full decision/curve logs are saved under `runs/mlb_historical_20260907/risk_capacity/`. Every accepted/rejected risk decision reconciles against an independent integer-dollar-unit replay with settlement-timed releases. Tests cover duplicated incidence versus single cash charging, all simultaneous binding limits, no lookahead funding, locked unknown outcomes, common-cohort filtering before funding, full-size rejection, reduced risk multipliers, and independent audit disagreement detection. **27 focused tests passed.**
