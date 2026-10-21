# Pinnacle selector and payoff review — September 7, 2026

The saved capture supports **180 normal-game full-game selector/payoff matches**: 148 half-point spread/total contracts and 32 moneyline contracts with a distinct tie basis. It does not support declaring all three venues' exceptional settlements identical. The new candidate file retains every pricing block.

| Review result | Mappings |
|---|---:|
| Half-point full-game spread, ordinary binary payoff verified | 65 |
| Half-point full-game total, ordinary binary payoff verified | 83 |
| Full-game moneyline, decisive result verified; tie adjustment needed | 32 |
| Full-game moneyline/spread/total exact selector unavailable | 121 |
| Period/team-total review deferred | 153 |
| Fully approved for three-source live pricing | 0 |

The review rebinds against the final saved OddsPapi snapshot and the archived market catalog. It retains exact fixture/date/start, period, team, catalog market/outcome ID, and handicap matching. No nearest-line replacement is used. For covered full-game markets, an independent score enumeration checks both mapped outcomes against every integer home/away score pair from 0 through 100. This verifies payoff logic, not outcome probabilities. The existing exchange mappings preserve actual Kalshi rules and Polymarket descriptions.

## A real implementation error fixed

The previous normalizer required `bookmakerMarketId` to remain byte-for-byte equal to its mapping-time value. **45 of 265 existing selectors had changed IDs** even though the exact catalog market and both native outcome side/line identifiers remained the same. Another 218 were unchanged; two markets disappeared; 189 mappings had no selector.

The native strings contain current line identifiers. The archived changes affected component 4, and additionally component 5 for alternate lines. Pinnacle's API documentation identifies `lineId` and `altLineId` separately from the event, period, bet type and handicap, and instructs callers to use current returned identifiers. [Pinnacle Getting Started](https://github.com/pinnacleapi/pinnacleapi-documentation/blob/master/GettingStarted.md?plain=1).

`pinnacle_feed.same_native_market_identity` now permits these numeric identifier changes only for recognized NFL native shapes with matching native sport, league, fixture, period and market type, matching provider/native fixture IDs, exact catalog outcomes, and both exact native outcome side/line strings. Unknown formats and changed lines still fail. The old and current IDs are retained in observation context. This repairs a false exclusion; it does not remove payoff, currency, active-state, or freshness checks. All 45 changed archived identifiers pass this stronger semantic check.

## Settlement basis that remains

Pinnacle two-way moneylines void on a tie; its NFL full-game markets include overtime. Pinnacle also has a 12-hour game-start deadline, suspension rules based on whether 55 minutes have been completed, and general venue-change rules. These terms differ from the archived exchange contracts. [Pinnacle official betting rules](https://www.pinnacle.com/en/future/betting-rules).

Kalshi's archived NFL moneyline rules pay 0.5 on a tie and use a 48-hour start window followed by fair-price settlement. The matching Polymarket description pays 0.5 on a tie or cancellation, and keeps a postponed game open until completion. Half-point spreads/totals have matching normal completed-game binary outcomes, but that alone does not resolve cancellation, abandonment, or venue-change basis. Some Kalshi market-level descriptions do not repeat the full series exceptional rules; the review must not manufacture those missing clauses.

For a de-vigged Pinnacle moneyline `q = P(win | decisive game)` and an independently estimated tie probability `tau`, ignoring other exceptional states:

`Kalshi expected settlement = (1 - tau) * q + 0.5 * tau`.

Thus treating Pinnacle `q` as an exact binary expectation makes an error of `(0.5 - q) * tau`. A symmetric near-even matchup has little tie adjustment; a lopsided matchup has more. We have not estimated `tau` here. This belongs in an explicit basis model; it is not justification for a large arbitrary charge on every RFQ.

## Information time and liquidity

The four archived polls span 95.95 seconds. Each carries 2,008 active outcomes. No active outcome's price, limit, or state changed; eight inactive outcomes appeared and disappeared. Median reported bookmaker-to-vendor change publication lag was 30.543 seconds. These observations are consistent with the delayed feed description but do not measure current source-to-client lag.

OddsPapi documents `bookmakerChangedAt` as the last reported bookmaker change and `changedAt` as the last change recorded in its system. Neither field is documented as a last-successfully-checked source snapshot time. Its `limit` field is a maximum bet amount; its public example describes maximum stake. These sources do not establish the account/feed limit currency. [OddsPapi GET odds](https://oddspapi.io/us/docs/get-odds), [OddsPapi outcome schema explanation](https://oddspapi.io/blog/json-odds-feed-format-parsing/).

**An old price-change timestamp is not evidence that a still-available price is stale.** HTTP receipt/Date proves recent HTTP delivery, not upstream collection health. We should retain last-change age as a diagnostic and separately record a modeled information age from nominal delay plus elapsed time since successful poll, with a provider-confirmed health/snapshot contract before calling that bound verified. The live normalizer's conservative last-change weighting remains unchanged in this patch. No conclusion about broad adverse selection from a 30-second delay follows from this capture; the MLB study should test that hypothesis separately from mapping correctness.

Two narrowly specified provider facts would close major remaining gaps: what currency `pinnacle+30.limit` uses, and whether a successful full snapshot guarantees current active offers as of a defined delayed horizon, including how upstream failures are exposed. Direct Pinnacle supports account currencies, so its own API documentation cannot establish the reseller feed's currency by inference. No provider message was sent.

## Reproduce and inspect

```sh
.venv/bin/python scripts/review_pinnacle_mapping.py \
  --runtime runs/shadow_research_20260907/capture_001/runtime.json \
  --raw-dir runs/shadow_research_20260907/capture_001/pinnacle_raw \
  --catalog runs/oddspapi_freshness_20260907/football_market_catalog.json \
  --output runs/pinnacle_mapping_review_20260907
```

Outputs: `summary.json`, per-mapping reviews, original selector diagnostics, and `runtime_reviewed_candidates.json`. Raw snapshots, catalog and runtime input hashes are recorded. The candidate is explicitly shadow-only and retains all pricing blocks. Existing configured fee references must also be refreshed before a new trading session; this offline review does not refresh them.

Validation: 31 focused tests passed, including real semantic rejection cases, preserved payoff blocks, side/complement errors, handicap sign mistakes, tie basis, total boundaries, and period exclusions. No odds requests or orders were made for this review.
