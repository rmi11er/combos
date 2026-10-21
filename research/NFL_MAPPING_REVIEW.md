# NFL Week 1 exchange mapping and fee review

Reviewed September 6–7, 2026. The generated
[collection configuration](../config/runtime_nfl_week1.json) joins **299 Kalshi
contracts** to exact Polymarket outcomes across all **16 Week 1 fixtures**.
The [machine-readable review](nfl_week1_mapping_review.json) lists every unmatched
contract and hashes the retained public response envelopes.

| Full-game market | Kalshi Week 1 contracts | Matched to Polymarket |
| --- | ---: | ---: |
| Moneyline | 32 | 32 |
| Spread | 404 | 81 |
| Total | 304 | 186 |

The unmatched 441 Week 1 contracts have no exact listed payoff in the captured
Polymarket set. Another 32 Kalshi moneylines belong to Week 2 and are excluded.
There is no nearest-line substitution or mixing of full games, halves, quarters,
team totals and player props. Source acquisition and matching can be rerun with
`scripts/configure_nfl.py`; this is no longer a manual token-ID worksheet.

## Identity and payoff checks

- Discover the actual `nfl-2026` season series (12185) and select `eventWeek=1`.
  Polymarket's sports index still pointed to the 2025 series during this review.
- Use `startTime` for kickoff and cross-check its Eastern date against
  `eventDate` and the Kalshi event's scheduled date. `startDate` is a listing
  date; a UTC date in a Polymarket slug can be the following day. Kalshi expected
  expiry is not kickoff. The opener starts September 10 at 00:20 UTC, which is
  September 9 at 7:20 p.m. Chicago time.
- Resolve teams from venue identifiers and fixture team metadata, including
  `JAX`/`JAC` and `LA`/`LAR`. Reject unknown or ambiguous identities.
- Use the numerical `floor_strike`, not rounded ticker suffixes. The signed
  Polymarket spread belongs to outcome zero. Cross-check the market's prose
  settlement threshold and selected token against that signed line. Integer
  lines require a separate push model and are excluded.
- Kalshi moneylines and the matched Polymarket tokens pay 50¢ per team on a
  completed tied game. Kalshi combo settlements multiply the actual underlying
  payout values, including scalar settlements. The product of expected leg
  payouts is therefore an independence assumption about payoff values, not
  necessarily a product of outright-win probabilities.

Sources: [Kalshi NFL game terms](https://assets.kalshi.com/contract_terms/NFLGAME.pdf),
[spread terms](https://assets.kalshi.com/contract_terms/NFLSPREAD.pdf),
[total terms](https://assets.kalshi.com/contract_terms/NFLTOTAL.pdf),
[combo settlement](https://help.kalshi.com/en/articles/13823820-combos), and the
[Polymarket opener](https://polymarket.com/sports/nfl/nfl-ne-sea-2026-09-10).
Individual market descriptions and token choices are retained in each mapping.

## Fees and quote grids

| Input or execution series | Verified coefficient per share |
| --- | --- |
| Kalshi NFL moneyline/spread/total taker | `0.07 × p × (1-p)` |
| Matched Polymarket NFL taker | `0.05 × p × (1-p)` |
| Kalshi `KXMVECROSSCATEGORY0-SHARD1` maker | Zero |
| Kalshi `KXMVECROSSCATEGORY-SHARD1` maker | `0.035 × p × (1-p)` |

The published Kalshi schedule excludes uncorrelated NFL combos from its general
combo maker-fee row. The zero-fee series metadata confirms that exception.
The RFQ collection ticker can still be the nonzero-fee collection, so routing
uses the resulting market's exact series prefix and a hyphen boundary.
[Kalshi fee schedule](https://kalshi.com/docs/kalshi-fee-schedule.pdf).

Polymarket's current NFL `feeSchedule` fields specify coefficient 0.05 and
exponent 1. Its July 10 changelog confirms the increase from 0.03. Legacy CLOB
base-fee fields differ; they are not used to overwrite the market fee schedule.
[Polymarket changelog](https://docs.polymarket.com/changelog/predictions).

Sampled actual markets in both combo series use these dollar-price grids:

| Start, inclusive | End, exclusive | Step |
| ---: | ---: | ---: |
| 0.0000 | 0.0100 | 0.0001 |
| 0.0100 | 0.9900 | 0.0010 |
| 0.9900 | 1.0000 | 0.0001 |

The runtime requires prices strictly between zero and one. Each grid records its
actual market source. This is sample-verified series configuration; per-market
grid validation remains necessary before a future live order adapter submits.
Fee metadata expires after 24 hours or at the next scheduled Kalshi fee change,
whichever comes first. Expiry inhibits pricing while raw collection continues.

## Remaining pricing work

These are collection mappings and reviewed normal-game exchange payoffs.
Every mapping carries `pricing_block_reason=pinnacle_payoff_mapping_unreviewed`.
Supplying an odds number alone must not silently clear that gate.

Pinnacle's provider-specific game IDs, full-game/OT rules, paired sides, currency,
limits, suspension semantics and push rules must be matched when the feed is
available. If a two-way moneyline refunds ties, its de-vig probability is
conditional on a non-tie. It does not by itself identify the half-payout fair:
with tie probability `t` and conditional win probability `q`, that expected
payout is `(1-t)q + 0.5t`. No tie probability is invented here.

Exceptional settlements also differ: Kalshi has 48-hour and discretionary fair
price provisions, while the captured Polymarket rules keep postponed games open
and settle canceled games 50–50. A fixture-status/exception policy must handle
that basis before these are treated as globally identical payoffs. Already
settled RFQ legs are explicitly skipped pending scalar-leg pricing support.

The $10,000 capital base is retained. User risk caps are still unset. The runtime
has no order-submission adapter, ticket cap or combo-probability restriction.

## Refresh and collect

Use a new raw directory and experiment database for each refreshed configuration:

```sh
.venv/bin/python scripts/configure_nfl.py \
  --raw-dir data/raw/nfl_week1_refresh_001 --refresh \
  --combo-sample KXMVECROSSCATEGORY-SHARD1-S20265B09DE8FC08-15BCF6B717A \
  --combo-sample KXMVECROSSCATEGORY0-SHARD1-S20266DFD5D79268-C2DF69E37F4 \
  --out-config config/runtime_nfl_week1.json \
  --out-review research/nfl_week1_mapping_review.json
.venv/bin/python scripts/runtime.py --db runs/nfl_next/events.sqlite \
  --config config/runtime_nfl_week1.json init
caffeinate -i .venv/bin/python scripts/runtime.py --db runs/nfl_next/events.sqlite \
  --config config/runtime_nfl_week1.json run --seconds 3600
.venv/bin/python scripts/review_runtime.py --db runs/nfl_next/events.sqlite \
  --out runs/nfl_next/review
```

On macOS, `caffeinate -i` prevents idle sleep while the command runs; it does not
make a laptop a reliable always-on server. The runtime now bounds duration by
both monotonic and calendar time so sleep cannot silently extend the session.
Use an always-on host for the next uninterrupted soak and Wednesday's session.
