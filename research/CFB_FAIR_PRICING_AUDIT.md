# CFB fair pricing audit — September 7, 2026

The saved fair calculations are arithmetically consistent. The evidence does
**not** establish that the resulting probabilities or our quote reserves are
well calibrated. The major concerns are the quality of historical price inputs,
selection on apparent edge, and an uncalibrated dependence bound that makes
three- and four-leg reservation prices much wider than their point forecasts.

This audit uses all saved contexts, not just losing trades. No production code,
pricing configuration, input selection or live orders changed. The diagnostic
script is `scripts/audit_cfb_fair_pricing.py`; outputs are under
`runs/cfb_performance_audit_20260907/fair_audit/`.

## What is actually charged

For a customer YES price c, maker purchase of NO, quantity q and estimated joint
YES probability p:

```
expected maker profit = q * (c - p) - combo maker fee
realized maker profit = q * (c - YES settlement) - combo maker fee
```

The backtest observes somebody else's historical c and tests whether that price
clears the selected reservation rule. It does not replace c with our fair plus
0.3c. It also does not demonstrate acceptance of a quote that we would have posted.
The 0.3c is a configured **minimum net edge per payout contract**, after the
combo maker fee, rather than the entire customer-facing markup. For example,
a fair near 25% with a 0.035 maker coefficient requires approximately 0.97c gross
markup to leave 0.3c net edge, before any uncertainty or dependence reserve.
Actual quantity, price grid and rounding must be applied to a real quote.

Underlying taker fees widen the evidence bands and affect venue weights. They
are not also paid on hypothetical underlying trades. No such second fee debit
appears in these replay economics. A future hedge would require its own explicit
cash costs. Multiplying by q is correct: these are dollar notional edges, not
unscaled cents or a percentage of the customer's YES premium.

## Arithmetic and mapping checks

| Check | Observations checked | Result |
|---|---:|---|
| Kalshi point equals raw bid/ask midpoint | 174,330 leg occurrences | Exact agreement |
| Pinnacle point equals opposing-odds proportional de-vig | 25,581 leg occurrences | Exact agreement |
| Blend point equals weights × native historical source points | 24,577 leg occurrences per blend | Exact agreement |
| Venue weights sum to one | 24,577 per blend | Error at most 2.23e-16 |
| Selected YES/NO probabilities multiply to saved combo point | 90,100 model evaluations | Exact agreement |
| Combo maker fee matches current direct-member single-fill adapter | 61,205 distinct prints | Exact agreement |
| Native outcome label, spread sign, full-game period, non-player flag | 1,126 mapped payoffs | No mechanical mismatches |

No selected Pinnacle state was inactive, available after its decision under the
30-second archive allowance, or after the configured kickoff-minus-60-second
cutoff. Kalshi source availability also did not exceed decision time under its
60-second publication allowance. The native selector uses outcome 1 for the
first fixture participant and outcome 2 for the second, with the native home
handicap converted to the selected team's winning-margin threshold. Total YES
selects Over at the exact half-point line. NO legs complement the entire interval
before multiplication.

These checks validate the saved implementation under its declared input
semantics. They do not independently establish that vendor timestamps reproduce
live availability, that a thin quote is informative, or that all exceptional
settlement rules are interchangeable. Current-account fee rounding depends on
membership precision and per-order accumulators; the exact match here is to the
single-fill direct-member assumption, not proof of each historical participant's
fee account. [Kalshi fee rounding](https://docs.kalshi.com/getting_started/fee_rounding).

## Historical Polymarket data is not an observed order book

Our retained Polymarket history supplies `(timestamp, price)` points. It contains
neither historical bid/ask spread nor top-of-book depth. The endpoint's official
description identifies historical price data but does not establish that every
returned price is an actual bid/ask midpoint. Therefore the correct label is
**historical price point, midpoint semantics unverified**.
[Polymarket price-history endpoint](https://docs.polymarket.com/api-reference/markets/get-prices-history).

Polymarket separately explains that its displayed price generally uses the
midpoint but can use the last trade when the spread exceeds 10c. That is not
sufficient evidence that the history endpoint follows the identical display rule.
[Polymarket displayed-price explanation](https://help.polymarket.com/en/articles/13364488-how-are-prices-calculated).

For this historical experiment, the Kalshi raw spread is centered on the PM
price point, clipped near 0/1, and then widened using PM's fee coefficient. Both
exchange depths are imputed at $1,000 payout capacity per side because these
Kalshi candles also lack depth. Consequently PM's copied spread is **not a second
independent observation of pricing room**, and our liquidity weights are proxy
scenarios. Live/shadow evaluation must use actual maintained books and sizes.

Median effective venue weights across the three-venue leg occurrences were:

| Model | Kalshi | Polymarket | Pinnacle |
|---|---:|---:|---:|
| Base blend | 27.35% | 52.66% | 20.00% |
| Stronger Pinnacle | 17.14% | 32.91% | 50.00% |

Pinnacle commonly hits its cap. These mixtures reflect priors, imputed depth,
fee-expanded widths and fixed effective ages; they are not estimated venue
forecast precision. The larger Pinnacle prior did not improve the paired
calibration scores in this sample.

## Price age versus feed health

In the three-venue contexts, median last-state ages were approximately 97 seconds
for Kalshi, 91 seconds for PM and 2,932 seconds (49 minutes) for Pinnacle. The
Pinnacle 90th percentile was 6.52 hours and its maximum was 71.34 hours.
Nevertheless, historical weighting assigns every carried Kalshi/PM observation
an effective age of 60 seconds and every Pinnacle observation 30 seconds.

This is the previously disclosed assumption that an active state stays current
until updated or suspended. A long last-price-change age alone does not prove
staleness. But the replay cannot establish the upstream snapshot/heartbeat health
that would justify treating that state as freshly verified. It does **not** test
production freshness behavior: none of the 24,577 three-venue leg occurrences
passes the production-style 15-second exchange-age diagnostic. That is expected
with minute history and its publication allowance, not a reason to weaken the
live requirement.

OddsPapi documents `createdAt` as archive-record creation time, not a verified
end-to-end availability guarantee for our delayed subscription. The extra
30-second allowance is causal relative to the chosen archive interpretation;
the actual delay semantics still need provider/forward validation.
[OddsPapi history fields](https://oddspapi.io/en/docs/get-historical-odds).

## The dependence charge is the main three-/four-leg obstacle

The blend's final marginal upper is the maximum of its weighted upper and both
exchange upper endpoints, plus padding. A low-weight wide source can therefore
control the reservation bound. Relative to the weighted upper, that envelope
adds a median 0.875c per leg in the base blend, and 0.922c in the stronger blend.

Across all available blend combo evaluations:

| Legs | Median marginal reserve above product point | Median additional dependence reserve |
|---|---:|---:|
| 2 | 3.23c | 1.24c |
| 3 | 2.62c | 11.43c |
| 4 | 1.92c | 16.49c |

These are separate medians, not a median total. Marginal reserve includes the
fee/margin bands, exchange envelope and padding. Dependence reserve is the
additional difference between the moment-bound upper and the product of marginal
uppers. The 0.3c minimum net edge and combo maker fee come afterward.

For three/four legs, the moment model leaves higher-order dependence unrestricted
within pairwise bounds. Even pairwise independence does not imply joint
independence. This makes the result a worst-case ambiguity bound, not a measured
correlation charge or confidence interval. Zero external-model entries at that
bound do not show zero market opportunity; they show that our present reservation
policy is incompatible with these observed prices. Calibrate a joint model and
its uncertainty separately rather than lowering rho until trades appear.

## Calibration across underlying contracts and combos

Underlying evaluation keeps the earliest observed decision per canonical
payoff/hour/model, then averages within payoff and fixture. Complementary
full-game moneylines and half-point spreads share the same economic key. The
paired set requires all four models at the originating decision. This is an
observed-flow evaluation cohort, not a randomly sampled forecast experiment.

| Model | Fixture-balanced Brier, common 344 payoffs / 90 fixtures | Unique-combo-balanced Brier, common 5,261 payoffs |
|---|---:|---:|
| Kalshi | 0.229652 | 0.141045 |
| Pinnacle | 0.230664 | 0.141650 |
| Base blend | 0.230338 | 0.141271 |
| Stronger Pinnacle | 0.230395 | 0.141384 |

Lower is better. These small differences do not demonstrate a sharp-feed
improvement. Reused fixtures and repeated hourly forecasts are dependent;
5,261 distinct combo payoffs are not 5,261 independent outcomes. No significance
or stable Sharpe claim follows from this table.

For the blend, the unique-combo-balanced forecast averages 21.38% versus a 23.47%
realized YES rate. Quantity weighting changes the picture because trade sizes
vary considerably. All supplied known settlements, including settlement after
the trading window, give:

| Model / selection | Quantity-weighted forecast | Quantity-weighted YES outcome | Hypothetical settled maker P&L |
|---|---:|---:|---:|
| Blend / all public prints | 16.89% | 15.83% | +$32,136.96 |
| Blend / point-edge entries | 42.45% | 54.49% | −$48,128.06 |
| Pinnacle / all public prints | 16.71% | 15.72% | +$37,038.58 |
| Pinnacle / point-edge entries | 34.61% | 40.05% | −$34,107.11 |
| Stronger Pinnacle / point-edge entries | 39.51% | 48.57% | −$46,048.22 |

The blend's point-entry subset expected +$3,406.29 on the known-settlement rows,
but realized −$48,128.06 under the public-fill assumption. Its adverse forecast
residual is 12.05 percentage points by quantity and 14.60 points without quantity
weights. This supports investigating conditional selection on noisy fairs; it
does not by itself prove informed creators or a persistent 12-point bias.
All these P&Ls are unconstrained public-print counterfactuals, not achievable
$10,000 strategy returns. Window-end cash equity is a separate measurement.

## What observed spreads can tell us

Kalshi's median raw leg spread was 1c; its 99th percentile was 14c and maximum
96c. Very wide markets can create unreliable midpoints, but thin/wide books are
not the entire explanation. Restricting blend trades to maximum Kalshi leg spread
of 2c still leaves point-entry P&L of −$41,184.15. In that stratum the observed
public gross markup over model fair averaged 0.478c without quantity weights;
selected trades' quantity-weighted adverse outcome residual was 13.45 points.

For the blend, the 2–5c *joint marginal band* stratum had +$6,906.53 point-entry
P&L, whereas the 5–10c stratum had −$53,857.71. These are exploratory diagnostics,
not threshold recommendations: band width depends on leg probabilities, leg
count and fixture mix, and the groups were examined after outcomes were known.
The full spread, band and source-age strata are retained in `quality_strata.csv`.

A separate severe Kalshi-only failure illustrates why source support matters:
repeated NCCU/ETSU first-half combos sold YES for 3.8c while both archived leg
books were 4c/15c, giving a 0.9025% product midpoint; those combos resolved YES.
The pipeline reproduced the raw quotes correctly. Historical depth is absent,
and this period pair has no three-venue full-game pricing support. It is evidence
to investigate unreliable books and concentrated unusual flow, not an isolated
example from which to recalibrate the full-game Pinnacle blend.

For forward pricing-room research, retain actual K/PM bid, ask, size, spread and
health separately, plus fee-expanded bounds and the resulting joint band. Compare
public/observed RFQ prices with the generated quote, model point, reserves and
realized markouts. A broad input band describes uncertainty; it does not tell us
that customers will pay its upper endpoint. Acceptance at our own proposed
markup needs quote-response evidence, with decision-time source context and
later labels kept separate.
