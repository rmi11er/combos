# Round-spend discount: NFL proxy backtest

## Conclusion

Under the user's working assumption that partial fills are relatively uncommon, inferred spend is usable as an **exploratory proxy**. The proposed discount does **not backtest robustly** in the retained January NFL sample. Tight matching changes very few trades; broader inferred-budget labels produce unstable results and no consistent funded benefit. Charging the other group 0.4c changes allocation, but a flat 0.4c control often does better than the segmented schedule.

This is a trade-admission replay at historical executed prices, not an experiment in quoting a lower price. It cannot establish the acceptance lift from a discount, and does not model handing back margin on trades we already would have won. No live configuration was changed.

## Test setup

- 23,809 retained pregame distinct-game NFL moneyline prints, January 5–18; nine fixtures.
- Primary inferred spend = executed YES price × contract quantity. Label round when within $0.01 of $5/$10/$20/$50. Original requested spend is unavailable; the proxy uses an observed execution price rather than a known pre-quote field.
- Sensitivities: exact matching, ±$0.05, ±$0.50, inferred requester fees, a wider amount list, and whole-contract budget compatibility.
- All observed quantities in this sample are integers. Whole-contract compatibility asks whether this quantity fits the round budget but one more contract would exceed it. This is a sensitivity assumption, not proof that the historical exchange used that sizing grid.
- Net hurdles in cents per payout contract: flat 0.15/0.2/0.3/0.4; round 0.15 or 0.2 with other spend 0.3 or 0.4.
- Prices, quantities, settlement cash timing and risk identities remain unchanged. Existing scope eligibility is preserved.
- Funded replay: $10,000 starting capital, $100 contract/combo caps and $250 fixture cap; full observed prints only. Unlimited results remove funding/risk limits and are not implementable capacity estimates.
- Maker fee coefficient remains the archived, historically unverified 0.035 assumption. Fee-inclusive label sensitivities use explicit requester coefficients 0.035 or 0.07.

The flat 0.3c funded fill count/PnL and unlimited PnL match the preceding edge-schedule study. The primary baseline commits at most $139.07 under these small caps, so its dollar outcome is not a return on $10,000 continuously deployed.

## Primary result: principal within one cent of $5/$10/$20/$50

Only **35 prints** receive the round-spend proxy label.

| Round / other hurdle | Funded fills | Funded settlement PnL | Unlimited settlement PnL |
|---|---:|---:|---:|
| 0.3 / 0.3c | 21 | -$29.40 | $62,749.36 |
| 0.2 / 0.3c | 21 | -$29.40 | $62,754.20 |
| 0.15 / 0.3c | 21 | -$29.40 | $62,768.75 |
| 0.4 / 0.4c | 34 | +$89.97 | $53,846.74 |
| 0.2 / 0.4c | 35 | +$83.69 | $53,851.58 |
| 0.15 / 0.4c | 35 | +$83.69 | $53,866.13 |

The round discount adds just **one print** at 0.2c and **three prints** at 0.15c versus flat 0.3c without capital constraints. Their total incremental settlement PnL is $4.84 and $19.39; modeled after-maker-fee edge is only $0.084 and $0.348. None adds a funded fill. Removing the largest added winner leaves $0 and $9.67 respectively. Omitting an implicated fixture can erase the unlimited gain.

The positive funded result when other spend pays 0.4c is not evidence of successful segmentation: **flat 0.4c earns $6.28 more** than either discounted version in this primary case. Unlimited PnL also falls substantially versus flat 0.3c because the higher threshold removes trades; neither result alone identifies optimal pricing.

## Label sensitivity

Funded PnL; flat 0.3c is -$29.40 and flat 0.4c is +$89.97 in every row.

| Proxy definition | Round prints | 0.2 / 0.3c | 0.15 / 0.3c | 0.2 / 0.4c | 0.15 / 0.4c |
|---|---:|---:|---:|---:|---:|
| Principal exact | 15 | -$29.40 | -$29.40 | +$89.97 | +$89.97 |
| Principal ±$0.01 | 35 | -$29.40 | -$29.40 | +$83.69 | +$83.69 |
| Principal ±$0.05 | 122 | -$29.40 | -$29.40 | +$83.69 | +$80.31 |
| Principal ±$0.50 | 3,875 | -$55.31 | -$57.59 | +$51.28 | +$44.45 |
| Fee-inclusive, coefficient .07, ±$0.01 | 261 | -$29.40 | -$29.40 | +$84.56 | +$97.46 |
| Fee-inclusive, coefficient .035, ±$0.01 | 26 | -$29.40 | -$29.40 | +$89.97 | +$89.97 |
| Whole-contract budget, fee .07 | 7,240 | -$55.31 | -$57.59 | +$4.72 | -$1.70 |
| Whole-contract budget, fee .035 | 1,329 | -$29.40 | -$29.40 | +$78.45 | +$103.38 |
| Wider amount set, principal ±$0.01 | 164 | -$29.40 | -$29.40 | +$83.69 | +$85.31 |

The wider amount set is $1/$2/$5/$10/$20/$25/$50/$100. Calling everything outside the primary four amounts “non-round” would be misleading: $25 and $100 are obvious counterexamples. Label choices should be frozen before a prospective test.

There are isolated positive 0.15/0.4c outcomes, but they do not persist across label assumptions. In the whole-contract/.07 case, unlimited PnL changes versus flat 0.3c by +$24.15 for the 0.2c round discount and **-$235.69** for 0.15c. Even the unconstrained direction is not stable.

Rare partial fills are one defensible working assumption; they do not eliminate fees, quantity-grid effects, fixed-size orders accidentally producing round principal, or different accepted-flow selection. No accuracy rate for these labels is claimed.

## Separate September quote-mechanics check

This is a different sample, not additional historical PnL evidence. Repriced 617 spend-labelled, priceable distinct-game RFQs at 0.15/0.2/0.3/0.4c hurdles under two requester-fee scenarios: **4,936 dry-run candidates**.

Of 389 requests for exactly $5/$10/$20/$50, **248 (63.8%) produce identical native quotes at 0.15c and 0.2c** under both fee scenarios. Lowering the internal floor often does not lower the customer price because of grid rounding.

In the zero-requester-rate scenario, the 0.2c discount lowers the mean ask by 0.10c and the 0.15c discount by 0.136c versus the 0.3c floor. Recomputing candidate quantities, a uniform within-group acceptance probability would have to increase by about **40%** and **64%**, respectively, to preserve aggregate modeled margin after the same explicit reserves and maker fees. These are break-even scenario ratios, not measured demand elasticities or true conditional-profit estimates. Without grid/sizing effects, the simpler per-contract hurdle ratios imply 50% and 100% more fills.

## Decision

Keep flat 0.3c as the benchmark, not a proven optimum. If testing segmentation prospectively, start with **0.2c on a predefined round-spend cohort versus 0.3c on that same cohort**, randomized within cohort. Hold the other cohort unchanged initially; test its 0.4c alternative separately. This identifies the discount effect without conflating it with a higher non-round threshold. Current evidence does not justify choosing 0.15c or deploying the segmented schedule.

No same-game result is implied; those RFQs still require validated joint pricing and risk controls. Historical settlement PnL here is not a 10/30/60/300-second markout.

## Reproduce

```sh
.venv/bin/python scripts/round_spend_proxy_backtest.py --out runs/round_spend_proxy_backtest_20260909
.venv/bin/python scripts/spend_demand_candidates.py --hurdles-cents 0.15 0.2 0.3 0.4 --out runs/round_spend_schedule_20260909
.venv/bin/python scripts/round_spend_schedule_study.py --folder runs/round_spend_schedule_20260909
.venv/bin/python -m pytest -q tests/test_round_spend_proxy_backtest.py tests/test_research_spend_risk.py
```

The proxy output includes all nine label scenarios, eight policies, archived baseline parity, primary funded ledgers, fixture-omission and largest-win diagnostics. The quote-mechanics output includes candidate ledgers and grid/break-even comparisons. 53 focused tests passed, including proxy tolerance, fee basis, whole-contract compatibility and preserving the existing scope filter.

The official schemas distinguish public historical trade price/quantity from RFQ requested spend. They also describe quote-dependent sizing and requester fees. These distinctions motivate the proxy sensitivities rather than prohibit exploratory testing. [Historical trades](https://docs.kalshi.com/api-reference/historical/get-historical-trades), [RFQ sizing](https://docs.kalshi.com/getting_started/rfqs)
