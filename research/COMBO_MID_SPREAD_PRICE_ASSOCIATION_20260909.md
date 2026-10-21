# Historical combo premium versus leg spread and combo price

The retained sample supports a modest positive spread association for MLB and a
very weak spread association for NFL. NFL premium has a clearer relationship
with price; MLB does not support a simple increasing price surcharge. These are
descriptive trade-premium results, not estimates of the optimal quoting margin.

## Sample and definition

415,673 MLB prints across 15 retained July 2026 dates and 402 distinct fixtures;
23,809 NFL prints across 13 active dates within January 5–18 and nine fixtures.
All included prints are priceable pregame YES-taker moneyline combos with 2–4
distinct fixtures. No edge threshold, capital restriction, or settlement/outcome
filter is applied. July 13 and unsaved July dates are absent. August validation
data was not loaded.

Gross seller premium in cents = 100 × (combo YES trade price − product of
selected-leg Kalshi midpoints). Positive values mean the YES buyer paid above
this reference. NO legs use complementary bid/ask orientation. The script
independently reproduces the archived Kalshi fair product for every retained
print. The product assumes independence across fixtures.

Spread is the sum of each selected contract's native ask minus bid. This differs
from the earlier July study's sum of opposite-team ask inconsistencies. A second
width measure propagates prices through the combo: product(asks) − product(mids).
Both are historical quote measurements without executable depth.

## Main contract-weighted results

| Predictor | MLB slope | MLB R² | NFL slope | NFL R² |
|---|---:|---:|---:|---:|
| Summed native leg spread, unadjusted | +0.06437 | 1.107% | +0.01641 | 0.0124% |
| Summed spread, adjusted | +0.14146 | 0.923% partial | +0.06590 | 0.0288% partial |
| Traded combo price, unadjusted | −0.00030 | 0.00285% | +0.02921 | 6.915% |
| Traded combo price, adjusted | +0.01406 | 1.305% partial | +0.05036 | 13.308% partial |
| Midpoint-implied combo price, unadjusted | −0.00348 | 0.381% | +0.01769 | 2.418% |
| Midpoint-implied price, adjusted | −0.00110 | 0.00789% partial | +0.03409 | 5.599% partial |

Each slope is cents of extra gross premium per one-cent increase in the
predictor. Partial R² is the fraction of remaining variation explained after
controls, not total model R² or percentage-point improvement in total R².

Spread controls: cubic midpoint-implied combo probability, categorical leg
count and trade date, log1p time to first game, maximum leg-book age, and trade
quantity. Price controls: summed leg spread, categorical leg count/date, and
the same time/age/quantity terms. No traded-price control is used in the main
spread regression. Trade price is itself a component of premium, so its
association can be mechanical; midpoint-implied price is available before
choosing a quote and is the cleaner candidate input.

Equal-print weighting strengthens the MLB spread relationship: unadjusted
correlation 0.268 and R² 7.16%, versus contract-weighted correlation 0.105 and
R² 1.11%. NFL spread R² remains only 0.50% with equal-print weighting. Thus
spread is more informative about a typical MLB ticket than about all traded
contracts.

## Stability and magnitude

MLB adjusted spread slopes remain positive when omitting each date in turn:
0.1307–0.1480. Restricting every leg to a source age of at most 120 seconds
reduces its partial R² to 0.233% and slope to 0.1017. Restricting total spread
to at most 5¢ reduces partial R² to 0.165%. The relation is weak in the common
narrow-spread region. NFL adjusted spread changes sign under date omission
(−0.0255 to +0.0869) and fixture omission (−0.0382 to +0.1213).

NFL price slopes are more stable under fixture omission: adjusted traded-price
slope 0.0384–0.0625, midpoint-implied-price slope 0.0190–0.0371. These ranges
are influence diagnostics, not confidence intervals. Nine repeated fixtures
cannot establish broad NFL generality.

NFL contract-weighted mean premium by traded-price bucket rises from 0.020¢
at 5–10¢ to 0.203¢ at 10–20¢, 0.401¢ at 20–30¢, and 0.537¢ at 40–50¢.
Corresponding contract-weighted medians are 0.049¢, 0.133¢, 0.217¢, and 0.417¢.
For MLB, medians in the heavily populated 5–40¢ region are approximately
0.11–0.13¢; mean premiums are less monotonic because of the tails.

The MLB 50–60¢ bin has only 145 prints. Its contract-weighted mean premium is
13.577¢ versus median 0.598¢. One 22,900-contract print contributes 43% of bin
quantity: `b52289f4-60d2-441c-7e84-338c14b3705b`, July 9, price 0.533,
archived midpoint product 0.226875, summed spread 2¢, maximum source age
119.72 seconds. This is retained evidence requiring trade/book forensic review;
it should not anchor a fitted high-price quoting rule. No record was removed
from the main fit based on its edge.

## Chronological prediction diagnostic

Fit on the first two-thirds of active dates and evaluate on the final third.
The target is gross observed premium. The 0.3¢ constant below is a gross
prediction reference; it is not equivalent to the existing post-fee entry hurdle.

| Predictor | MLB later-date contract-weighted MSE (¢²) | NFL later-date contract-weighted MSE (¢²) |
|---|---:|---:|
| Constant 0.3¢ | 0.16506 | 0.14768 |
| Earlier-date mean | 0.11100 | 0.11656 |
| Cubic traded price | 0.17625 | 0.30764 |
| Cubic midpoint-implied price | 0.10942 | 0.25750 |
| Spread plus leg count | 0.10937 | 0.11729 |
| Midpoint price plus spread/leg count | 0.11018 | 0.28187 |

MLB test dates are July 23/25/27/29/31; NFL test dates January 14–18.
Ten MLB fixtures cross the split. All three NFL test fixtures also occur in
training. This is a temporal stability diagnostic within development history,
not an independent fixture holdout or untouched validation result.

Flexible price curves do not justify replacing the 0.3¢ hurdle on this evidence.
Predicting the average traded premium and selecting a profit-maximizing quote
are different objectives: the latter also needs maker fees, adverse markouts,
acceptance probabilities conditional on offered price, and inventory cost.
The next edge-function experiment can use sport-specific midpoint probability,
propagated width, and leg count with regularization and held-out evaluation;
the observed coefficients alone do not identify a deployable surcharge.

## Artifacts and reproduction

[Price/spread figures](../runs/combo_mid_spread_association_20260909/price_followup/price_and_spread.png)
show means and medians with sparse-bin counts and a magnified MLB main-price
region. [Spread results](../runs/combo_mid_spread_association_20260909/results.json)
and [price results](../runs/combo_mid_spread_association_20260909/price_followup/results.json)
retain coefficients, weights, omission ranges, coverage, bins, and forward
diagnostics. Compressed normalized observations retain exact trade identifiers.

```sh
.venv/bin/python scripts/combo_mid_spread_association.py \
  --out runs/combo_mid_spread_association_20260909
.venv/bin/python scripts/combo_edge_price_study.py \
  --input runs/combo_mid_spread_association_20260909/observations.csv.gz \
  --out runs/combo_mid_spread_association_20260909/price_followup
```

Validation: unique trade/model and context identities, context/trade timestamp
equality, legal bid/ask bounds, historical availability before trade, selected
midpoint-product parity, and gross edge identity were checked. Independent
full-design weighted least squares reproduces the residualized NFL adjusted
spread coefficient within 1e-9. A known-slope numerical check confirms cents
units. Input hashes are retained. The figures were visually inspected.

Source books are prior candle states with the existing 60-second publication
delay convention, occasionally carried forward. They cannot identify the exact
live spread the maker faced. The retained replay's external-price coverage
also restricts this sample; it is not a census of the entire combo universe.
