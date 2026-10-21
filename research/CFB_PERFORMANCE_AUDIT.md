# CFB performance, fees, pricing and market selection audit

September 7, 2026. This supersedes the prior report's interpretation of low fill
counts and adds the requested $50 premium experiments and market benchmarks.
All P&L below is after the modeled combo maker fee. Known eventual outcomes are
attributed to trade time; actual settlement still controls cash and risk release.
Trading settings have not been changed.

## The strongest result is conditional selection

On the identical 9,511-print cohort priceable by all four models, the currently
known outcomes give the following unrestricted seller comparison:

| Selection | Known-outcome net P&L |
|---|---:|
| Sell every priceable print | +$32,136.96 |
| Prints selected by the point-price blend | −$48,128.06 |
| Prints rejected by that blend | +$80,265.02 |

These reconcile exactly: all = selected + rejected. The all-print set has 243
unresolved prints, selected has 100, and rejected has 143. The all-print total
could ultimately range from −$43,079 to +$41,887 under loose individual-position
outcome extremes. The positive number is a **known-outcome subset result**, not
a guaranteed positive final P&L. Compare the same resolved rows when analyzing
forecast error; do not infer that missing outcomes earned zero.

The selected prints lose under all four point models on this shared cohort.
This supports investigating selection on erroneous fairs: conditioning on an
apparently attractive market-minus-model gap can select cases where the model
understates the customer's win probability. It does not establish that another
maker has a superior fair, that the customer is informed, or that these losses
are statistically independent. Public prints do not reveal other makers' hedges,
inventories, identities, private fees or total account P&L.

The unlimited $50-premium comparison gives a different market backdrop:

| Blend-priced prints with premium ≤ $50 | Prints | Known net P&L |
|---|---:|---:|
| All priceable | 8,295 | −$10,117.29 |
| Selected | 1,601 | −$7,143.97 |
| Rejected | 6,694 | −$2,973.31 |

Thus smaller observed tickets broadly lost money in this captured cohort too.
Filtering large tickets cannot be treated as a universal profitability fix.

## Plots

| View | Artifact |
|---|---|
| Entire available CFB seller universe, all legs/phases, with unresolved-outcome bounds | [Market curve](../runs/cfb_performance_audit_20260907/market_benchmark/market_equity.png) |
| Identical four-model cohort: all prints versus selected versus rejected | [Uncapped selection comparison](../runs/cfb_performance_audit_20260907/common_point_no_cap/unconstrained_selection.png) |
| Same comparison with $50 maximum observed YES premium | [Capped selection comparison](../runs/cfb_performance_audit_20260907/common_point_premium50/unconstrained_selection.png) |
| $50 premium, $10k and concentration limits | [Portfolio curve](../runs/cfb_performance_audit_20260907/point_premium50/constrained.png) |
| $50 premium, unlimited funding/concentration | [Portfolio curve](../runs/cfb_performance_audit_20260907/point_premium50/unconstrained.png) |
| $50 premium, current stressed reservation rule | [Constrained](../runs/cfb_performance_audit_20260907/stressed_premium50/constrained.png) / [unconstrained](../runs/cfb_performance_audit_20260907/stressed_premium50/unconstrained.png) |

Each report now automatically exports its model-specific all/selected/rejected
curves and summaries. Their all/rejected benchmarks have unlimited exposure,
even when selection obeys $10k limits; they diagnose selection and cannot be
treated as funded $10k alternatives. All lines start at the same reporting base,
so **P&Ls**, rather than equity levels, add. Sharpe and daily-return variance are
descriptive known-outcome statistics on seven calendar days.

The entire available CFB benchmark contains 335,947 public prints across both
taker directions. It takes the opposite side of the 298,747 YES-taker prints,
consistently with our seller strategy. It includes all observed leg counts and
game phases, without a fair/edge filter or risk caps. Its 290,041 known-outcome
prints give −$3,166,689.75 net; the remaining 8,706 prints can change the final
sign. Loose total P&L extremes are −$8.378m to +$6.514m. One unresolved combo alone
has about $8.003m YES premium, so this uncertainty is economically substantial.
Full details and subsection results are in [the market benchmark](CFB_MARKET_BENCHMARK.md).

Saturday is a census; other dates contain every retained sampled interval,
not every trade all day. Nothing is multiplied by the old volume-estimation
weight. All curves are hypothetical public-print executions, not observed RFQ
acceptance or the industry's actual equity curve.

## Fees and selling direction reconcile

Our side is economically **selling the customer's YES combo**, represented by
buying NO at `1 − customer YES price`. For q payout contracts, YES price c,
model probability f, settlement y, and combo maker fee F:

```
cash committed    = q(1 − c) + F
realized net P&L  = q(c − y) − F
expected net edge = q(c − f) − F
```

The official CFB combo coefficient is 0.035 in `q × rate × c × (1−c)`, with
account-specific balance rounding. The current exact direct-member fee adapter
reconciles to all saved fills. There is no duplicated leg-fee cash charge or
factor-of-100 conversion error. The uncapped blend is −$45,657.31 gross minus
$2,470.75 fees = −$48,128.06 net on resolved outcomes. Removing fees from these
fixed executions cannot rescue them. See [the fee audit](CFB_FEE_ACCOUNTING_AUDIT.md)
and its official-source links; alternative selection under zero fees would be a
separate experiment.

## The $50 premium experiment

The new reusable setting is `maximum_yes_premium_dollars: 50`. It accepts or
rejects the whole observed print using `quantity × YES price`; it does not clip
quantity. The filter remains active in both portfolio regimes. Public parent
RFQ IDs are unavailable, so it proxies small tickets rather than verifying the
total premium of the original RFQ or order.

| Point model | $10k/risk-limited fills | Known net P&L | Unlimited fills | Known net P&L |
|---|---:|---:|---:|---:|
| Kalshi | 739 | −$574.81 | 10,184 | −$63,241.76 |
| Pinnacle | 321 | −$614.97 | 3,401 | −$13,895.85 |
| Blend | 248 | −$349.97 | 1,601 | −$7,143.97 |
| Stronger Pinnacle | 274 | −$420.30 | 2,308 | −$9,779.65 |

Single-venue coverage differs; use the common-cohort plots for model comparisons.
Constrained portfolios were rerun chronologically, not filtered after the fact.
Removing earlier large prints changes later inventory availability.

For capped unlimited blend, 712 resolved prints earn an average $12.85, while
800 lose an average $20.37. Its quantity-weighted forecast YES win rate is
26.84%, versus 37.14% realized. That 10.30-point residual overwhelms its 0.55-cent
expected net edge per resolved contract. Pinnacle wins more prints than it loses,
but loses more dollars per losing print. Negative results persist among ≤$10
premiums and separately in two-, three- and four-leg subsets.

$50 customer premium is not $50 maker risk. A 448-contract print at YES 9.3c
has $41.664 customer premium but $407.659 maker loss if YES wins. Existing
capital and canonical underlying limits remain necessary.

The 1,512 resolved capped blend prints represent 1,018 combo tickers and 83
fixtures. About 96% of its prints occur Saturday; Baylor–Auburn participates in
471 of 1,601 accepted prints. More executions of shared outcomes do not create
the same number of independent tests. See [concentration and win/loss detail](CFB_PERFORMANCE_CONCENTRATION.md).

## What we actually charge and how spreads should help

The replay's 0.3-cent minimum is a **net edge floor per payout contract**, after
the combo fee. It uses the actual historical public execution price, never
synthetically fills at fair plus 0.3c. Among accepted capped blend prints, the
observed net markup over its point fair has median 0.54c and 90th percentile
1.16c; the quantity-weighted mean is 0.56c. Thus the minimum resembles the lower
part of the accepted market-minus-model distribution, not a validated optimal
commercial charge. It is a fixed research assumption.

The stressed rule is much more demanding: the median **additional dependence
reserve alone** is 11.43c for three legs and 16.49c for four legs, beyond marginal
book uncertainty. Its unrestricted higher-order ambiguity bound is not a
calibrated correlation forecast. This explains much of the zero-entry result.

On the common $50 cohort, raising the point net floor gives the following
in-sample unlimited blend sensitivity:

| Net edge floor | Fills | Known net P&L |
|---|---:|---:|
| 0.3c | 1,601 | −$7,143.97 |
| 1c | 243 | −$1,488.89 |
| 2c | 14 | −$103.88 |
| 5c | 0 | $0 |

The full four-model sweep is retained in `edge_sweep/summary.csv`. Pinnacle has
a small positive result at 5c on 41 prints; this is in-sample sensitivity, not a
selected production policy or evidence that 5c is optimal.

Leg spreads belong in both reference-price uncertainty and quote competitiveness.
For independent selected legs, a useful local sensitivity is
`joint width ≈ sum_i [product of other leg probabilities × leg width_i]`.
Simply adding leg spreads in cents gives the wrong joint scale. Dependence and
source disagreement require separate treatment.

However, our historical PM data does not contain observed bid/ask or depth, and
its price-point midpoint semantics are unverified. The experiment copied Kalshi
spread around a PM price point and imputed exchange depth. It cannot establish
independent PM spread headroom. Moreover, even narrow Kalshi spreads did not
eliminate the observed blend selection losses. [Full pricing audit](CFB_FAIR_PRICING_AUDIT.md).

## Next model work

1. **Measure the fair before optimizing fill rate.** Validate exact payoff rules,
   coherent related markets and out-of-sample probability/markout errors on all
   candidates, then on the selected subset. Historical arithmetic is correct;
   historical information quality remains questionable. Keep Kalshi, PM,
   Pinnacle and simple blends as independent benchmarks. The current stronger
   Pinnacle mixture did not demonstrate better paired calibration.
2. **Use a delayed sharp level plus causal live changes.** Retain Pinnacle as an
   anchor; test shrunk PM/Kalshi innovations since the anchor's verified effective
   timestamp, with actual books, depth, suspension and heartbeat information.
   Copied historical spreads and rejuvenated carried-state timestamps cannot
   validate this forward model.
3. **Separate the reservation price from commercial markup.** Estimate fair,
   execution fee, uncertainty/adverse-selection reserve and incremental inventory
   cost separately. Then choose a quote above that floor using measured acceptance
   versus price. A candidate objective is acceptance probability times expected
   incremental profit, subject to risk limits. The eventual public trade price
   is an evaluation target, not information available before quoting.
4. **Calibrate joint risk coherently.** Replace the uncalibrated worst-case bound
   as the sole competitive pricing rule only after testing a coherent game/score
   model and its forecast errors on held-out slates. Simulate shared game outcomes
   once per scenario and settle all overlapping combos consistently.
5. **Collect shadow acceptance evidence.** Record original RFQ size, own quote,
   exact books and times, reprices/cancellations, acceptance, private fees and
   subsequent markouts. Maintain creator behavior separately; public repeated
   prints alone do not establish toxicity. These results support shadow diagnosis,
   not confidence in the current model for live capital.

## Reproduction and verification

Use `scripts/backtest_report.py` with either premium50 config for paired reports.
It automatically emits selection comparisons. `scripts/backtest_edge_sweep.py`
tests declared edge floors without synthesizing executions at different prices.
`scripts/cfb_market_benchmark.py` collects the broad seller outcome benchmark;
`scripts/market_benchmark_report.py --run runs/cfb_performance_audit_20260907/market_benchmark`
renders the whole-universe view. Agent audit scripts and all inputs are linked
in the individual reports. Run `python -m pytest -q`: 179 tests pass.

Checks cover premium-boundary behavior, whole-print filtering in both regimes,
continued liability limits, accepted/rejected P&L reconciliation, unknown
outcomes, causal funding and retrospective attribution. All 90,100 saved model
evaluations passed the arithmetic audit; there were no detected price-side or
declared-availability violations. Full benchmark rows and right-edge curve
totals reconcile. Manifests retain input/config/code identity. Passing these
checks validates mechanics under stated assumptions, not profitability.
