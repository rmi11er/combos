# Improving combo market making with a delayed sharp anchor

Research proposal, September 7, 2026. This document changes no production policy.
The original 23-print pilot is superseded by the
[all-available CFB replay](CFB_FULL_WEEK_BACKTEST.md), with 61,205 eligible prints
and 9,511 common four-model prices. The larger replay still requires market
quality checks, complete outcomes and held-out calibration before it can
establish a profitable quoting policy.

## What the existing implementation tells us

`src/combos/weighted_fair.py` estimates the point using spread, depth, freshness
and venue priors. But its final upper endpoint is the maximum of the weighted
upper and **both** exchange upper endpoints, plus padding. Consequently a wide,
low-weight exchange can determine the reservation price even when it barely
moves the point estimate. In historical CFB, Polymarket spread is additionally
imputed from Kalshi, so a sensitivity assumption can influence this envelope.

`src/combos/joint_pricing.py` then maximizes joint payout under marginal intervals
and pairwise moment ceilings. For three and four legs, higher-order dependence
is unrestricted. Even zero pairwise correlation does not imply independence:
three 50% Bernoulli variables can be pairwise independent and all succeed with
probability 25%, versus the independent product of 12.5%. This is a legitimate
worst-case ambiguity bound, but it is not an empirically calibrated forecast.
Reducing rho alone will not remove this source of conservatism.

These observations explain why the point model can show modest positive edge
while the stressed reservation price rejects every observed print. They do not
establish that the stress guard should be removed or that an RFQ creator would
accept a more expensive quote. The live engine proposes a price; a public-print
replay asks whether another participant's historical price met our threshold.
Those are different experiments.

## Separate five quantities before tuning anything

1. **Settlement probability:** a point estimate of the precise canonical payoff.
2. **Fees and bookmaker margin:** explicit trading friction and an explanation
   for why a visible price may differ from latent fair. Exchange fee expansion
   remains part of the observation model, as requested; it is not automatically
   a confidence interval or a cash expense incurred on every underlying leg.
3. **Forecast uncertainty and delay:** uncertainty about the current probability,
   conditional on available observations, latency, market family and news state.
4. **Dependence:** the joint distribution of distinct outcomes, including both
   event dependence and shared errors in marginal forecasts. Different fixtures
   do not eliminate the second form.
5. **Execution and inventory costs:** actual combo maker fees, conditional adverse
   selection, capital holding time and incremental portfolio concentration.

For maker purchases of NO against a customer YES price c, expected P&L is
`q * (c - p_joint) - actual_combo_fee`. Raising `p_joint` lowers expected P&L.
Underlying taker fees affect the evidence for fair or the cost of an explicit
hedge; do not deduct three venues' hypothetical leg fees again as executed costs.
Every decision should log the point and each reserve separately, together with
its units and whether it is estimated, assumed or a hard operational guard.

Polymarket currently documents a sports taker coefficient of 0.05 in
`shares * rate * p * (1-p)`, zero maker fees, and five-decimal fee rounding.
Read each market's parameters and archive the effective version; today's schedule
is not evidence of the fee in July. Our Kalshi fee adapter and actual combo fee
metadata must likewise remain distinct from historical coefficient assumptions.
[Polymarket fee documentation](https://docs.polymarket.com/trading/fees).

## Candidate models, ordered by research value

### A. Static benchmarks and a calibrated observation model

Keep Kalshi, Polymarket, de-vigged Pinnacle, equal weights, the current guarded
blend and a fixed sharp-heavy blend on the same decisions. First establish
whether any added complexity beats these benchmarks out of sample.

Treat fee-expanded books as noisy bands in which correction may not pay for
arbitrage. Do not replace the current maximum envelope with a naive intersection:
latency, payoff differences and heterogeneous constraints can make even apparently
identical books disagree. Test a robust latent-probability estimate whose venue
error scale is calibrated from spread, usable size, freshness and subsequent
forecast errors. A spread/depth proxy is an initial feature, not an estimate of
statistical precision. Pinnacle maximum stake is likewise a capacity proxy, not
resting exchange depth, and requires verified currency and unit conversion.

Estimate source residual covariance rather than pretending three quotes are
independent observations. A shrunk linear blend is a useful first implementation;
a nonlinear state-space model is a later candidate only if simpler models fail.
The belief that Polymarket is sharper should remain a testable prior, not an
invariant derived from fees or access policy. For Pinnacle, compare proportional
versus alternative de-vig methods on held-out favorite/longshot calibration.

**Falsification:** the added model must improve fixture/day-clustered probability
scores or independent future-price errors, and subsequently conditional net
markouts, on a frozen holdout. Increased quoted edge alone does not qualify.

### B. Delayed Pinnacle anchor plus live exchange innovation

This is the most useful next modeling experiment. A 30-second-old sharp quote
can remain a useful level estimate while the live exchanges convey changes
since its information timestamp. In log-odds coordinates, a simple candidate is:

```
z_corrected(t) = z_pinnacle(s)
                 + beta_pm * [z_pm(t) - z_pm(s)]
                 + beta_k  * [z_k(t)  - z_k(s)]
p_corrected(t) = logistic(z_corrected(t))
```

Here `s` is the verified effective information time of the delayed snapshot,
not an unchanged price's last-change time. All records used must already be
available to the strategy at t. The baseline exchange state at s is constructed
causally; missing state makes this correction unavailable. Probabilities near
zero/one need a declared numerical clipping rule. Coefficients require shrinkage
because the live innovations are strongly related; simply adding both moves
would usually double-count common news.

An alternative with only one coefficient uses a quality-weighted live exchange
consensus innovation. Start with frozen beta values 0, 0.5 and 1 as transparent
research scenarios; estimate a beta only on earlier dates. Do not select the
winner on the evaluation period. A sharp-heavy anchor can then be blended with
current live levels using an uncertainty estimate that expands over the blind
window. Live exchange changes reduce staleness; they do not make the delayed
subscription equivalent to an undelayed feed.

Distinguish disagreement regimes using information available now:

- Both healthy exchanges move together against the anchor: likely new common
  information; test correction plus a temporary reserve/cooldown.
- Only one thin exchange moves: possible microstructure noise; test lower weight
  for that innovation while retaining a disagreement flag.
- A source suspends, mapping changes, depth disappears or health is unverifiable:
  block affected quotes; a model should not repair missing operational evidence.

Repeatedly polling cannot reveal a provider's hidden 30 seconds. Use live moves
to invalidate or widen local quotes immediately; coalesce subsequent refreshes
through the shared cache and rate limiter. The RFQ path must never wait on HTTP.

**Falsification:** compare next-available Pinnacle and leave-one-source-out
5/30/120-second markouts against static blends, by quiet/moving regime and time
to kickoff. Future Pinnacle is an evaluation target only. Also score eventual
outcomes because predicting a later bookmaker quote is not proof of true fair.
Reject an innovation correction that overshoots transient exchange moves or
fails delay/clock-offset sensitivities. A minute-candle historical dataset
cannot resolve a 30-second response strategy; this experiment requires the
forward event archive or history with adequate timestamps and availability.

### C. Calibrated reserves and joint probability

Keep the current worst-case model as a reported stress benchmark. Alongside it,
test reserves learned from conditional forecast errors, with pooling across
similar market families when individual cells have little data. Delay, spread,
venue disagreement, time to kickoff and feed health should explain the reserve;
leg count alone should not determine an arbitrary repeated surcharge.

For distinct-game combos, begin with the product point forecast, then evaluate
shared marginal-error factors and residual outcome dependence on held-out days.
Construct joint scenarios from a coherent factor model rather than setting
pairwise correlations without controlling higher-order structure. Estimate
reserve quantiles on the *joint* forecast error where data permits; summing
separate per-leg worst cases can systematically charge for incompatible states.
Calibrate probability forecasts with proper scores and risk reserves with the
loss/markout target they are intended to protect. A one-sided markout quantile
is not a settlement guarantee, especially with discrete parlay outcomes.

Same-game MLB requires a separate joint score/outcome model: the original MLB
screenshot's same-game two-leg results are not evidence for an independent
cross-game strategy. Price game-winner, run-line and total combinations from a
joint score distribution with sport-specific settlement semantics, or exclude
them. Do not learn SGP correlation by lowering an arbitrary rho until a chart
looks attractive.

**Falsification:** compare calibration and realized loss tails by leg count,
fixture reuse and slate; measure reserve coverage out of sample. Use day/slate
resampling as well as fixture clustering, because common model errors survive
fixture-only resampling. Keep canonical contract and fixture limits until a
validated scenario model earns any additional hedge credit.

### D. Quote selection, creator evidence and inventory

The economically relevant probability is conditional on a customer accepting
our quote, not just conditional on the public book. Estimate acceptance and
post-acceptance markouts separately from the fair-value model. A schematic
objective for quote c and quantity q is:

```
Pr(accept | c, q, context)
  * [q * (c - p_joint_given_acceptance)
     - combo_fee - incremental_inventory_charge - capital_holding_charge]
```

This is a research objective, not a fitted implementation. A strong fair can
still lose if only informed customers accept. Conversely, a profitable public
print can be unavailable at our response latency. Passive shadow data supplies
RFQs, proposed quotes and future marks, but does not reveal acceptance of quotes
we never submitted. Log that censoring explicitly; no simulated acceptance
probability should be presented as measured until we have relevant observations.
Any future controlled quote exploration requires a separate authorized live
experiment within the existing limits.

Creator profiling should separate operational abuse (deduplicated spam rates,
repeated canceled requests) from economic toxicity (repeated adverse markouts
conditional on market state). Use sample-size shrinkage, minimum evidence,
expiry/decay and appeal/review records. Long combos or common fixtures can trigger
scope/model exclusions without proving bad intent. Replay only blacklist evidence
that was available before the RFQ; blocklisting based on a later loss is lookahead.
Measure good flow rejected as well as losses avoided.

Inventory-aware quote skew is preferable to indiscriminately lowering every
risk limit if concentrated positions explain bad variance. Retain hard cash and
canonical contract caps; add an incremental scenario-risk charge before a limit
is hit. Equivalent YES/NO descriptions need the same economic bucket. Do not
assume positions in different combos perfectly offset merely because one leg
is complementary: the other legs make their full payoffs different.

The general separation between inventory valuation and fill-sensitive quote
placement follows established market-making research; its Brownian-price and
arrival assumptions are not directly transferable to sports RFQs. The proposed
sports formulation above is our inference, requiring local validation.
[Avellaneda and Stoikov, original paper](https://math.nyu.edu/inmemoriam/avellaneda/HighFrequencyTrading.pdf).

## Reading a bad historical equity curve

| Observed failure | First investigation | Candidate change after evidence |
|---|---|---|
| No historical entries | Common-cohort funnel; reserve waterfall; achievable quotes | Calibrate reserves and study RFQ acceptance; do not force entries |
| Positive point edge, negative later marks | Availability leakage, delayed news, source bias | Innovation correction, regime reserve, shorter quote validity |
| Good leg scores, bad combo results | Dependence and selected-flow errors | Coherent joint model; conditional acceptance/creator model |
| Good unconstrained, poor constrained | Arrival ordering, settlement recycling, concentration | Inventory skew and allocation by expected return per capital-time |
| Good settled P&L, large exposure swings | Missing intraday marks; shared fixtures | MTM reporting and scenario risk before expanding caps |
| Isolated bad week with reasonable calibration | Effective sample size and clustered luck | Gather more held-out days; avoid immediate parameter changes |

Annualized Sharpe from a few settlement days can be meaningless. Report full
calendar-day observations, variance units, zero-variance/short-history handling,
peak capital and drawdown. Settlement-only equity smooths unresolved risk; it
needs a clear label and eventually a separate marked-to-market curve. Ordinary
square-root annualization assumes away serial dependence; show block-bootstrap
uncertainty or a serial-correlation-aware diagnostic once enough days exist.
The unconstrained run needs explicit peak funding, not an implied realizable
return on $10,000 when it borrows unlimited cash.

## Delegated workflow and MLB sequence

Separate research workstreams should share one immutable input cohort and
experiment registry:

1. **Data and causality:** exact payoff mapping, historical fee versions,
   clock/availability semantics, depth coverage and decision-to-leg acquisition.
   Sample actual combos first, then retrieve every required leg; independently
   sampling games destroys multi-leg coverage.
2. **Fair and delay:** static benchmark suite, robust venue errors and the
   delayed-anchor innovation experiment. Produce forecast and markout tables.
3. **Joint risk and execution:** reserve ablations, dependence, creator evidence,
   fill censoring and concentration. Produce loss and coverage diagnostics.
4. **Independent evaluation:** constrained/unconstrained plots and daily metrics,
   manifests, chronology audit and negative controls. This reviewer must not
   repeatedly tune on the holdout supplied to the other workstreams.

For MLB, use July for an initial development/calibration period, August for
chronological evaluation and September as a final frozen holdout, provided those
periods actually have sufficient comparable data. Fix the split before inspecting
returns. Report CFB and MLB independently before considering transfer: market
structure, season stage, schedules and settlement rules differ. Audit doubleheader
IDs, starting-pitcher/action conditions, shortened games, postponements and period
pushes before accepting mappings. Begin with exact non-player full-game,
non-push, distinct-game legs; treat SGP as a separately specified expansion.

OddsPapi documents history since January 2026, outcome activity and stake-limit
fields, with a five-second history-endpoint cooldown. These capabilities make a
July study plausible, but do not prove that our football-only account includes
baseball or that archived `createdAt` exactly reproduces delayed live availability.
Verify one MLB fixture and subscription entitlement before a broad acquisition.
[OddsPapi historical endpoint](https://oddspapi.io/en/docs/get-historical-odds).

Prefer a small preregistered model set over a large parameter sweep. Freeze each
configuration and its data hashes, run every model on the same cohort, and report
all tested variants. Expand the data only after coverage and accounting pass;
advance a model only after its forecast, conditional economics and operational
behavior agree. Wednesday shadow capture is useful for the missing temporal and
RFQ evidence even if historical Sharpe remains inconclusive.

## Subsequent direct MLB entitlement probe

The new key was tested through `scripts/oddspapi_baseball_history.py`. Baseball
fixture discovery returned 403. A separate direct historical request, using
native fixture `id1300010963303845` published in an OddsPapi example, returned
403 for both book slugs: `pinnacle` reported a bookmaker restriction, while
`pinnacle+30` explicitly reported restricted access to sport 13. Therefore this
account did not expose that baseball history in the direct test. This conclusion
is based on historical-endpoint responses, not an inference from live subscription
metadata. Both history requests left the account counters unchanged.

Redacted request/response evidence and counters are retained in
`runs/oddspapi_baseball_direct_history_20260907/`; the separate fixture-discovery
probe is in `runs/oddspapi_baseball_history_20260907/`. No subscription purchase,
live odds request or trading action was performed. Free/unmetered requests and
cross-sport access are separate questions for the provider to resolve.
