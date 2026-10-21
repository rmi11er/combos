# Exact-spend demand and same-game portfolio screen

## Outcome

Exact $10 spend is a persistent feature of the captured NFL request flow, and same-game combinations are a substantial opportunity set. Some structural payout offset is demonstrable in hypothetical portfolios, but neither profitable joint pricing nor acceptance-conditioned risk reduction is established. **Same-game RFQs are now included in this research workflow; the production scope filter remains unchanged.** No quotes or orders were sent.

Completed work: multi-window request analysis, exact-spend cohorts, scalar-safe payout-bound solver, volume/fill-selection stress tests, candidate-dependent spend sizing and an expanded flat-arm dry run. The next implementation target is a small score-based same-game joint model, not blanket removal of the filter.

## Expanded coverage

Five retained capture windows on September 9 span approximately 12.6 minutes of observed NFL request traffic, distributed between 08:02 and 13:17 UTC. Archive folder names are not authoritative timestamps; one is named September 10 but contains September 9 events. The study uses event timestamps and hashes all archive chunks.

There are 61,773 NFL-containing RFQs and **38,464 NFL-only RFQs**, with no duplicate RFQ IDs across these windows. Of NFL-only requests, **22,738 (59.1%) contain repeated legs from an NFL fixture**. Of these, 17,818 involve a single game and 4,920 combine a same-game component with other games.

Across windows, same-game shares range from 52.6% to 66.7%; exact $10 shares range from 49.1% to 51.3% of NFL-only requests. This is stronger replication than the original two-minute sample, but it remains short-window, one-day data. Do not extrapolate request throughput to executed volume or revenue.

## Exact-spend cuts

Denominator: all 38,464 NFL-only RFQs, including fixed-quantity requests.

| Requested spend | RFQs | Share | Creator IDs | Same-game share | Median legs |
|---|---:|---:|---:|---:|---:|
| $5 | 1,322 | 3.4% | 259 | 54.4% | 6 |
| $10 | 19,084 | 49.6% | 2,024 | 62.4% | 5 |
| $20 | 1,102 | 2.9% | 142 | 40.1% | 4 |
| $50 | 572 | 1.5% | 106 | 51.6% | 3 |

The four exact amounts account for **22,080 requests (57.4%)**. Other spend amounts account for 10,056 requests; 6,328 are fixed-sized or have no target-cost field. Exact amounts are matched as decimals: $4.9999 is not classified as $5. Requested-budget sums in the JSON are repeated requests, **not handle**.

Two repeat-traffic checks are provided:

- First chronological request per creator–ticket: $10 remains 54.9% of observations, but this view discards later budget changes.
- First request per creator–ticket–size: preserves changed spend/contract quantities; $10 remains 45.1%. This is the better companion view when studying denomination itself.

The largest creator supplies 22.5% of raw $20 requests and 24.7% of raw $50 requests, versus 4.9% of $10 requests. Round spend is not a verified retail label. App defaults, automation and repeat submissions remain plausible mechanisms; acceptance rates and toxicity cannot be inferred from denomination alone.

## Does high volume create usable offset?

### What was tested

Each requested ticket is represented by its actual market tickers and YES/NO selections. A market's settlement is allowed anywhere in [0,1]; NO is its complement. The solver maximizes a conservative upper bound on aggregate ticket payout using the fact that a product of nonnegative factors no greater than one cannot exceed any of its factors.

This captures exact same-market complementary exposure without assuming independence or binary-only settlement. It does not infer equivalence between different tickers, score relationships or player-stat dependence. Solver dual multipliers are repaired to obtain a conservative upper certificate; failure falls back to the sum of individual maximum payouts. All runs succeeded.

Portfolios contain one hypothetical fill per first chronological creator–ticket. Two weighting scenarios are used: one contract per ticket, and quantities proportional to requested budgets at a hypothetical common price. **Neither is actual inventory.** Budget weights are not actual contract quantities when prices differ. The bound measures gross payout exposure, not net loss, capital relief, expected PnL or variance.

### Results

| Hypothetical portfolio | Tickets | Reduction from summed maximum payouts certified by the relaxation |
|---|---:|---:|
| All same-game, one contract each | 9,188 | 14.18% |
| Spend-sized same-game, budget-weighted | 7,039 | 6.94% |
| Exact $5/$10/$20/$50 same-game, one contract each | 5,706 | 13.81% |
| Exact-spend same-game, budget-weighted | 5,706 | 14.23% |

These are **conservative reductions for the specified hypothetical portfolios**, not an upper limit on all possible diversification. The residual upper bound is not proven achievable. More offsets might become demonstrable with verified cross-market payoff constraints, but this study cannot grant them.

Volume alone does not rapidly diversify the observed mix: the all-same-game unit-contract reduction is 12.41%, 12.10% and 14.18% at the first quarter, half and full chronological sample. The corresponding budget-weighted reductions are 5.70%, 5.84% and 6.94%.

Fill-selection stress, with fixed seed and no claim to estimate actual fill rates:

| Retained hypothetical fills | Tickets | Certified reduction |
|---|---:|---:|
| Independent random 10% sample | 960 | 11.98% |
| Independent random 50% sample | 4,532 | 14.29% |
| Only tickets whose legs are all YES | 6,965 | 0% under these constraints |

The last case demonstrates a failure mode, not a forecast: complementary requests help only if the complementary exposures actually execute. These constraints cannot certify an offset in all-YES flow, although other verified game relationships might. Of raw same-game leg selections, 119,365 are YES and 17,104 are NO. Only 219 of 1,366 market atoms appear on both sides.

Equal spend is also not equal hedge size. Before fees, $10 buying YES at 10c gives 100 contracts; $10 buying NO at 90c gives about 11.11 contracts. The positions do not offset one-for-one. Profitability requires a correct joint fair even if payout exposure is reduced.

**Decision:** some offset potential exists, but these results do not support automatically relaxing risk because requested volume is high. Credit only verified existing positions and binding commitments, with candidate-dependent quantities and stressed joint payoffs. Do not credit hoped-for future requests or fills. Exchange cash-collateral credit is explicitly zero in these artifacts.

## Spend sizing: implementation and dry-run progress

Current Kalshi documentation says target spend normally includes requester fees, while `target_cost_excludes_fees=true` uses principal-only sizing. The exchange returns side-specific contract counts on the quote. Those returned counts, not an inferred fixed quantity, are the reconciliation target. [RFQ documentation](https://docs.kalshi.com/getting_started/rfqs)

`research_spend_risk.target_size` computes the maximum 0.01-contract quantity under supplied requester fee and balance-precision assumptions. It checks the budget and that the next quantity increment would exceed it. Principal-only mode is supported separately. It uses the existing fee engine, assumes one full fill and no prior rounding accumulator, and never submits an order.

For illustration, a $10 fee-inclusive budget under a **hypothetical** 0.07 quadratic requester fee coefficient and $0.0001 balance precision gives:

| Seller YES ask | Modeled contracts | Total requester debit |
|---|---:|---:|
| 5c | 187.52 | $9.9996 |
| 10c | 94.07 | $9.9997 |
| 25c | 38.00 | $9.9988 |
| 50c | 19.32 | $9.9981 |

The coefficient is not 7% of stake. This is not verified account pricing. None of the 61,773 retained NFL-containing RFQs explicitly carries the fee-exclusion flag; absence was not retroactively asserted to prove historical fee mode. The dry runs explicitly assume fee-inclusive mode.

The expanded distinct-game demand dry run processes **all 617 previously excluded spend-sized priceable RFQs**. It constructs **3,702 candidates**: 617 requests × three net-hurdle arms (0.2c/0.3c/0.5c) × two requester fee scenarios (0 and 0.07). Every arm recomputes quantity from its own native-grid price; maker fees are then evaluated separately. All 3,702 candidates pass budget maximality and their modeled after-reserve minimum-profit checks.

These remain retrospective candidates, not prospective assignments or executable recommendations. The archived fair, sampled grid and zero non-uncertainty reserves remain research assumptions. Requester fee terms, fee mode, balance precision and exchange-returned counts require verification. There are no quote-created/accepted/executed messages in the scanned archives with which to reconcile counts or estimate elasticity.

## Same-game admission path

Kalshi combos can have fractional settlement when a player does not participate; they are not universally canceled or reduced to a binary ticket. That is why generic redundant-leg simplification and binary-only hedge credit are unsafe. [Combo settlement documentation](https://help.kalshi.com/en/articles/13823820-combos)

The study routes same-game requests to `same_game_joint_review`, retaining features while setting `quote_eligible=false`. The existing `same_fixture_joint_model_required` production guard is unchanged.

First tractable cohort: **2–4-leg NFL same-game-containing tickets restricted to moneyline, spread and total families**. There are 2,584 raw requests, including 2,340 single-game tickets. Of these, 1,368 request exact $5/$10/$20/$50 spend:

| Spend | 2–4-leg score-based same-game-containing requests |
|---|---:|
| $5 | 97 |
| $10 | 1,088 |
| $20 | 67 |
| $50 | 116 |

Do not confuse “no recognized player prop” with “score-only”: 2,807 requests pass the former screen, but only 2,584 have exclusively the explicit score-market families. The remainder needs classification.

This is a **joint-model development queue**, not a permitted live pilot. Before admission:

1. Canonicalize each market into a reviewed payoff on game scores, with tie, cancellation, reschedule and scalar exceptions retained.
2. Fit and validate a score-joint distribution against contemporaneous moneyline/spread/total quotes; validate joint calibration on separate slates. A product of marginal prices is not a substitute.
3. Reconcile each candidate's spend quantity to exchange response data, with current fee terms and precision; use actual maker cash costs separately.
4. Compute incremental payout/loss risk against actual open positions and binding obligations. Check adverse game states and counterparty-conditioned fills, not just unconditional covariance.
5. Preserve per-game and cash limits, hedge-liquidity checks and cancellation/revalidation controls. A risk reduction is not exchange collateral relief.
6. Add prospective exposure, acceptance, execution and independent markout evidence. Only then consider a narrow, explicitly enabled same-game policy.

Player props are the larger next layer: 9,719 same-game requests have 2–4 legs and recognized props; another 10,212 same-game requests exceed four legs. They require player-stat joint modeling and settlement review beyond the score-only starting cohort.

## Reproduction and verification

```sh
.venv/bin/python scripts/spend_same_game_study.py --out runs/spend_same_game_study_20260909
.venv/bin/python scripts/spend_demand_candidates.py --out runs/spend_demand_candidates_20260909
.venv/bin/python -m pytest -q tests/test_research_spend_risk.py tests/test_parlay_preference_study.py tests/test_demand_experiment.py tests/test_quote_policy.py
```

The study supports `--captures` for additional saved capture names; it makes no network requests. Outputs include raw feature records, per-window and per-spend tables, prefix/fill-selection risk screens, sizing scenarios and the candidate ledgers. Requester IDs remain local.

89 targeted tests passed. Tests cover exact denomination boundaries, fee-inclusive/principal-only sizing, both account precisions, budget maximality, aligned exposure, asymmetric contract quantities, complementary branches and scalar settlement with repeated or contradictory legs. The real-data audit checks every generated candidate's size and modeled profit condition. All 15 risk-screen optimizations succeeded. No production source/configuration or live filter was modified.
