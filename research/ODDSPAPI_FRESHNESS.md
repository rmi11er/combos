# OddsPapi coverage and freshness validation — September 7, 2026

A bookmaker quote's last-change time is not its last-observed time. An unchanged
price may be old and still executable. Conversely, an HTTP 200 response can
return an old upstream snapshot. The two problems need separate measurements.

## Subscription coverage confirmed by the vendor catalog

The NFL snapshot was joined by exact market ID to `GET /v4/markets`. Every
observed market matched; all were marked `playerProp: false`.

| Period | Winner | Spreads | Totals | Team totals |
|---|---:|---:|---:|---:|
| Full game, including overtime | 16 | 211 | 238 | 32 |
| First half | 16 | 176 | 175 | 32 |
| First quarter | 16 | 49 | 48 | 32 |

Counts are market entries in the initial 16-game snapshot, including alternate
lines and inactive entries. First-half and first-quarter winners are already
included in this no-player-prop subscription. The account's `has_player_props`
flag and the catalog's per-market `playerProp` flag refer to player props;
there is no basis here for treating every period or team market as paid props.
This evidence does not promise coverage of every possible exotic market.

Our initial algorithm still permits only full-game moneyline/spread/total legs.
Additional period/team markets require their own payoff and risk mappings.

References: [market catalog](https://oddspapi.io/en/docs/get-markets),
[account entitlements](https://oddspapi.io/en/docs/get-account). Captured evidence:
`runs/oddspapi_freshness_20260907/football_market_catalog.json` and
`market_coverage.json`.

## Three different clocks

1. **Last bookmaker/vendor change:** `bookmakerChangedAt` and `changedAt`.
   These measure when a selection changed, not a heartbeat. Their difference
   measures a reported change-publication interval, not total current feed lag.
2. **Our last complete successful poll:** request start, response receipt,
   HTTP cache information and response content. Polling failures or missing
   selections cannot refresh a price's locally observed state.
3. **Upstream source health:** evidence that OddsPapi is still observing
   Pinnacle correctly. HTTP Date advancement proves neither Pinnacle connectivity
   nor that every individual fixture is current. A fixed `bookmakerIsActive`
   flag also lacks a last-checked timestamp in the documented response.

The [odds schema](https://oddspapi.io/en/docs/get-odds) explicitly describes the
two change timestamps as last changes. Treating an old change timestamp as proof
of feed failure is incorrect. Treating receipt time as proof of a fresh upstream
source would also be incorrect.

## Reusable validation infrastructure

`scripts/oddspapi_freshness.py` performs a bounded repeated-poll test, joins
account quota state to a shared subscription budget, saves the market catalog
and archives all odds snapshots and selected HTTP headers. It accepts an
environment key or a temporary key-file path; the optional deletion flag removes
that file after completion. It does not submit orders or publish quoteable fairs.

`feed_freshness.py` distinguishes price/limit/state changes, timestamp-only
updates, missing/reappearing selections, timestamp regressions, source-change
age, request latency and HTTP cache/date information. Quiet snapshots produce
an inconclusive diagnosis, never an automatic stale-feed label. Membership
changes alone do not establish fresh economic prices.

The existing normalizer now preserves these separate clocks in the decision
context. Its current weighting timestamp remains a labeled conservative
last-change proxy; this experiment does **not** silently enable a different
live pricing policy or lift the payoff/limit mapping blocks.

## Proposed replacement for the placeholder freshness gate

After validating the snapshot and upstream-health assumptions, use:

`effective_reference_age = nominal_delay + age_since_last_successful_poll_start + known_cache_age`

This is a model of information age, not an independently measured latency
bound. Using request start includes request/download latency conservatively.
Keep quote-change age as a diagnostic. Do not refresh local age from a cache
hit or a failed, partial, inactive or missing selection. Preserve original
receipt time when reading cached files. Source as-of timestamps, if a verified
provider field becomes available, should take precedence over this proxy.

With a 30-second delayed feed polled every 30 seconds, the modeled reference age
normally ranges from roughly 30 to 60 seconds plus HTTP overhead/cache age,
even when the price itself has been unchanged for hours. Existing live-exchange
disagreement widening/halting, low Pinnacle weight and per-leg concentration
limits remain relevant: snapshot polling does not remove the 30-second blind
period or establish upstream health.

A short quiet-market test cannot calibrate the feed-freeze detector. Observe
actual price changes through an active betting period and verify their
publication/reception timing; obtain a provider snapshot/last-checked/health
contract before treating HTTP success alone as trading evidence.

## Measured result

The completed run made 11 odds polls over 305.2 seconds. All returned the 16 NFL
fixtures. Median request latency was 381ms; maximum was 702ms. All 2,008 active
outcomes remained present, and no observed price, limit or active-state value
changed. No timestamp regressions were observed. Eight inactive total selections
for one fixture intermittently disappeared and reappeared; these membership
changes do not demonstrate live price updates. HTTP dates advanced and the
responses reported `CF-Cache-Status: DYNAMIC`, with no `Age` header.

The result establishes working, timely HTTP delivery. It is **inconclusive for
upstream price freshness** during this quiet window. It does not justify labeling
all unchanged quotes stale, and it does not validate the upstream delay bound.
Next useful evidence is a real price change observed through both publication
and subsequent polling, ideally in a busier pregame window, plus vendor source
health semantics.

The run consumed 12 quota requests (11 odds batches and one market-catalog call).
Two account reads were additional HTTP requests but did not increase quota usage.
The account now reports 16 requests used. The temporary key file was deleted.

`runs/oddspapi_freshness_20260907/summary.json` preserves the capture report.
`validation.json` is the final offline analysis; it distinguishes inactive
membership changes from economic price changes and includes raw-file hashes.
The full suite passes 103 tests, including quiet-market diagnostics, cache-age
separation, timestamp regressions, missing outcomes and delayed-feed identity.
