# Native MLB cohort, September 7, 2026

The retained public tape contains **318,536 pure-MLB prints**, classified before
any price-source selection. This is a substantial immediate baseline, not the
requested complete July–September dataset. September 5 is a complete Chicago
calendar-day census. August 31–September 4 and September 6 contain the previously
selected, fully paginated 15-second cells (four per hour). These observations
always have replay weight one; no missing hours are fabricated.

`runs/mlb_historical_20260907/cohort/summary.json` records all 600 source windows,
their compressed-file SHA256 values, census/sample designation, date/leg/family/
structure cuts, fee assumptions, and acquisition limits. Every one of the
1,565,981 scanned combo prints has a known native definition in the prior cache.
159,450 unique pure-MLB definitions are retained in `combo_markets.json.gz` and
`metadata_index.sqlite`. The universe uses the exchange's KXMVE-prefix tape;
nonprefix composite instruments are outside this explicit enumeration rule.

## Reusable inputs

- `universe_trades.jsonl.gz`: all MLB leg counts, trade sides, market families and
  same-game structures, with native economic fields, official combo settlement,
  per-fill maker fees, classification and source interval.
- `candidate_trades.jsonl.gz`: **78,004** full-game moneyline/spread/total prints
  preceding the earliest native scheduled start. Includes all leg counts,
  same-game structures and both taker sides so downstream models can make
  explicit exclusions and produce comparison cuts.
- `underlying_tickers.json`: union of **1,825** candidate underlying markets,
  with no fixture, line, trade-size or source-availability cap. All 1,825 native
  definitions were recovered in **19 public unauthenticated GETs**; no missing
  market remains. Full responses and checksums are in `underlying_batches/` and
  `underlying_acquisition.json`.
- `all_universe_underlying_tickers.json`: **17,130** underlying identities across
  the broader universe, including props. Their complete individual metadata
  has not been downloaded; native combo definitions and settlements are kept.

Native MLB ticker tokens encode the original scheduled clock in New York time,
confirmed against acquired primary rules. `occurrence_datetime` can denote the
expected game finish and must not substitute for start. The cohort explicitly
labels its pregame flag as a scheduled-time proxy; it does not assert possession
of historically versioned schedule updates or actual first-pitch observations.
Doubleheader tokens include distinct scheduled times and remain distinct.

Unknown series remain unknown. Only GAME/SPREAD/TOTAL are designated full-game
core; unrecognized families are never silently declared no-player-prop. Any
repeated fixture is a same-game-containing combo. It is retained, but a product
of marginal probabilities is not a validated same-game joint model.

Only YES-taker prints correspond to the hypothesized maker sale of a combo.
NO-taker prints remain in the raw cohort for other studies. The convenience
seller-P&L column represents the hypothetical seller economics at either
observed price; reports must apply the YES-taker filter explicitly. Payout
notional is face quantity, not money won by buyers.

## September 5 native seller benchmark

The census contains **262,584 YES-taker prints** with **$8.304 million YES
premium** and **$272.857 million face notional**. Known-settlement seller P&L is
approximately **+$1.643 million**, after approximately **$203,926 fees** across
all prints. There are **181 unknown-settlement prints**, so this is not a final
complete-cohort profit figure. Reports should give their possible liability
bounds and keep their fees/cash commitments visible.

Known-settlement P&L is about +$1.682 million for distinct-game combos and
−$39,460 for combos containing repeated fixtures. By leg count it is +$353,385
(two), +$302,488 (three), +$164,079 (four), and +$822,809 (five-plus). These are
counterfactual observed-price sales, not observed industry maker profits or
achievable RFQ fills. Shared games, ticket-size concentration and missing final
settlements require the same scrutiny applied to CFB.

Fees use the repository's exact cash-rounded Kalshi maker calculation with a
0.035 rate and 0.0001 account precision. Raw quantities/prices remain intact for
rate/account-precision sensitivity. Historical-date fee terms must be verified
before extending this assumption to July dates.

## Larger history acquisition

`scripts/mlb_public_day_acquire.py` provides zero-network planning and resumable
complete-day collection with explicit `/historical/cutoff` routing, hourly
partitions, strict page-cursor validation, request-attempt bounds, raw compressed
responses, checksums and completion manifests. It never calls a paid provider or
an order endpoint. An exhausted request allowance produces an incomplete
manifest rather than treating the last page as complete. The shared repository
pacer limits request starts to roughly 5.5 per second across collectors.

The fixed, outcome-blind expansion plan chooses fortnightly Wednesdays from
July 1 (July 1/15/29 and August 12/26), plus the existing September 5 census.
This is an explicitly sampled-day design, not the complete 68-day window.
Default execution only writes the plan and makes zero requests. No additional
full-day download was launched during this cohort build.

The existing September 5 all-market scan required **11,875 pages** for
**11,864,448 raw rows** (410 MB compressed). The trade endpoint has only an exact
market-ticker filter, not a combo-prefix or series filter. At comparable activity,
a new full day costs roughly 12,000 public GETs, at least 36 minutes of pacing,
plus metadata/history requests. Earlier dates can differ substantially. A full
July–September census is thus materially larger than a short historical probe.

Example bounded acquisition, resumable by repeating the command:

```sh
.venv/bin/python scripts/mlb_public_day_acquire.py --execute --max-new-requests 5000
```

The default fixed plan is saved under
`runs/mlb_historical_20260907/daily_acquisition/plan.json`. Changing dates requires
a new output directory. If the moving historical cutoff changes the route of a
previous partition, the collector fails visibly on the route mismatch rather
than silently accepting a potentially different cached query.

Eight focused tests cover scheduled-time parsing, doubleheaders, same-game
classification, unknown families, mixed sports, historical-cutoff splitting,
pagination exhaustion/resumption and repeated cursors. The cohort build is
reproducible from cached responses with no new API calls:

```sh
.venv/bin/python scripts/mlb_native_cohort.py --fetch-underlying
.venv/bin/python -m pytest -q tests/test_mlb_native_cohort.py tests/test_mlb_public_day_acquire.py
```
