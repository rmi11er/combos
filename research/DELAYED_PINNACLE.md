# Delayed Pinnacle, pregame-only shadow model — September 7, 2026

The user selected the retail OddsPapi Pinnacle product with a reported 30-second
delay. Treat that as a minimum information delay, not a freshness guarantee. The
user subsequently supplied football prices: 5k calls/$35, 100k/$70, 500k/$175,
1.5m/$350 per month. Entitlements and delay semantics await account verification.

## Implemented model defaults

`config/weighting.json` now selects `delayed_pinnacle_pregame_v1` for the runtime
and reusable research replay. `WeightPolicy()` without configuration retains the
legacy model for explicit comparisons. Frozen September 5 outputs are unchanged.

| Parameter | Provisional shadow default |
|---|---|
| Universe | Two distinct NFL fixtures; every leg pregame |
| Last quote time | 60 seconds before the earliest scheduled kickoff |
| Pinnacle effective age | max(decision − source observation, decision − receipt + 30 seconds) |
| Maximum effective age | Pinnacle 90 seconds; direct exchanges 15 seconds |
| Liquidity score | sqrt(two-sided payout capacity) / max(fee-expanded spread in cents, 1), times freshness and venue prior |
| Venue priors | Kalshi 1; Polymarket 1.5; Pinnacle 0.5 |
| Final weight ceilings | Pinnacle 20%; each exchange 60% |
| Baseline interval padding | 0.5 contract cents on each leg endpoint |
| Defensive threshold | Any pair's fee-expanded intervals separated by at least 2 cents |
| Defensive response | Pinnacle score ×0.25; exposure caps ×0.5; padding += interval gap above 2 cents |
| Halt threshold | Any pair's fee-expanded intervals separated by at least 5 cents |
| Capital | $10,000 |
| Aggregate maximum-loss caps | $100 per underlying contract, $100 per combo, $250 per fixture |

The disagreement measure uses interval separation, rather than treating normal
fee/overround differences as news. All pairwise gaps and the unadjusted midpoint
range are logged. Either exchange can trigger a defense; agreement by both is
not required. The model does not infer that news occurred merely from disagreement.

The protected interval encompasses both current exchange intervals plus the
padding. Thus a delayed Pinnacle quote cannot drag the upper risk bound beneath
a current exchange's bound. The lower endpoint receives symmetric protection for
selected NO legs. The fair point remains the weighted estimate. Existing cross-game
correlation stress and combo maker fees apply afterward. No probability filter or
customer-ticket cap is introduced. Caps measure maker maximum loss, include open
reservations and simulated fills across RFQs, and conservatively charge each leg
the full combo loss; they are not customer spend or directional delta limits.

Polymarket's 1.5 multiplier is a testable sharpness prior, not a factual ranking.
Lower fees already affect the interval/spread score; this extra preference is an
intentional separate hypothesis and should be ablated against multiplier 1. KYC
is not a pricing variable. Compare later price changes and independent closing
benchmarks by league/market type, while controlling for liquidity, fees and age.

Open shadow offers are invalidated on new observations, resets, fixture-status
events and heartbeats when their edge disappears, the risk regime tightens, or
their inputs become invalid. Reservations expire no later than the pregame cutoff.
The `fixture_status` input (`fixture_key`, `phase`) can stop quoting early; once
in-play/finished is observed it is latched and delayed pregame messages cannot
reopen the fixture. Automatic live game-status collection remains to be wired;
the scheduled cutoff is currently the automatic time boundary. Simulated fills
after cancellation/expiry are rejected explicitly. This is not a live cancel/fill
race model, and filled positions remain capital commitments after kickoff.

Every decision retains weights, ages, venue priors, fee-expanded gaps, guard
regime, padded and unpadded intervals, risk checks and configuration hash. Quote
invalidations retain their triggering event and available pricing context.

## Causal historical replay

Delayed-mode replay requires `start_at` on both decision legs and rejects in-play
or near-kickoff decisions. Pinnacle snapshots are selected with effective
availability max(original availability, observation time + 30 seconds). A future
price may not be used merely because it appears in a historical dataset. Replay
then uses that effective availability, avoiding a second addition of the delay.
Production recording will preserve actual receipt times, source change times,
and validated snapshot-as-of times separately. An unchanged price is not proof of
an unhealthy feed, but a response received now is not proof of current upstream
state. Until the provider's timestamps are understood, no receipt-time refresh
may silently rejuvenate old odds. Missing limits/payoff mappings still block pricing.

## Request budget and acquisition design

[The tournament endpoint](https://oddspapi.io/en/docs/get-odds-by-tournaments)
accepts comma-separated tournament IDs and a bookmaker filter and is documented
to return all fixtures. [Quota accounting](https://oddspapi.io/en/docs/requests-and-quota)
charges one request per billable call regardless of the number of returned
fixtures. Errors also count. Historical calls do not increment usage, but vendor
quota exhaustion can block them; `/account` remains accessible.

Use one collector/cache owner per subscription. Query the NFL tournament in one
call and fan out the same response to all leg mappings and strategy consumers.
RFQ volume and combo count must not create additional HTTP calls. Validate actual
batch response shape, line/fixture coverage and tier access before depending on
one request per sweep; documentation examples alone do not prove completeness.

Refresh the batch every 30 seconds while pregame quoting is enabled; every five
minutes during idle discovery. A strategy requesting activation waits for a fresh
batch before quoting. Idle snapshots older than the pricing age limit cannot price
RFQs. A movement in either direct exchange triggers quote protection immediately
and marks the shared batch for refresh at the next permitted slot. Coalesce
signals into one pending refresh and allow one request in flight. Do not poll on
every price tick or only on movements: the former burns quota and the latter
misses sportsbook-led changes. Do not infer that the 30-second delay is a fixed
30-second publication cadence. The initial cadence is a cost/latency assumption.

Cache metadata separately (daily where appropriate); invalidate/reload for unknown
market IDs. Archive raw responses before normalization, including original receipt
and request identity, and publish normalized observations to the existing event
log. Strategies read local state without waiting for HTTP. A failed request leaves
the old cache timestamp unchanged; once too old it stops pricing. Use bounded
exponential backoff with jitter in the future collector, and no stale-while-refresh
pricing beyond the hard age limit. Inspect account quota on startup and periodically,
using actual billing boundaries, and reconcile all other clients' usage.

| Schedule, one complete batch per poll | 30-day base calls | 31-day base calls |
|---|---:|---:|
| 30 seconds continuously | 86,400 | 89,280 |
| 12 hours/day at 30 seconds; remainder at 5 minutes | 47,520 | 49,104 |
| 4 hours/day at 30 seconds; remainder at 5 minutes | 21,600 | 22,320 |
| Five-minute discovery only; not continuous quoting | 8,640 | 8,928 |

Budget roughly 25–60k/month for selective NFL pregame operation, conditional on
active hours and one-call batch completeness. Reserve room for metadata, failures,
retries and manual research. The 100k/$70 tier is the initial recommendation.
The 5k tier permits only 41.7 hours of 30-second polling with no other requests;
even continuous five-minute discovery exceeds it. The 500k and 1.5m tiers are not
justified for this initial batch design. Multiple per-fixture calls or additional
unbatchable tournaments multiply the relevant counts, so remeasure after access.

Implemented primitives: `OddsPapi.get(..., max_cache_age_seconds=30)` uses the disk
cache without changing receipt timestamps; `odds-by-tournaments` is allowed.
`RequestBudget` is a persistent SQLite allowance shared by clients, with explicit
billing boundaries and per-attempt accounting, including retries. It defaults to
preserving 10% of the purchased allowance and must be passed to `OddsPapi` by the
collector. Its count is conservatively seeded/reconciled from account usage; it
cannot observe requests made outside the shared counter. A new billing period
requires explicit configuration. `monthly_requests` reproduces the table.

`config/oddspapi_polling.json` records the intended scheduler settings. The
automatic scheduler, account reconciliation and provider-to-canonical normalizer
are not yet connected. Next integration step once the user has access: obtain a
small raw batch and account sample, verify units/timing/entitlements and exact
Pinnacle payoff mappings, then wire the one-owner collector and measure effective
staleness and quota consumption. No subscription or provider requests were made
while implementing these changes.

## September 7 launch scope update

The engine now accepts 2–4 full-game NFL moneyline/spread/total legs from distinct
fixtures. Pregame eligibility and the 60-second cutoff are enforced independently
of the weighting model. Three/four-leg dependence uses a conservative joint-state
moment bound, not repeated multiplication of two-leg stresses. The no-prop REST
recorder is implemented; account payload validation and payoff mappings are still
required. See [the launch plan](NFL_LAUNCH_PLAN.md) for current readiness.
