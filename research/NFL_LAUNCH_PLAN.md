# NFL Week 1 launch plan — September 7, 2026

The requested target is a supervised shadow session Wednesday September 9 and
live trading the September 12–13 weekend, conditional on the checks below.
The current executable strategy remains **shadow only**. A recorder running
successfully is not proof of valid three-venue pricing or execution readiness.

## Launch scope and economics

- Two, three or four legs; every leg from a different NFL fixture.
- Full-game, first-half and first-quarter moneylines, spreads, totals and team
  totals, subject to exact three-venue payoff matches. No player props, in-play
  or settled legs. See [expanded scope and architecture](NFL_NONPLAYER_ARCHITECTURE.md)
  for period-tie exclusions and current mapping coverage.
- Stop quoting 60 seconds before the earliest scheduled kickoff. An observed
  started flag is latched; a later delayed pregame update cannot reopen it.
- Maker buys combo NO (customer buys YES). Full requested size or decline;
  no ticket-spend cap, minimum/maximum combo probability filter or size clipping.
- $10,000 capital; provisional maximum-loss limits of $100 per canonical
  underlying, $100 per combo and $250 per fixture. The defensive disagreement
  regime halves the concentration limits. Each commitment consumes portfolio
  capital once and charges its full loss to every involved underlying/fixture.
- Complementary contracts and buying/selling orientations share the canonical
  risk families described in [fees and risk](NFL_FEES_AND_RISK.md). No invented
  offset credit between different combo payoffs.

One Pinnacle no-prop feed is the first subscription scope. Revisit props after
Week 1 using measured coverage and captured economics, not all-market turnover.

## What is implemented

`rfq_scope.py` enforces the same 2–4-leg non-player candidate scope for live book
subscriptions and quote decisions. Reviewed mappings enforce distinct fixtures
and market types; the pregame rule is independent of the weighting-model switch.

`shadow_engine.py` logs each RFQ disposition, full-size hypothetical quote,
three-venue inputs, reference ages/fees/weights, dependence reserve, creator
policy and all capital/concentration checks. Existing offers are rechecked on
price, status, reset and heartbeat events. No fills are inferred.

`joint_pricing.py` retains an independence point/interval as a benchmark and
uses a pairwise moment upper bound for the quote reserve. It preserves the old
two-leg bound. For three/four legs it maximizes all-win probability over the
8/16 joint outcome states subject to marginal intervals and every pair's
correlation-stressed upper moment. Higher-order dependence is unrestricted.
A repaired dual certificate makes the numerical result conservative; failures
exclude the quote. The rho ceiling 0.05 remains an **uncalibrated assumption**.

Pairwise independence does not imply joint independence. With three 50% legs,
a distribution on 111,100,010,001 with 25% mass each has pairwise independence
and a 25% all-win probability, versus the 12.5% independence price. This bound
can therefore be much wider than our old heuristic. Wednesday's review should
show its reserve separately; narrowing it requires an explicit, tested model
of higher-order dependence. Same-game requests remain excluded.

`weighted_fair.py` uses fee-expanded spreads and top-of-book capacity, freshness
and venue priors. Delayed Pinnacle has a 20% maximum weight and at least 30s
age; Polymarket has a provisional 1.5x liquidity-score prior. Live-exchange
intervals protect the fair even when the delayed reference has not moved.
Soft/hard interval gaps of 2c/5c reduce risk/widen or halt. See
[delayed feed modeling](DELAYED_PINNACLE.md) for the full formula.

`creator_service.py` remains an independent consumer with persistent evidence,
causal policy versions, spam cooldowns, expiry and manual overrides. High leg
counts alone do not cause permanent bans. Adverse-selection markouts at
5/30/120s are review evidence; correlation blacklisting still needs calibration.

`oddspapi_feed.py` implements account inspection and a separate REST recorder:
one subscription lock, shared persistent quota ledger, 30s tournament batch
polls while configured games remain pregame, 300s idle polls, raw archives,
exact reviewed market/outcome IDs, active-state checks and normalized events.
An account response echoes the API key, so it is redacted before caching.

The polling config now uses the verified NFL tournament and `pinnacle+30`
subscription, with a shared billing-cycle quota ledger. Native price-change timestamps are retained and **not** rejuvenated
by polling. Quiet prices may age out; vendor snapshot/heartbeat semantics must
be verified before treating unchanged prices as newly verified. USD stake-limit
units, NFL push/tie treatment, exact selectors and batch completeness also need
actual source evidence. A missing or changed line produces an inactive record.

## Wednesday run and review

Run the static preflight first; exit code 2 means unresolved configuration:

```sh
.venv/bin/python scripts/oddspapi_feed.py inspect
.venv/bin/python scripts/nfl_preflight.py --out runs/nfl_launch/preflight.json
```

Configure `config/oddspapi_polling.json` from actual subscription usage/billing
boundaries and NFL tournament IDs. The environment must expose
`ODDSPAPI_API_KEY` to the process starting the recorder. Never place a key in
runtime JSON, archives or CLI arguments. Reviewed `pinnacle` selectors belong
on the corresponding runtime mappings; simply removing their pricing block
is insufficient to establish payoff equivalence.

Refresh leg fees and validate current combo-series fees and each quote market's
actual price grid. Save a new immutable runtime configuration, then initialize
a **new** database after the code/configuration is final:

```sh
.venv/bin/python scripts/runtime.py --db runs/nfl_wed/events.sqlite --config config/runtime_nfl_week1.json init
.venv/bin/python scripts/runtime.py --db runs/nfl_wed/events.sqlite --config config/runtime_nfl_week1.json run --seconds 14400
```

In a separate process, start the Pinnacle collector against that same manifest:

```sh
.venv/bin/python scripts/oddspapi_feed.py capture --db runs/nfl_wed/events.sqlite --runtime config/runtime_nfl_week1.json --seconds 14400
```

The supervisor currently starts Kalshi, Polymarket and both consumers; the
Pinnacle REST process is separate and must be monitored too. Missing Pinnacle
prices inhibit quotes. Run all processes on an awake, clock-synchronized host
with measured storage capacity. A full one-hour three-venue soak remains due;
short historical capture benchmarks primarily measured rejection throughput.
Do not overwrite configuration or source in a running experiment.

Review before kickoff as well as after the opener. The configured opener is
Wednesday at 7:20pm Chicago time, with quoting cutoff at 7:19pm. Combinations
with later Week 1 games remain eligible only while **all** legs are pregame;
refresh schedule/status sources before the run.

```sh
.venv/bin/python scripts/review_runtime.py --db runs/nfl_wed/events.sqlite --mapping-config config/runtime_nfl_week1.json --out runs/nfl_wed/review
.venv/bin/python scripts/runtime.py --db runs/nfl_wed/events.sqlite --config config/runtime_nfl_week1.json archive --out runs/nfl_wed/archive
```

The compact review reports decisions/rejection reasons by leg count; proposed
YES premium, payout face notional, stressed net edge and maximum loss; per-minute
proposals alongside entire-combo public trades; venue coverage; latency;
creator evidence; consumer gaps and disk growth. Proposal sums may include
repeated/overlapping RFQs. They are not realized fills, cumulative deployable
opportunity, customer winnings or capital consumption.

Wednesday's acceptance criteria are complete RFQ dispositions; no unexplained
consumer errors or feed gaps; current paired inputs on every proposed leg;
latency measured through actual fair/risk work; correct stale-feed and kickoff
inhibition; restart/replay consistency; and exposure never exceeding limits.
Record priced/rejected flow even when a reserve prevents quoting.

## Required before weekend live trading

The following are implementation/evidence gates, not manual boolean switches:

1. Operating, verified Pinnacle mappings/limits/timestamps/payoff treatment;
   current fees/grids and verified account balance precision.
2. Quote submission, acceptance, revalidation, confirmation and cancellation
   adapter connected to a durable live commitment ledger. The existing shadow
   reservation expiry must never release an uncertain live commitment.
3. Exchange-derived target-cost contract counts reconciled before confirmation;
   restart recovery and account balances, positions, quotes, orders and fills
   reconciled before adding risk. No blind retries after ambiguous submission.
4. Exercise disconnects, duplicate/out-of-order notifications, cancellation races,
   accepted-but-unconfirmed quotes, partial execution and unknown outcomes.
5. A supervised execution test proves actual acceptance/confirmation/fill and
   fee/capital accounting; establish a halt path and off-host log retention.

Kalshi's [RFQ lifecycle](https://docs.kalshi.com/getting_started/rfqs) specifies
private quotes for the full request, then customer acceptance, maker confirmation
and subsequent order entry. Combo markets use a 3s confirmation window and 1s
execution timer. Quote-derived YES/NO counts are supplied by the exchange for
target-cost RFQs. Our current target-cost ceiling is explicitly a shadow sizing
assumption. Public prints cannot establish our acceptance or fills.

The goal is the weekend launch; **the current code cannot yet submit live RFQ
quotes**. `nfl_preflight.py` records these outstanding capabilities explicitly.

## Account probe, September 7

The active subscription identifies the delayed bookmaker as `pinnacle+30`.
Requesting `pinnacle` returned HTTP 403 with `RESTRICTED_ACCESS`. The probe now
derives the exact feed name from active account entitlements, and the recorder
preserves that source name while normalizing its venue to `pinnacle`. NFL is
sport 14 / tournament 31. The account reports 100,000 requests and no in-play,
player-prop or WebSocket access. Evidence is retained in
`runs/oddspapi_smoke_20260907/`; current odds results are in the retry directory.
