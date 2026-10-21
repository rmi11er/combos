# NFL: 0.2¢ floor with a price-dependent rise toward 0.5¢

The tested schedule does not yet support replacing flat 0.3¢. It improves a
small, tightly capped historical portfolio, but loses to the baseline in the
unlimited comparison and all three larger-risk-cap comparisons. The unlimited
disadvantage persists after individually excluding every underlying fixture.
Fee assumptions materially change the result.

## Specification

Primary candidate: required NET edge after maker fees per payout contract is
0.2¢ through a Kalshi midpoint-implied combo price of 10¢, then rises linearly
to 0.5¢ at 50¢ and stays there. In dollars:

`h(p) = 0.002 + 0.003 * clip((p - 0.10) / 0.40, 0, 1)`

| Midpoint-implied combo price | Net hurdle |
|---|---:|
| ≤10¢ | 0.200¢ |
| 20¢ | 0.275¢ |
| 30¢ | 0.350¢ |
| 40¢ | 0.425¢ |
| ≥50¢ | 0.500¢ |

The candidate crosses the flat 0.3¢ baseline at approximately 23.33¢.
The endpoints are fixed research scenarios, not parameters optimized on these
outcomes. Additional comparisons: 0.5¢ reached at 40¢ or 60¢; each ramp keyed
to traded combo price; flat 0.2¢, 0.3¢ and 0.5¢.

The primary fair remains the product of selected-leg Kalshi mids. The
midpoint schedule can be evaluated before selecting a quote; the traded-price
version is an observed-price selection sensitivity. All comparisons retain
the original trade prices, quantities, fees, risk identities and settlement
times. The experiment applies a changing admission hurdle; it does not assume
customers execute newly repriced quotes at the same acceptance rate.

## Primary results

23,809 priceable pregame 2–4-leg moneyline YES-taker prints from January 5–18,
2026, involving nine fixtures. January maker fee coefficient 0.035 is the
archived, historically unverified research assumption. No outcome-based
eligibility filter is used; all selected outcomes are known in this archive.

| Policy | Unlimited admitted prints | Unlimited eventual net P&L | Unlimited peak committed cash | Funded fills | Funded eventual net P&L |
|---|---:|---:|---:|---:|---:|
| Flat 0.2¢ | 1,752 | $71,665.78 | $254,140.15 | 45 | −$58.88 |
| Flat 0.3¢ | 1,307 | $62,749.36 | $214,844.57 | 21 | −$29.40 |
| Primary midpoint ramp | 1,325 | $54,940.30 | $224,426.01 | 24 | −$4.51 |
| Traded-price ramp, 10–50¢ | 1,308 | $54,716.47 | $222,928.75 | 24 | −$4.51 |
| Flat 0.5¢ | 841 | $49,831.93 | $158,309.36 | 23 | +$75.55 |

The base funded ledger starts with $10,000, with $100 per-contract, $100
per-combo and $250 per-fixture gross liability limits. It fills whole observed
prints or rejects them; settlement alone releases capital. These are
hypothetical public-print fills, not observed RFQ wins. Unlimited profits
require substantially more capital than the funded account.

Flat 0.5¢ producing more funded fills than flat 0.3¢ reflects chronological
capacity allocation: rejecting some earlier trades leaves room for later
ones. It is not a monotone demand curve. The small funded sample does not
identify flat 0.5¢ as an optimal policy either.

## What the primary schedule changes

Against flat 0.3¢, before capital constraints:

- Adds 154 lower-price prints / 35,209 contracts: $84.90 modeled net edge,
  $256.13 eventual net profit.
- Removes 136 higher-price prints / 22,039 contracts: $80.88 modeled net edge,
  $8,065.20 eventual net profit forgone.
- Net effect: +18 prints, +$4.03 modeled edge, −$7,809.06 realized-outcome P&L,
  and approximately +$9,581 peak committed cash.

The larger historical customer premium at higher combo prices does not by
itself show that the maker must require a higher admission hurdle there. The
removed trades were profitable in this sample. Whether we could instead win
these RFQs at a more profitable quote requires acceptance evidence.

## Capital and fixture sensitivity

Holding capital at $10,000, raise per-contract/per-combo caps together, with
per-fixture cap twice that amount:

| Contract/combo cap | Flat 0.3¢ P&L | Midpoint ramp P&L | Ramp minus baseline |
|---|---:|---:|---:|
| $500 | $158.62 | −$150.63 | −$309.25 |
| $1,000 | $589.93 | $460.13 | −$129.79 |
| $2,000 | $1,393.15 | $1,169.89 | −$223.26 |

For each of the nine fixtures, exclude every combo involving that fixture and
rerun the funded portfolio from the beginning. The primary-minus-baseline
funded P&L difference ranges from −$23.20 to +$91.07. Its full-sample $24.89
improvement is therefore not uniformly robust to removing one game.

In unlimited selection the difference stays negative in all nine fixture
omissions, ranging from −$8,861.27 to −$1,320.38. The largest winning print is
identical under both policies ($19,504.18), so removing it does not change the
−$7,809.06 policy difference. These are influence checks, not independent
replications or confidence intervals.

January 14–18 alone favors the ramp: unlimited selected P&L is $2,416.62
versus $1,424.49 for flat 0.3¢. Those fixtures were already observed in earlier
data; this inspected development subperiod is not a fresh validation sample.

## Fees and fair-source sensitivity

Recompute exact maker fees and reselect trades for each coefficient:

| Assumed maker coefficient | Flat 0.3¢ unlimited P&L | Midpoint ramp unlimited P&L | Difference |
|---|---:|---:|---:|
| 0 | $92,220.70 | $95,217.37 | +$2,996.67 |
| 0.0175 | $97,182.68 | $105,112.43 | +$7,929.75 |
| 0.035 | $62,749.36 | $54,940.30 | −$7,809.06 |
| 0.07 | $25,469.42 | $5,762.72 | −$19,706.70 |

The coefficient is an input to the fee formula, not a flat percentage of
notional. This sensitivity changes both fees and admitted cohorts. Lower
coefficient results prevent treating the main negative finding as independent
of the applicable fee schedule.

At the primary fee assumption, the midpoint ramp also underperforms flat 0.3¢
when admission edge is measured against Polymarket fair (−$6,314.51) and PM75
fair (−$6,051.75). For these comparisons the ramp input remains Kalshi midpoint
price, making the source change in the edge calculation explicit.

## Implication for a demand-based edge schedule

The historical analysis leaves the 0.2–0.5¢ curve as a candidate for prospective
measurement. It does not establish a beneficial production replacement for
0.3¢. Two different targets need evidence: (1) minimum compensation required
for fees, adverse selection and inventory; and (2) how quote acceptance varies
with the compensation requested at each combo probability.

For illustration, with identical size, risk and calibration, moving net edge
from 0.3¢ to 0.2¢ requires 50% more filled contracts to preserve expected edge
dollars; moving from 0.3¢ to 0.5¢ can tolerate a 40% decline. These are arithmetic
break-even conditions, not measured demand elasticities. Conditional markouts
could change both comparisons. This historical study does not have the
corresponding RFQ acceptance or short-horizon forward-markout labels.

## Reproduction and verification

```sh
.venv/bin/python scripts/nfl_edge_schedule_study.py \
  --out runs/nfl_edge_schedule_20260909
```

[Curves and schedule plot](../runs/nfl_edge_schedule_20260909/schedules.png) ·
[All scenario results](../runs/nfl_edge_schedule_20260909/results.json).
Eight compressed replay artifacts retain full decisions, fills, daily
increments and curves for flat 0.2¢/0.3¢ and the two 10–50¢ ramps in funded
and unlimited modes.

The fixed-0.3¢ replay exactly reproduces all archived Kalshi fill records:
21 funded and 1,307 unlimited. All unrestricted fill identities equal the
independently selected schedule cohort; every funded fill passes its hurdle.
Primary recomputed maker fees match the archived fees. Schedule boundary,
cent-to-dollar and inherited guard checks pass. Plot labels and curves were
visually reviewed. Input SHA-256 is in results.json.

A research-local temporary on-disk EventStore is used because the current
core store's periodic file-size check fails for SQLite ':memory:' after 256
events. The existing risk and backtest implementations are otherwise reused;
no runtime policy or production code was changed.
