# NFL playoff history: independent January study

The study covers trading January 5–18, 2026 in America/Chicago and the ten games in the [Wild Card](https://www.nfl.com/news/nfl-reveals-2026-wild-card-weekend-schedule) and [Divisional](https://www.nfl.com/news/nfl-announces-schedule-for-upcoming-2025-divisional-round) rounds. `config/nfl_playoffs_history_2026.json` freezes the target identities and original schedules. Primary scope is full-game non-player, 2–4 distinct fixtures, with a 60-second pregame cutoff. Other pure-NFL prints and scope classifications are retained for later comparisons; NFL parameters and results remain separate from MLB.

## Initial availability

OddsPapi fixture discovery matched all ten exact NFL team/date identities. All ten unfiltered `pinnacle+30` historical queries returned HTTP 404, `No historical odds found`. One `pinnacle` query returned HTTP 403, restricted bookmaker, and was not retried. This is different from the prior MLB sport-entitlement 403. The full probe made 20 read attempts including account snapshots, one fixture discovery, an initial player-filtered request and a single rate-limit retry; the active football request count increased by one, from 27 to 28. No further provider requests are planned until the archive/access question is resolved. A [support draft](ODDSPAPI_NFL_JANUARY_SUPPORT_DRAFT.md) is saved and has not been sent.

Provider scheduled starts differ from the original official announcements for three games. The collector preserves both clocks and the differences. The scope uses the earlier original schedule, so a later provider clock cannot admit already-started play. The provider's 49ers–Seahawks schedule is twenty minutes later even though its recorded true start is near the official clock; this reinforces that `startTime` and `trueStartTime` need distinct treatment.

Kalshi's historical NFL moneyline catalog contains all ten fixtures, with 20 team-side contracts. Its native codes use `LA` for the Rams and `JAC` for Jacksonville. Polymarket's `nfl-2025` series ID is `10187`; the closed-event query returned all ten matching events. All have `eventWeek=13`, so that field is not used as a playoff round identifier. Team names, native aliases and Eastern event dates establish the join.

`scripts/nfl_playoffs_exchange_review.py` verifies the saved identities and produces `runs/nfl_playoffs_history_20260907/exchange_review.json`, including all 20 moneyline identity candidates and source hashes. Full requested moneyline history has now been collected for both sides of all ten games: 152 public queries, all HTTP 200, with 108 nonempty and 44 empty windows. Each identity's history starts with a January 4 seed-search day and ends at the earlier official/PM kickoff minus 60 seconds. Three-day chunks respect the historical endpoint limits. Empty pre-listing windows do not establish price availability at every earlier trade.

The raw archives contain 143,594 Kalshi candle rows and 157,044 Polymarket points. The offline, hash-checked audit finds 143,562 unique valid Kalshi bid/ask states after removing repeated chunk boundaries, with no missing or crossed quote states, and 157,044 valid unique PM points. All twenty identities have valid states on each venue. Historical Kalshi candles use fixed-point dollar strings in `yes_bid.close` and `yes_ask.close`; the shared historical parser now recognizes the native endpoint schema explicitly. It does not guess whether ambiguous integer values are cents or dollars. The audit records the parser hash and per-identity first/last source clocks in `exchange_history/availability_review.json`.

The sample PM market reports `feesEnabled=false`; January cannot inherit September's sports fees. Kalshi and PM sample moneyline rules both split actual ties 50/50, while their cancellation/postponement terms differ. Postseason games normally continue until a winner, but exceptional outcomes, exact integer-line pushes and historical fee effective dates still need explicit review. No three-source pricing or net-P&L backtest is claimed from these probes.

## Durable collection and resumption

`scripts/nfl_playoffs_public_acquire.py` uses the established shared Kalshi pager/rate limiter and an independent NFL output directory. It requests full public-tape hourly partitions, because the endpoint cannot filter by combo sport. Every partition retains response hashes and complete cursor chains. Only terminal pages can mark a partition complete; budget exhaustion remains incomplete. The overall window has 336 hourly partitions. A lock prevents duplicate collectors; `progress.json` records PID, status, counts and timestamps every thirty seconds or partition completion.

The authorized collector runs with two workers and at most 150,000 new public GET attempts, sharing the global 0.18-second pace with MLB. No odds-provider calls or order endpoints occur in this collector. The exact resumption command, after confirming the prior PID is no longer running, is:

```sh
.venv/bin/python scripts/nfl_playoffs_public_acquire.py --out runs/nfl_playoffs_history_20260907/public --execute --max-new-requests 150000 --workers 2
```

That budget is per invocation; do not silently restart with a fresh allowance if the authorized budget is exhausted. The frozen plan/config/code hashes must match on resume. Track `runs/nfl_playoffs_history_20260907/public/progress.json` and each date's partition manifests. A crashed worker can leave a stale running status, so check the recorded PID as well.

The automatic watcher verifies each complete day's page hashes, pagination and calendar coverage, then recovers all native combo definitions with the existing cached metadata adapter. Historical-first lookup uses two workers and a 15,000-GET cap per day that persists across resumes. It writes a broad pure-NFL universe plus the exact primary candidate cohort and underlying ticker list, and explicitly leaves maker fees/net-P&L unset pending a January fee review. Missing metadata fails the cohort instead of silently shrinking the universe. Its frozen code/config closure and output hashes are checked on resume. The watcher runs independently of the collector and writes PID, child command, attempts, failures and completed-day counts in `days/state.json`.

```sh
.venv/bin/python scripts/nfl_playoffs_cohort_watch.py --acquisition runs/nfl_playoffs_history_20260907/public --out runs/nfl_playoffs_history_20260907/days --execute --metadata-budget-per-day 15000 --poll-seconds 30 --max-hours 24
```

January 5 is the first complete day: 1,109,938 public prints, 34,164 unique combo prints across all sports, 4,316 pure-NFL prints, and 789 primary 2–4 distinct-fixture full-game pregame candidates. This is a complete-day population count, not a claim that every candidate has a certified fair or a simulated fill. The watcher preserves the expanding candidate underlying union for exact spread/total acquisition; its initial day includes many alternate lines beyond the twenty moneylines already collected.

The completed exchange-history job can be resumed offline from its matching cached captures with the command below. Its 800-request allowance is persistent across resumes; 152 have been used. The audit command is entirely offline and applies no fee model.

```sh
.venv/bin/python scripts/nfl_playoffs_exchange_history.py --review runs/nfl_playoffs_history_20260907/exchange_review.json --out runs/nfl_playoffs_history_20260907/exchange_history --execute --max-public-requests 800 --workers 2
.venv/bin/python scripts/nfl_playoffs_history_audit.py --input runs/nfl_playoffs_history_20260907/exchange_history
```

Remaining work is exact candidate spread/total mapping and history acquisition, historical fee and ordinary/exceptional payoff review, Pinnacle archive access clarification, and an NFL-specific replay with fixed model/entry/risk alternatives. Moneyline history is complete at the query level; the two-week tape and daily native metadata continue collecting automatically. Historical PM price history contains neither a bid/ask book nor depth, so the earlier historical-only liquidity fallback must remain explicit in a future blended replay. Actual forward/live depth is still required. A conservative 60-second publication allowance is a modeling assumption, not an observed historical feed latency. There is no NFL net-P&L or live-readiness claim yet.
