# CFB fair pilot and repeatable performance report — September 7, 2026

Updated portfolio evaluation: [paired constrained/unconstrained backtester](BACKTEST_EVALUATOR.md)
adds settlement recycling, equity, daily Sharpe/variance and reserve ablations.
Use it for portfolio comparisons; the original allocation ledger below did not
recycle settled capital.

The guarded three-venue blend has a slightly better outcome score in this small
sample, but the fixture bootstrap interval includes no improvement. Stronger
Pinnacle weighting did not improve on the guarded blend. This supports further
shadow validation, not increasing live Pinnacle weight on the strength of this
pilot.

## Scope, history and coverage

Historical access was verified using `pinnacle+30`: the LSU–Clemson probe returned
23,326 records starting August 20, before the September 7 subscription start.
The undelayed `pinnacle` slug returned 403. CFB regular-season tournament 27653
was found through fixture discovery; the live collector remains NFL-only.

The fixed pilot selected 20 September 5 fixtures by a saved hash ordering from
80 fixtures with at least ten existing exact exchange mappings. Selection did
not inspect forecasts or outcomes. The pricing window spans August 31 through
September 6, Chicago time. This is a subset of that week's games, not a full-week
opportunity estimate or a random sample of every RFQ.

Nineteen historical fixture downloads succeeded; one returned 404. Exact
full-game, non-player, half-point or moneyline matching produced 103 leg mappings.
Seventeen fixtures supplied common-cohort evaluation inputs. There were 224
canonical leg/time evaluations after deduplicating complementary team contracts,
at 24 hours, six hours, one hour and ten minutes before kickoff. Period/team-total
history exists in the downloaded feed, but this first pilot uses the already
reviewed full-game exchange join; those extensions are not included in its scores.

Account request count moved from the earlier verified 16 to 17. The one billable
request was fixture discovery; history did not consume monthly quota. The
provided temporary key file was deleted after acquisition.

## Historical-only assumptions

- Missing Polymarket depth equals contemporaneous Kalshi depth, as requested.
  Actual historical depth takes precedence if supplied. Our Kalshi candles also
  lack depth, so both exchanges use explicitly imputed $100/$1,000/$10,000 payout
  capacity scenarios. The central scenario uses $1,000 on each side.
- Polymarket price history lacks bid/ask spread as well. This pilot centers the
  contemporaneous Kalshi raw spread on the Polymarket price, symmetrically clipped
  at probability bounds, then applies each venue's fees separately. This spread
  proxy is an additional research assumption, not observed Polymarket liquidity.
- Retained Kalshi 0.07 and Polymarket 0.05 fee coefficients and archived combo
  series rates are used as historical assumptions. Pinnacle limits are treated
  as USD stake for the sensitivity calculation; provider unit confirmation and
  exceptional-settlement approval are still required for live use.
- The latest active historical state is carried until another update or an
  inactive state. No future state is read. Both Pinnacle sides are reconstructed
  independently; suspensions block, with no fallback to an older active price.
- Pinnacle `createdAt` publication/delay semantics are not yet fully verified.
  The central case adds 30 seconds to archived availability, with zero/60-second
  additional-delay sensitivities. Zero additional delay is an optimistic archive
  scenario, not an assumption that our subscription is undelayed.
- Exchange histories have a 60-second publication allowance. Effective history
  state ages are explicit model assumptions; raw last-update ages remain in the
  audit output. No evaluated minute-history observation passes the production
  15-second exchange-age test. The historical calculation does not loosen that
  forward/live rule or establish upstream feed freshness.
- The forward `PricingService` explicitly rejects `historical_only` or
  `depth_imputed` records. No production imputation fallback was added.

## Fair-value results

Brier scores average squared probability error, first within fixture and then
across fixtures. Lower is better. All models use the same evaluation cohort.

| Model | Fixture-balanced Brier | Difference versus Kalshi |
|---|---:|---:|
| Kalshi only | 0.226309 | — |
| Pinnacle only | 0.226785 | +0.000477 |
| Guarded blend, 20% Pinnacle cap | **0.225913** | **−0.000396** |
| Stronger Pinnacle, 50% cap / 1.5 score prior | 0.226187 | −0.000121 |

The blend's relative improvement is about 0.18%. Its fixture-bootstrap 95%
interval for the Brier difference is **−0.002007 to +0.001135**. All three model
comparisons include zero. These intervals are exploratory: only 17 games on one
slate contribute, and a fixture bootstrap does not capture arbitrary slate-wide
common shocks. Repeated lines/combos do not provide independent games.

The guarded blend remains slightly ahead across the tested depth assumptions.
Increasing Pinnacle's weight does not reliably improve the result. Against later
Kalshi prices, average absolute error is approximately 1.00c for Kalshi alone and
1.17c for the blend; against later Pinnacle prices it is 1.63c and 1.36c. These
source-dependent closing comparisons are diagnostics, not independent proof
that one source is sharper.

[Accuracy and depth-sensitivity plot](../runs/cfb_fair_pilot_20260907/fair_validation.png)

## Combo economics and P&L

Seventy recovered combo definitions met the pilot's mapping/2–4-leg/distinct-game
screen. Sixty-eight pregame public prints involved that cohort. After missing
prior state, inactive history and NO-taker exclusions, **23 YES-taker prints**
were comparable: 22 two-leg prints and one three-leg print. No four-leg print
survived this small common cohort. They total **$577.31 YES premium** and
**$3,573.15 payout notional**; sums below are observed samples, not weighted
full-market estimates.

| Model | Net expected edge at fair point | Net edge at stressed upper |
|---|---:|---:|
| Kalshi only | −$0.89 | −$85.37 |
| Pinnacle only | +$13.42 | −$71.39 |
| Guarded blend | +$9.65 | −$100.29 |
| Stronger Pinnacle | +$11.53 | −$101.82 |

These are signed notional estimates, `quantity × (public YES price − probability)
− maker fee`, before entry filtering. They are not realized P&L. The stressed
upper includes marginal spread/fee/delay uncertainty and the common joint model;
it is not purely a correlation charge.

No print cleared the 0.3c per-share minimum net edge at the stressed upper. Thus
all four strategy ledgers have **zero simulated fills and zero P&L**, with the
$10,000 capital and $100 underlying/$100 combo/$250 fixture limits preserved.
There is no ticket/probability filter or size clipping. The historical allocation
scenario assumes a whole observed print could be filled and never recycles
capital; it does not infer actual RFQ acceptance or creator behavior.

A separately configured rho=0.02 sensitivity also produced zero entries. Its
blend stressed-edge sum was −$81.24, versus −$100.29 at rho=0.05. This is not
evidence of zero opportunity across the market: the mapped sample is tiny and
many profitable-looking public prints cannot be assumed to be available RFQs.

For visual comparison with the example P&L chart, an **unfiltered reference**
assumes buying combo NO at every one of the 23 matched YES-taker prints, with
no entry/risk/capital filters. Its ex-post settled P&L is +$258.49, on $3,009.45
maker cash spent, $577.31 customer YES premium and $3,573.15 payout notional.
This is a separate hindsight ledger, **not performance of the configured algo**.
It cannot establish an attainable return or justify removing its guards.

## Repeatable plots and experiments

The report emits PNG and SVG figures, exact curve CSVs and a provenance manifest:

- [Model edge and observed volume](../runs/cfb_fair_pilot_20260907/performance/model_edge_and_volume.png)
- [Strategy fill/settlement P&L](../runs/cfb_fair_pilot_20260907/performance/strategy_performance.png)
- [Unfiltered public-print reference](../runs/cfb_fair_pilot_20260907/performance/unfiltered_reference.png)
- [Rho comparison](../runs/cfb_fair_pilot_comparison_20260907/model_edge_and_volume.png)

`performance_input.json` is the reporting contract. It contains a run identity,
model/config/data hashes, time window, evaluation rows and an explicit fill /
settlement ledger. An evaluation can move expected-edge and observed-volume
curves; it cannot create executed volume or P&L. Actual, simulated and unfiltered
reference execution bases cannot be mixed within one model ledger.

For maker purchases of NO, cash spent is `quantity × (1 − YES price) + fee`.
Settled P&L is `quantity × (YES price − YES settlement) − fee`; the report recognizes
it at settlement and includes the fee once. Customer YES premium, maker cash
spent and payout face notional are retained separately. Payout notional is not
customer winnings. The plotter also supports fractional settlement values.

Reproduce the central pilot entirely from saved data:

```sh
.venv/bin/python scripts/cfb_fair_pilot.py \
  --config config/cfb_fair_pilot.json \
  --data-run runs/cfb_fair_pilot_20260907 \
  --out runs/cfb_fair_pilot_20260907
.venv/bin/python scripts/performance_report.py \
  --run runs/cfb_fair_pilot_20260907 \
  --out runs/cfb_fair_pilot_20260907/performance
```

For a new hypothesis, copy the research configuration, change the model priors,
correlation ceiling or risk settings, and use a **new output directory**. Keep
production config separate. Compare completed runs without repricing:

```sh
.venv/bin/python scripts/performance_report.py \
  --run runs/cfb_fair_pilot_20260907 \
  --run runs/cfb_fair_pilot_rho002_20260907 \
  --out runs/cfb_fair_pilot_comparison_20260907
```

A future live execution adapter should emit the same reporting ledger from
exchange-confirmed fills and settlements. This report does not implement that
adapter. Changes to the input universe should be compared on a common cohort
as well as separately for incremental coverage; larger plotted edge alone is
not evidence of a better fair.

## Implementation checks and next work

The full suite passes 128 tests, including historical depth precedence,
lookahead/suspension handling, forward imputation rejection, settlement-time
P&L, fee accounting and duplicate/mixed-execution prevention. API fixture data
also exposed a live-adapter bug: status 1 means live, 2 finished, 3 cancelled.
The mapping was corrected and all non-pregame statuses now have regression tests.

Keep the current conservative Pinnacle weighting for forward collection while
validating native freshness, limit units, payoff semantics and actual depth.
Use a larger independently chosen cohort and extend exact historical period/
team-total joins before drawing market-wide opportunity conclusions. Wednesday's
shadow data remains necessary for acceptance, latency and execution validation.
