# OddsPapi delayed Pinnacle API probe — September 7, 2026

Authenticated API access and NFL odds retrieval succeeded. This was a bounded
read-only probe, not a continuous feed run or a trading session.

The active subscription grants `pinnacle+30`, American football (sport ID 14),
100,000 requests, no player props, no in-play odds and no WebSocket access.
The NFL tournament ID is 31. Account validity is September 7–October 7 at
18:23:19 UTC. Credentials are redacted from retained account responses.

An initial request using `pinnacle` failed with HTTP 403 / `RESTRICTED_ACCESS`.
The corrected request used `bookmakers=pinnacle+30` (the plus sign is encoded
by the HTTP client). It returned HTTP 200 in approximately 357ms:

- 16 Week 1 fixtures, all marked pregame.
- 465 full-game market entries: 16 moneylines, 211 spreads and 238 totals,
  including alternate and integer lines. Of these, 429 were active on both sides.
- 1,041 market entries in the complete response, including periods/team totals.
  Those additional markets are outside the launch scope.
- Numeric stake-limit fields were present on all 930 full-game outcome records.
  Their currency still requires verification; account billing currency does not
  establish the units of these limits.

The account request count rose from 0 to 4 across both probes. Seven HTTP calls
were made: three account reads, sport and tournament discovery, the failed odds
request and one successful odds batch. No retry loop or continuous poll ran.

## Timestamp findings

Across 930 full-game outcome records, `changedAt - bookmakerChangedAt` had a
median of 30.537s and 95th percentile of 40.184s; the sample also contained large
outliers. This is the provider's reported change-publication interval, not a
measurement of end-to-end live transport delay.

The freshest last-price-change timestamp was about 80 minutes before receipt;
the median was about 16.8 hours old. These are change times, not snapshot-as-of
or source-heartbeat timestamps. Old unchanged quotes alone neither prove nor
disprove a stale feed. Our conservative 90s source-age gate would currently
exclude them. A validated snapshot/source-liveness policy is needed before
promoting this data into the live fair; a successful HTTP response alone is
insufficient evidence that upstream bookmaker collection is healthy.

## Implementation and remaining work

The recorder now requests the exact delayed bookmaker slug and normalizes the
venue to `pinnacle` while retaining `provider_bookmaker: pinnacle+30`. The probe
selects only active subscription entitlements. Both credential files supplied
for this test were deleted, and the running session environment was not changed.

The polling config now records the verified sport/tournament IDs, bookmaker,
subscription dates and usage count with source references. Refresh account usage
before a subsequent run if the subscription is used elsewhere. Exact payoff
matching, push/tie treatment, limit currency, sustained freshness and live
execution/reconciliation remain unresolved launch requirements.

Evidence: `runs/oddspapi_smoke_20260907/` (initial probe) and
`runs/oddspapi_smoke_20260907_retry/` (successful odds, account check,
`summary.json` and `odds_inspection.json`).
