# Historical round-spend discount replication

Run date: September 9, 2026. Result: the retained MLB history does not provide robust support for lowering the edge hurdle specifically for round-spend trades. This is a historical selection replay, not an estimate of demand elasticity or the PnL of actually repricing quotes.

## Sample and experiment

The extension uses 772,961 historical prints: 415,673 from 15 retained July dates and 357,288 from 15 retained August dates. These are sampled dates, not complete months. The scope is Kalshi-model, pure KXMLBGAME, two-to-four-leg combos with distinct fixtures; same-game and mixed-market combos are excluded. There are 402 July fixtures and 429 August fixtures. August is a later-period replication, not an untouched holdout, since the archive has been used in other research.

Following the requested assumption that partial fills are rare, inferred principal is observed filled quantity times observed premium. Targets are $5, $10, $20, and $50. Classification is retrospective and does not establish that the original request specified that dollar amount.

Five labeling specifications were retained:

| Round-spend definition | July prints | August prints |
| --- | ---: | ---: |
| Principal within $0.01 | 411 | 240 |
| Principal within $0.05 | 1,481 | 1,035 |
| Principal plus modeled requester fee, coefficient 0.07, within $0.05 | 96,569 | 95,304 |
| Principal plus modeled requester fee, coefficient 0.035, within $0.05 | 1,473 | 1,139 |
| Integer quantity exhausting a target budget before one more contract, coefficient 0.07 | 7,562 | 5,049 |

Fee coefficients are scenarios, not verified historical fee schedules. The strong dependence of label coverage on fee treatment is itself an important result. Do not silently interpret the fee-inclusive group as the user's principal-only definition.

## Funded replay: fee-inclusive 0.07, five-cent tolerance

Edges below are cents per combo contract, net of archived maker fees. Each period starts with $10,000, with $100 per-contract and per-combo caps and $250 per-fixture caps. Cash and risk carry across retained dates within each period; they reset between July and August. Outcomes release capital through the existing causal settlement ledger, with configured settlement delay zero.

| Round / other edge hurdle | July settlement PnL | August settlement PnL |
| --- | ---: | ---: |
| Flat 0.30c | $236.25 | $313.75 |
| Flat 0.40c | $300.78 | $523.78 |
| 0.20c / 0.30c | $96.31 | $246.19 |
| 0.15c / 0.30c | -$73.60 | $358.18 |
| 0.20c / 0.40c | $121.93 | $384.86 |
| 0.15c / 0.40c | -$105.64 | $294.39 |

The 0.20c discount against flat 0.30c underperforms in both periods. The 0.15c discount improves August but loses money in July. Flat 0.40c beats all four segmented schedules in both periods under this definition; this is not sufficient to declare 0.40c optimal.

These are modest, cap-constrained dollar results, not returns on continuously invested $10,000. For example, July flat 0.30c has 507 fills and approximately $769 peak committed cash. Changing admission rules can displace later fills, so incremental funded PnL is not simply the sum of the newly eligible prints.

## Separate the marginal cohort from capital sequencing

Without funding caps, the incremental settlement PnL of each round discount versus its matching flat other-trade hurdle is:

| Round / other hurdle | July incremental PnL | August incremental PnL |
| --- | ---: | ---: |
| 0.20c / 0.30c | -$408.45 | +$136.63 |
| 0.15c / 0.30c | -$541.36 | -$647.68 |
| 0.20c / 0.40c | +$238.69 | +$180.90 |
| 0.15c / 0.40c | +$105.77 | -$603.41 |

Thus 0.20c versus a 0.40c other-trade hurdle has a positive unconstrained marginal cohort in both samples, but this does not survive the funded portfolio replay. The 0.15c versus 0.30c marginal cohort is negative in both samples. In July, the latter admits 587 additional prints; removing its largest added winner makes the result worse, not better.

328,290 August prints share no fixture with July. On this restricted subset, the incremental unconstrained PnL remains +$136.63 for 0.20c / 0.30c and -$679.84 for 0.15c / 0.30c. Shared July fixtures do not explain that sign pattern. No IID trade-level significance claim is made: shared legs and games create dependent outcomes.

## Sensitivities that should not be hidden

The strict principal-only, one-cent proxy produces exactly the same funded PnL as its matching flat policy in both months for all four segmented schedules. It changes too little of the funded book to support a discount decision.

The integer-budget sensitivity is more favorable to discounts against 0.30c:

| Round / other hurdle | July PnL | August PnL |
| --- | ---: | ---: |
| Flat 0.30c | $236.25 | $313.75 |
| 0.20c / 0.30c | $236.51 | $352.56 |
| 0.15c / 0.30c | $240.98 | $337.98 |

However, 288,632 July prints and 282,427 August prints have fractional quantities. An integer-budget rule therefore applies only to a minority, and its historical quantity-grid assumption is unverified. Against flat 0.40c, the integer-budget discounts improve July but worsen August. Principal-five-cent and fee-0.035-five-cent specifications have unconstrained results in the machine-readable output; funded replays were not run for those two specifications.

## Interpretation and next experiment

Keep round-spend as a segmentation feature, but this experiment does not justify deploying a blanket round-number discount. First validate spend semantics and fees using original request fields where available. Then compare quote schedules prospectively in shadow or a separately authorized controlled experiment, retaining quote-time budget labels, exposure, acceptance, subsequent markouts, and fixture-level risk. Pricing lower could change both quantity and win probability; historical executed prints alone cannot identify those responses.

This replay holds executed prices and quantities fixed and changes only eligibility. It assumes access to observed prints at those terms; there is no queue/competition model. Fair values are archived candle-mid-derived estimates and fees are archived assumptions. Reported PnL is net settlement PnL, not a forward-markout curve or a verified executable hedged return. Same-game offset feasibility is not tested here.

## Reproduction and checks

Run from the project root:

```sh
.venv/bin/python scripts/historical_round_spend_extension.py --out runs/historical_round_spend_extension_20260909
.venv/bin/python -m pytest -q tests/test_historical_round_spend_extension.py tests/test_round_spend_proxy_backtest.py
```

All six focused tests pass. Vectorized policy eligibility is checked against the original scalar implementation. Prefiltered financial replay is tested against full-row replay, including settlement recycling. An additional actual-data comparison on July 1 checked 25,558 historical input rows: full and prefiltered engines agreed exactly on all 40 fills and financial metrics, including $88.2781 settlement PnL. Every funded replay asserts that filled IDs belong to its policy-selected set.

Machine-readable results, configuration, source-date lists, input SHA-256 hashes, and sensitivity results: `runs/historical_round_spend_extension_20260909/results.json`. Fill ledgers are stored beside it for each distinct funded selection; equivalent cached selections reuse metrics rather than writing duplicate ledgers.
