# July 1 MLB public history probe

Completed September 7, 2026 with **10 public unauthenticated GETs total** across
resumptions. No OddsPapi calls or subscription changes. Raw responses, exact
queries, hashes and the script hash are in
`runs/mlb_history_probe_20260701/summary.json` and `raw/`.

Three fixed July 1 windows, 17:00, 20:00 and 23:00 UTC, each fifteen seconds,
returned 559 combo prints involving 512 tickers. Every trade response has a next
cursor, so these are **incomplete first-page samples**, not window censuses or
volume estimates. The observed historical cutoff was July 9: July 1 trades
require `/historical/trades`, and settled definitions require
`/historical/markets`. Both worked. Historical metadata supports ticker batches.

The first 100 sorted combo tickers were selected without inspecting outcomes.
All 100 definitions were recovered across the live and historical tiers. They
classify 105 of the 559 observed combo prints; 454 remain unclassified because
the probe stopped at its request budget. Among classified prints:

| Scope | Observed prints |
|---|---:|
| All pure MLB | 21 |
| Two-leg pure MLB | 3 |
| Three-leg pure MLB | 9 |
| Four-leg pure MLB | 3 |
| Five-plus-leg pure MLB | 6 |
| Two–four legs, full-game moneyline/spread/total families, distinct fixture tokens | 9 |

The 21 pure-MLB prints total $2,126.25 YES premium and $16,740.25 payout face
notional. These include player props and same-game combinations and cannot be
called the strategy opportunity set. The nine narrower candidate prints require
21 unique underlying leg histories, saved in `candidate_cohort.json`. Their
pregame eligibility and exact settlement equivalence are not yet validated.
`combo_sample.json` preserves prints, definitions and all classifications.

A Polymarket metadata query returned 80 MLB-slug events; 28 contained July 1 in
their slug, chiefly first-five and prop event groups. The response also contained
older event slugs, demonstrating that end-date filtering alone is insufficient
for game-date identity. One initial price-history probe picked an older event
and returned zero observations; that is not evidence of missing July history.
The script now requires the requested date in the candidate event slug. Its
correct-date history probe and Kalshi underlying probes were deferred because
the ten-request budget was exhausted.

Next acquisition should finish pagination and retrieve all remaining combo
definitions before forming the union of required leg histories. Roughly five
100-ticker historical batches would cover the current 412 unqueried identities,
with a live-tier check for any missing or later-settling market. Larger backtests
need complete chosen days, not scaled first-page samples. This probe is direct
evidence that July combo history is recoverable, not a backtest result.

The football live subscription does not establish whether baseball historical
access is allowed. A separate authenticated history probe must answer that
question directly; do not infer a restriction or require an upgrade from the
live sport list alone.

Reproduce entirely from cached responses, making zero additional requests:

```sh
.venv/bin/python scripts/mlb_history_probe.py
```

The script enforces a persistent ten-request ceiling and records deferred
requests as `budget_exhausted`; it does not silently retry failed requests or
expand the budget.
