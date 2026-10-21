# Reusable pricing and creator research

Implemented September 6, 2026. The frozen September 5 opportunity study remains
in `output/`; new experiments belong in separately named `runs/` directories.
The $10,000 capital base, no ticket cap, and no combo probability restriction
remain the study settings. The new replay measures prices independently of
capital allocation and does not assume fills.

The user's subsequent continuous-liquidity objective and Wednesday NFL target
are captured in [the NFL launch plan](NFL_LAUNCH_PLAN.md). That plan takes
priority for implementation order: build continuous shadow pricing, risk
reservations and online decision/blacklist logs while historical validation
continues. The research sequence below remains the calibration workstream.

The continuous services are now implemented in `scripts/runtime.py`; see
[runtime operations](RUNTIME_OPERATIONS.md) for collectors, online creator
policy, shadow decisions/risk, and archive/replay commands. The commands in this
document remain the original offline research interface.

## Research sequence and acceptance criteria

1. **Validate one complete historical game before buying into a broad estimate.**
   Discover OddsPapi sport, tournament, market and fixture IDs, then request both
   opposing Pinnacle outcomes, including inactive records. Verify September 5
   coverage, exact line and period, overtime, pushes/voids and cancellation rules,
   timestamp semantics, units of limits, and historical exchange depth. Inspect
   changing limits and suspension intervals as well as prices. Expand to the
   slate only after a manually reviewed game replays correctly. Do not filter
   historical fixtures by their *current* `hasOdds` status.
2. **Compare pricing models on the same observations.** Use Kalshi alone,
   Polymarket alone, Pinnacle alone, equal weights and spread/depth weights.
   Separate pregame from in-play. Hold out complete days and fixtures when
   calibrating weights; clustering at the fixture level matters because many
   combos reuse the same information. Score calibration and subsequent fair
   changes, not just how much apparent edge a model creates. Report missing-data
   coverage, source disagreement, lag sensitivity, and pricing intervals beside
   the point estimates. A high apparent edge can indicate a bad fair.
3. **Capture at least another college-football Saturday.** Three to seven days
   of RFQs are a useful first creator sample; weekdays alone need not represent
   the target CFB population. The communications recorder is available now.
   Next add live individual-leg books, reviewed fixture mapping and hypothetical
   quote decisions using the same observation schema and pricing function.
   Record receive time, source time, reconnects and unavailable intervals.
   Measure 5/30/120-second adverse markouts, with labels becoming available only
   after their horizons. Prefer an independent or leave-one-venue-out markout
   reference so the benchmark does not just echo the quote being tested.
4. **Build creator evidence before applying exclusions.** Deduplicate RFQ IDs;
   count repeated leg sets, request rates, leg counts, sample size, and observed
   time. Check creator-ID continuity across sessions before treating it as a
   persistent account identity. Repeated bursts are operational evidence. Shared fixtures and long
   combos are structural flags, not proof of pickoff intent. Add repeated
   adverse markouts and joint-model evidence before labeling correlation
   pickoffs. Evaluate any blacklist using only evidence available before the
   current decision, and measure lost good flow as well as avoided adverse flow.
5. **Then evaluate execution and capital.** Public prints are not historical
   quote midpoints and do not identify our fill probability. Passive recording
   cannot establish acceptance of a hypothetical quote. Keep gross notional
   price gaps, net edge after combo fees, executable size, acceptance, and
   portfolio capital usage separate. Model shared-game concentration and
   settlement timing before optimizing the uncapped $10,000 allocation. Keep
   same-game pairs outside the independent-leg product until a joint model is
   validated; three-source marginals do not solve dependence.

## Initial weighting hypothesis

For venue v, with both sides expressed as $1 payout capacity:

```
depth_v = min(bid_capacity_v, ask_capacity_v)
spread_v = 100 * (fee_expanded_ask_v - fee_expanded_bid_v)
score_v = sqrt(depth_v) / max(spread_v, 1 cent) * 2**(-age_v / half_life)
```

Normalize scores, capping each venue at 60% and redistributing excess weight.
Both the point and interval endpoints use these weights. Square-root depth
reduces sensitivity to one large displayed order; it is a hypothesis to compare
against linear depth and equal weights. Top-of-book size is a liquidity proxy,
not a guarantee that size is executable. Expose venue disagreement rather than
assuming a tight blended interval means the venues agree.

The initial policy in `config/weighting.json` uses a 60-second pregame half-life
and 120-second maximum age; in-play uses 5 and 15 seconds. These parameters are
provisional. In-play score changes can invalidate all lagging sources together.
Freshness should reflect the last verified book state, not merely a new
timestamp attached to an old quote; historical update-only feeds may not prove
that an unchanged quote remained available.

Exchange widening is `[bid - r*bid*(1-bid), ask + r*ask*(1-ask)]`, clipped to
[0,1], using the market's effective fee version. The point remains the raw
midpoint. This adapter currently supports this quadratic per-share fee shape;
other schedules require an explicit extension, and minimum/rounded ticket fees
belong in the execution calculation. Fee references are mandatory.

For Pinnacle decimal odds Y and N, the center is multiplicatively de-vigged
`(1/Y)/(1/Y+1/N)`, and the interval is `[1-1/N, 1/Y]`. The bookmaker margin is
already represented; no invented exchange taker fee is added. USD maximum
stakes convert to payout capacities `stake_yes*Y` and `stake_no*N`. Verify that
the provider's limits really mean those units before normalization. Alternative
de-vig methods are an additional sensitivity, especially for longshots.

These intervals describe fee/margin uncertainty. They are not statistical
confidence intervals or correlation reserves. Missing depth is not replaced
with arbitrary venue weights in the strict model; report price-only benchmarks
separately if historical capacity cannot be recovered.

## Commands

Run from the project root using `.venv/bin/python scripts/research.py --help`.
Every replay, recorder and profile output directory must be new. SQLite imports
are atomic and deduplicated. Conflicting snapshots at the same availability
time fail rather than silently overwrite. Raw OddsPapi responses are compressed
and versioned by request; cached reads do not require another API call.

Set `ODDSPAPI_API_KEY` in the process environment. Do not put it in request
parameters or commands committed to this repository. No OddsPapi credential is
currently configured here, so actual provider payloads and coverage are still
unverified.

```sh
.venv/bin/python scripts/research.py odds-fetch sports
.venv/bin/python scripts/research.py odds-fetch markets
.venv/bin/python scripts/research.py odds-fetch historical-odds --params '{"fixtureId":"REVIEWED_FIXTURE_ID","bookmakers":"pinnacle,kalshi,polymarket"}'
.venv/bin/python scripts/research.py import-observations path/to/normalized.jsonl --db runs/observations.sqlite
.venv/bin/python scripts/research.py replay path/to/decisions.jsonl --db runs/observations.sqlite --out runs/experiment_001
.venv/bin/python scripts/research.py record-rfqs --out runs/rfq_session_001 --seconds 60
.venv/bin/python scripts/research.py profile-creators runs/rfq_session_001 --out runs/creators_001
```

The recorder uses existing `KALSHI_API_KEY_ID` and `KALSHI_PRIVATE_KEY_PATH`
environment variables and signs independently of the old project. It subscribes
only to communications. There is no quote submission or order placement path.
For a three-day run on an always-on host, use `--seconds 259200`. Choose a new
directory on restart, then pass closed journals in chronological order to
`profile-creators`. Do not launch multiple OddsPapi fetch processes against a
shared account without an account-wide rate limiter; the current pacing is per
process. The fetch CLI is sequential and conservatively waits at least 5.05
seconds between calls.

Closed journal chunks have SHA-256 hashes, row counts and a manifest. They rotate
at 10,000 records and on ten-second heartbeats. Reconnects and sequence
discontinuities are retained; sequence validation is possible only where the
server supplies sequence numbers. A completed capture duration is not proof of
uninterrupted coverage. Abrupt shutdown leaves `.open` files or an incomplete
manifest; replay refuses these until recovery is reviewed. Clean termination
can take the acquisition duration plus the WebSocket close timeout. Local disk
rotation does not upload or delete old data: budget storage and monitor disk,
clock, connection health and process uptime before a multi-day host run.

Creator profiling uses a disk-backed RFQ-ID deduplication table, a bounded
60-second request window and aggregate counts per creator. Raw IDs are retained
in the local journal and evidence database; the summary exports creator hashes.
It emits review flags and their availability timestamps, not automatic bans.
Its repeated-event count is only a lower bound: separate Kalshi market families
can describe the same real fixture. Canonical fixture mapping and live pricing
are needed for correlation evidence. Profile outputs are batch rebuilds over
the supplied journals, not a deployed online blacklist service.

## Normalized records and causal replay

One JSON object per line, canonical YES orientation. Required common fields:
`market_key`, `venue`, `observed_at`, `available_at`, `active`,
`source_reference`, `mapping_reference`. Timestamps are UTC epoch seconds;
availability must not precede observation. `source_reference` identifies the
raw record. `mapping_reference` identifies reviewed payoff evidence. This first
version requires supplied reviewed references; it does not yet automate mapping
review or normalize arbitrary provider payloads.

Example exchange fields (synthetic values):

```json
{"market_key":"fixture-a:full-game:home-win","venue":"kalshi","observed_at":100,"available_at":101,"active":true,"source_reference":"synthetic:raw-row","mapping_reference":"synthetic:reviewed-payoff","fee_reference":"synthetic:fee-version","yes_bid":0.48,"yes_ask":0.52,"taker_rate":0.07,"yes_bid_size":100,"yes_ask_size":150,"size_unit":"payout_dollars"}
```

Polymarket uses the same fields with its own actual fee version. Pinnacle
replaces exchange price/fee/size fields with `decimal_odds_yes`,
`decimal_odds_no`, `max_stake_yes`, `max_stake_no`, `limit_currency:"USD"`, and
`limit_unit:"stake"`. Both opposing quotes, capacities and active state must
describe a causally assembled snapshot; the normalizer must enforce component
freshness rather than refreshing an old side with the other side's timestamp.
An inactive record needs only common fields. The latest inactive record blocks
pricing; the store never falls through to an older active price.

Availability means when the observation could have been used by the strategy.
For live observations use actual receipt time. Retrospective provider data need
validated publication semantics and explicit latency assumptions; downloading
history today does not make today's retrieval time its historical availability.
Keep raw retrieval times separately. Mapping and fee changes also need effective
dates in their referenced evidence.

Decision records require `decision_id`, `decision_at`, `reference_yes_price`,
`reference_kind`, phase, and exactly two legs. Each leg has `market_key`,
`fixture_key`, and `side`. A leg-specific `phase` overrides decision phase.
Allowed reference kinds are `combo_book_midpoint`, `trade_price`, and
`hypothetical_quote`. Allowed phases are `pregame` and `in_play`.

```json
{"decision_id":"synthetic-decision","decision_at":102,"phase":"pregame","reference_yes_price":0.30,"reference_kind":"combo_book_midpoint","legs":[{"market_key":"fixture-a:full-game:home-win","fixture_key":"fixture-a","side":"yes"},{"market_key":"fixture-b:full-game:home-win","fixture_key":"fixture-b","side":"no"}]}
```

Replay outputs per-decision comparisons, leg weights, interval endpoints,
source/mapping/fee references, exclusions, and a configuration/content-hash
manifest. It keeps a consistent SQLite read snapshot. The reported gaps are
signed YES-reference minus fair, in cents per contract, **before combo execution
fees**. Quantity is deliberately absent; notional edge requires dividing those
cents by 100, multiplying by eligible quantity, and subtracting applicable fees.

## Validation and remaining work

Tests cover known-answer fee/weight calculations, currency/capacity validation,
future-data rejection, suspension handling, SQLite conflict/deduplication and
rollback, same-fixture exclusion, journal integrity, creator deduplication, and
the import-to-replay CLI. A bounded live capture saved 21,940 RFQs with creator
IDs and 22,178 deletion events. Profiling recovered 5,852 distinct creator IDs in
that sample. These are whole-universe observations on September 6 local time,
not evidence of CFB strategy profitability or a representative creator sample.

The continuous runtime now supplies exchange leg-book adapters, combined
RFQ/leg shadow valuation and diagnostic markouts. Remaining work includes
reviewed NFL payoff mappings, provider-specific Pinnacle normalization,
independent markout benchmarks and opportunity plot integration for the strict
model. Current historical Polymarket price histories do not establish historical
top-of-book depth. The existing September 5 estimates have not been replaced by
a three-venue result.

Provider references:
- [Historical odds](https://oddspapi.io/en/docs/get-historical-odds): documented
  timestamps, stake limits, active state, exchange metadata and historical scope.
- [Live odds](https://oddspapi.io/en/docs/get-odds): fixture identifiers and
  provider/bookmaker update metadata.
- [Kalshi communications](https://docs.kalshi.com/websockets/communications):
  RFQ event subscription. Empirical creator-ID availability is recorded above.
