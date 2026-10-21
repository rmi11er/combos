# July 5 common-model selected-ledger audit

All eight funded/unlimited portfolios pass the independent ledger audit. July 5's unlimited selections are profitable for every exchange-only model, while the original funded portfolios remain near flat. **PM's apparent advantage is concentrated in SD–LAD**: removing that fixture reverses both PM's selected portfolio profit and its paired calibration advantage over K.

## Verification

The exact common intersection has 22,487 prints per model. All 179,896 decisions across four models and two regimes were checked without sampling. Native joins verify YES-taker direction, quantity, price, archived fee and settlement exactly. All prints are 2–4 legs and pregame according to their native scheduled-start proxy; July 5 is the trade date, not the date of every game.

Selection is `q × (observed YES price − model fair) − fee >= q × .003`: **0.3 cents per combo contract, not per leg**. Unlimited decisions match that hurdle and quote guards. Every selected fill maps uniquely to an accepted decision, with identical terms and eventual P&L at trade time; rejected decisions have no fills. Fees are deducted once in P&L and once in the separate model-edge calculation, not twice in either. Selected plus rejected metrics equal the complete common universe exactly.

Funded accepted checks obey retained risk limits and cash availability. This validates stored checks, not an independent second chronological risk replay. The previously identified float-to-cash-ceiling issue recurs: 93 of 430 funded accepted records reserve $0.0001 more than exact NO cost, totaling $0.0093 across the separate portfolios. It is conservative reservation noise, not a fee duplication or explanation of performance. No frozen code was edited.

| Model | Funded fills | Funded net | Unlimited fills | Unlimited net | Unlimited model edge |
|---|---:|---:|---:|---:|---:|
| kalshi | 91 | $38.16 | 603 | $69,809.36 | $3,036.11 |
| polymarket | 114 | $-7.39 | 5,582 | $190,862.75 | $12,005.12 |
| exchange_blend_equal | 105 | $49.43 | 1,748 | $158,971.65 | $5,521.82 |
| exchange_blend_pm75 | 120 | $-61.40 | 2,997 | $211,519.49 | $8,083.99 |

Selling every print on this same common intersection returns +$396,446.089700, compared with +$1,931,852.344200 across the broader 187,774-print native YES-taker universe. Those denominators must not be conflated. These are observed-price hypothetical full fills, not actual RFQ acceptance or execution. Pinnacle history is absent; the maker .035 historical effective-date and cash-account assumptions remain explicitly unverified.

## Selected fixture omissions

The table omits already selected fills containing the largest positive fixture membership. It does not rerun the strategy with freed capacity or admit replacement fills. Membership overlaps and cannot be summed as an additive attribution.

| Regime/model | Largest positive fixture | Membership net | Net after omission |
|---|---|---:|---:|
| constrained/exchange_blend_equal | mlb:26JUL051920SDLAD | $88.08 | $-38.65 |
| constrained/exchange_blend_pm75 | mlb:26JUL062210COLLAD | $52.77 | $-114.18 |
| constrained/kalshi | mlb:26JUL051920SDLAD | $87.93 | $-49.77 |
| constrained/polymarket | mlb:26JUL051920SDLAD | $86.93 | $-94.33 |
| unconstrained/exchange_blend_equal | mlb:26JUL051920SDLAD | $127,619.69 | $31,351.96 |
| unconstrained/exchange_blend_pm75 | mlb:26JUL051920SDLAD | $163,966.33 | $47,553.16 |
| unconstrained/kalshi | mlb:26JUL051920SDLAD | $57,342.06 | $12,467.29 |
| unconstrained/polymarket | mlb:26JUL051920SDLAD | $195,021.17 | $-4,158.42 |

All four unlimited portfolios' largest quantity print is 47,674 contracts, $9,153.408 YES premium and +$8,894.5496 net (trade `03da5d1d-deb6-678f-0ff1-14e3b45f4c4a`). It spans July 5 SD–LAD/BOS–LAA and July 6 PHI–KC/COL–LAD. The funded largest quantities range from 76.56 to 107 contracts. Full IDs, native terms, worst prints, all fixture omissions and exact totals are in verification.json.

## Paired calibration and disagreement

Same exact 22,487 prints/outcomes in every model; lower Brier is better. Scores describe dependent public prints, not independent bets or out-of-sample confidence.

| Model | Equal-print Brier | Quantity-weighted Brier | Weighted fair minus outcome |
|---|---:|---:|---:|
| exchange_blend_equal | 0.13068141 | 0.10238791 | 0.06994974 |
| exchange_blend_pm75 | 0.13059215 | 0.10220606 | 0.06914626 |
| kalshi | 0.13087622 | 0.10276572 | 0.07156613 |
| polymarket | 0.13050822 | 0.10202885 | 0.06834591 |

PM minus K quantity-weighted Brier is **−0.00073687**, favoring PM. It stays negative in 37 of 38 single-fixture omissions; **removing July 5 SD–LAD changes it to +0.00025350, favoring K**. The calibration ranking and PM selected profit thus share a material single-fixture dependence.

| Source-selection subset | Prints | Seller net |
|---|---:|---:|
| both | 477 | $74,555.64 |
| kalshi_only | 126 | $-4,746.28 |
| neither | 16,779 | $210,329.62 |
| polymarket_only | 5,105 | $116,307.11 |

Where PM is more than 0.5 cents below K, PM has better weighted calibration (difference −0.00201873); where PM is more than 0.5 cents above K, PM is worse (+0.00119071). Those directions reverse July 3's descriptive findings. On July 3, both models substantially underpredicted outcomes; on July 5, both overpredict the size-weighted realized settlement frequency. This is a reason to retain fixed directional analyses across a longer dataset and inspect common fixture shocks—not to alternate source preference after observing each day's results.

## Research conclusion and artifacts

The profitable Sunday is encouraging as a development observation, but concentrated PM performance and nearly flat funded results do not establish a live allocation rule. Compare fixed models and capacity policies over all certified July dates, preserving coverage, scheduled-time caveats and actual settlement cash release. Do not choose a Sunday filter or remove SD–LAD retrospectively.

Evidence resides in `runs/morning_research_20260908/july5_selected_audit/`: `verify.py`, hashed native/decision/fill inputs in `verification.json`, `disagreement.json` from unchanged `scripts/model_disagreement_report.py`, and the Decimal four-model calibration workflow/output. Float display comparisons allow $0.000001; native fees/settlements and identities match exactly. No provider calls, August data, plots, prior-artifact modifications, frozen-source edits or surviving background jobs.
