# Reusable portfolio evaluator — September 7, 2026

The 23-print pilot below is superseded for coverage by the
[all-available CFB week replay](CFB_FULL_WEEK_BACKTEST.md): 61,205 native-priced
prints and 9,511 common three-venue prints, with trade-time P&L attribution.

The chronological backtester runs every fair model twice: funded capital and
canonical concentration limits, then unlimited capital/concentration with the
same entry criterion and quote guard. It is a hypothetical public-print replay,
not measured RFQ execution performance. This supersedes the pilot's original
non-recycling allocation ledger for portfolio comparisons.

## Original pilot artifacts (superseded)

- [Current stressed rule, constrained](../runs/cfb_backtest_20260907/stressed/constrained.png)
- [Current stressed rule, unconstrained](../runs/cfb_backtest_20260907/stressed/unconstrained.png)
- [Point-price diagnostic, constrained](../runs/cfb_backtest_20260907/point_diagnostic/constrained.png)
- [Point-price diagnostic, unconstrained](../runs/cfb_backtest_20260907/point_diagnostic/unconstrained.png)

Each figure now shows retrospective trade-attributed outcome equity, cumulative
accepted-trade model edge, simulated YES premium and payout notional, and committed
capital. Known eventual settlement P&L is assigned to each original trade timestamp;
expected net edge accumulates at the same timestamp. Cash and risk still release
only at actual settlement, and expected edge cannot fund another trade. Its equity legend includes descriptive
annualized Sharpe, sample daily return variance in basis-points squared, net
settled P&L and fill count. JSON summaries additionally include funding needs,
drawdown, unsettled exposure, accepted point/stressed edge and rejection counts.
CSV curves/daily returns/fills and a full-context JSONL decision log accompany
each run. Source data, pricing configuration, evaluator configuration and code
hashes are retained in a manifest. Reusing an output directory with different
input/configuration is rejected.

## Original pilot results (superseded)

The original pilot contained **23 comparable public prints** from preselected September 5
CFB fixtures, repeated across four fair models. Twenty-two prints have two legs;
one has three. These are not 23 total trades across the football week. The
calendar window is August 31–September 6, but the selected trading cohort is one
slate, and its trades and settlements occur on one local calendar day.

Under the current stressed-upper entry rule all four models reject all 23
prices before risk checks. Both portfolio regimes remain at $10,000; variance
is zero and Sharpe is undefined. Removing capital limits alone cannot change
an entry-price rejection.

The point-price diagnostic removes the probability reserves from the entry
test, while retaining actual combo maker fees, the 0.3-cent/share minimum edge,
quote guards and the selected portfolio regime. It changes no forward settings.

| Model | Constrained fills | Constrained net P&L | Unconstrained fills | Unconstrained net P&L |
|---|---:|---:|---:|---:|
| Kalshi | 1 | -$23.61 | 1 | -$23.61 |
| Pinnacle | 10 | -$62.23 | 12 | +$286.84 |
| Guarded blend | 6 | -$69.63 | 8 | +$279.44 |
| Stronger Pinnacle | 8 | -$64.27 | 10 | +$284.81 |

Two NO positions that subsequently won explain the $349.0734 difference for
the blend/Pinnacle models. Their maximum losses were $284.5361 and $768.3205,
each exceeding the $100 underlying allowance by itself. The full observed sizes
are either taken or skipped; no ticket cap or size clipping is introduced.
These results do not justify changing risk limits after observing winners.
The unconstrained blend's peak commitment was only $1,126.71, so this particular
comparison is about concentration limits, not exhaustion of the $10,000 base.

In this original pilot there is one nonzero daily P&L observation among seven days, so every
nonflat curve has descriptive annualized Sharpe of +7.22 or -7.22. This follows
mechanically from `sqrt(365/7)` and does not distinguish model quality. The
blend's daily return variance is 692.72 bp² constrained and 11,155.13 bp²
unconstrained, using P&L divided by the fixed $10,000 reporting base. Dollar
P&L sample variance happens to have the same numerical value at this base.

## What “net edge at stressed upper” means

For customer YES price `c`, quantity `q` and the maker buying NO:

```
expected net edge = q * (c - assumed_combo_YES_probability) - combo_maker_fee
```

The original model-edge diagnostic's bottom plot substitutes the stressed upper probability for the point fair,
then cumulatively sums across **all evaluated public prints**, whether or not
they pass entry. It is an assumption-dependent expected-edge diagnostic, not
realized loss, P&L variance, a confidence interval, or a plotted account value.
The upper probability is adverse because a maker holding NO loses when YES wins.
For example, 100 contracts at a 30-cent YES price, 25-cent stressed probability
and $1 maker fee have $4 net modeled edge. The edge is in actual dollars:
probability differences in cents are divided by 100 before multiplying quantity.
The new portfolio figures instead accumulate edge only on accepted simulated
fills in their second panel. Their bottom panel is committed capital, with
cash released at actual settlement.

The same-print blend reserve audit gives:

| Pricing stage | Cumulative net edge | Prints clearing minimum edge |
|---|---:|---:|
| Point probability | +$9.65 | 8 |
| Weighted raw book upper band | -$11.86 | 0 |
| Fee-expanded weighted band | -$35.86 | 0 |
| Maximum exchange envelope | -$54.37 | 0 |
| Per-leg delay/disagreement padding | -$67.01 | 0 |
| Joint correlation stress | -$100.29 | 0 |

The audit fixes final venue weights while changing interval stages; it is a
decomposition of quoting reserves, not statistical variance attribution. The
raw-book stage includes Pinnacle's bookmaker odds bracket and the historical
Polymarket spread proxy. The latter is imputed, not observed. See
`runs/cfb_fair_pilot_20260907/reserve_audit/per_print.csv` and `summary.json`.

Two implementation choices deserve empirical review. First, after computing
liquidity weights, the guarded blend takes the maximum upper endpoint across
the weighted estimate and both exchange books. A wide, weak exchange can thus
dominate quoting despite little point weight. Second, the three/four-leg moment
bound leaves higher-order dependence unrestricted even when pairwise rho is
zero. Both are conservative ambiguity guards, not calibrated error estimates.
Neither should be loosened solely to obtain a positive backtest.

## Accounting and input contract

`src/combos/backtest.py` consumes normalized per-model opportunities. A pricing
adapter supplies causal `fair_point`, `stressed_upper`, quote permission,
risk multiplier, quantity, observed YES price, fee, canonical contract/fixture/
combo buckets, and eventual settlement metadata. The engine never uses an
outcome for entry decisions. Future models can supply the same contract without
changing allocation, accounting or plotting. The CFB adapter imports completed
fair-model outputs; changing blend weights requires rerunning that fair producer,
not merely changing the portfolio configuration.

Constrained defaults are $10,000 capital, $100 per canonical underlying, $100 per
combo and $250 per fixture. A source-disagreement multiplier can reduce these
caps. Equivalent representations share a contract key. Full combo maximum loss
is charged to each distinct relevant bucket; no unverified hedge offsets are
granted. The generic engine requires a canonical mapping from its adapter—it
cannot infer equivalence from a ticker string.

The maker pays `q*(1-c)+fee`, and receives `q*(1-YES_settlement)` at settlement.
Capital and bucket exposure recycle only when the stored settlement timestamp
plus any configured availability delay is reached. Pending/unknown settlements
retain their cash commitment. Settlement value may be fractional. Every fee is
included exactly once in net P&L. The constrained engine uses the existing atomic
RiskLedger and its centicent risk rounding.

The main equity curve is initial capital plus eventual known net settlement
P&L attributed retrospectively to trade time. It is **not marked to market or
spendable capital**. Unknown outcomes remain explicitly unresolved; they do not
receive invented P&L. Supplied known settlements after the trading window may be
attributed back to their trades; an optional `outcome_as_of` cutoff freezes outcome
availability. The separate cash ledger and funding metrics retain settlement timing.
Daily statistics use trade-day attribution over full local calendar days, include
idle days, exclude partial boundary days, and use sample variance (`ddof=1`).
Trade-day intervals are `[midnight, next midnight)` so midnight trades are included. Sharpe uses zero risk-free return and sqrt(365)
annualization. In the unlimited run $10,000 is a fixed reporting denominator;
actual required funding and any amount above that base are reported separately.

The execution assumption is a full fill at every qualifying observed YES-taker
print. There is no measured RFQ win rate, quote latency or queue model. No
sampling weights are multiplied into positions; weighted tape input is rejected.
A complete selected sub-universe is still not a full-universe portfolio path.
The current small cohort cannot estimate live strategy throughput or Sharpe.

## Reproduce and extend

```sh
.venv/bin/python scripts/export_cfb_backtest.py \
  --run runs/cfb_fair_pilot_20260907 \
  --out runs/cfb_backtest_20260907/opportunities.json

.venv/bin/python scripts/backtest_report.py \
  --input runs/cfb_backtest_20260907/opportunities.json \
  --config config/backtest_stressed.json \
  --out runs/cfb_backtest_20260907/stressed

.venv/bin/python scripts/backtest_report.py \
  --input runs/cfb_backtest_20260907/opportunities.json \
  --config config/backtest_point_diagnostic.json \
  --out runs/cfb_backtest_20260907/point_diagnostic

.venv/bin/python scripts/audit_quote_reserves.py
.venv/bin/python -m pytest -q
```

Create a new output folder per changed input/model/configuration. The historical
and forward adapters retain separate responsibilities: historical depth proxies
remain forbidden in forward pricing. This implementation adds no live execution.

Independent agent reviews produced a [delayed-feed modeling research plan](DELAYED_FEED_MODEL_RESEARCH.md)
and [July-onward MLB validation plan](MLB_HISTORICAL_VALIDATION_PLAN.md). The next
priority is broader cohort-first data acquisition and forward 30-second-window
markouts, alongside calibrated reserves and an independently evaluated delayed
Pinnacle anchor corrected by live exchange innovations. MLB three-venue results
are pending baseball entitlement and data acquisition; they have not been run.
