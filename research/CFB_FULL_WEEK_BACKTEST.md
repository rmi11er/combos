# All available CFB week data — September 7, 2026

Follow-up: [fees, $50 premium, market benchmarks and selection audit](CFB_PERFORMANCE_AUDIT.md)
adds the full seller-universe curve and all/selected/rejected comparisons.

The 20-fixture / 23-print pilot restriction is removed. The evaluator now uses
every eligible retained print, with independent single-venue benchmarks and an
explicit common-cohort comparison. Known eventual settlement P&L and accepted
model edge accumulate at trade time; allocation and cash release remain causal
at actual settlement. No ticket cap or percentage-value filter is introduced.

## Data coverage

| Stage | Actual retained prints |
|---|---:|
| All observed combos | 1,565,981 |
| Pure CFB, all leg counts | 335,947 |
| Nonplayer, 2–4 legs | 176,474 |
| Distinct fixtures | 146,096 |
| Known pregame start, at least 60 seconds remaining | 61,856 |
| YES-taker side used by this maker-NO replay | 61,205 |
| Kalshi prices available | 61,205 |
| Pinnacle prices available | 9,873 |
| Both blend models available | 9,511 |
| Common four-model cohort | 9,511 |

Saturday is a complete public-print census. Other dates contain every retained
sampled interval, **not complete days**. No observed trade is multiplied by the
old volume-estimation weight of 60. Accordingly, these are all available data,
not a claim that the historical collection is a full seven-day census or that
the omitted intervals had no trades. The missing intervals affect allocation
and Sharpe; these remain diagnostic observed-flow replays.

The Polymarket matcher no longer hardcodes September 5. Native metadata covers
all 4,886 eligible underlying markets. Expanded provider matching preserves
exact kickoff equality and six reviewed provider-name aliases; it does not
guess through ambiguous team or schedule matches. All 184 selected fixtures /
2,287 exact exchange-mapped tickers were considered without minimum line count
or hash selection. Pinnacle supplied 147 fixture histories / 514,704 rows; 37
fixtures returned explicit 404s. Independent Pinnacle pricing matches 1,126
underlying payoffs; the complete three-venue join matches 827.

The collector finished 7,115 mapped-history captures, 822 focused full-game
coverage captures and 847 extended-nonplayer captures. All final requests passed
HTTP/schema validation; transient rate limits were repaired. Successful empty
responses, missing prior states and inactive quotes remain distinct from request
failure. Conflicting native historical timestamps exclude the affected payoff;
they no longer abort the entire venue or unrelated fixture markets.

Pinnacle pricing excludes 41,554 prints for unavailable exact payoffs, 7,503 for
no prior state and 2,275 for a latest inactive state. Blends exclude 46,427 for
incomplete three-venue mappings, 3,880 for no prior state and 1,387 for inactivity.
Those are data/pricing restrictions, not another arbitrary trade sample.

## Plots and results

| Rule | $10,000 and concentration limits | Unlimited capital/concentration |
|---|---|---|
| Current stressed reservation price | [Plot](../runs/cfb_full_week_20260907/backtests_settlement_refreshed/stressed/constrained.png) | [Plot](../runs/cfb_full_week_20260907/backtests_settlement_refreshed/stressed/unconstrained.png) |
| Point-price diagnostic | [Plot](../runs/cfb_full_week_20260907/backtests_settlement_refreshed/point_diagnostic/constrained.png) | [Plot](../runs/cfb_full_week_20260907/backtests_settlement_refreshed/point_diagnostic/unconstrained.png) |
| Point-price diagnostic, identical 9,511-print cohort | [Plot](../runs/cfb_full_week_20260907/backtests_settlement_refreshed/common_point_diagnostic/constrained.png) | [Plot](../runs/cfb_full_week_20260907/backtests_settlement_refreshed/common_point_diagnostic/unconstrained.png) |

The point-price diagnostic retains fees, the 0.3-cent/share minimum edge and
quote guards while removing probability reserves from entry. It does not change
the forward model. Dollar P&L below includes only known outcomes attributed back
to trade time; unresolved outcomes remain explicitly unscored.

| Model | Priced | Constrained fills | Known-outcome P&L | Unlimited fills | Known-outcome P&L |
|---|---:|---:|---:|---:|---:|
| Kalshi | 61,205 | 760 | -$651.35 | 12,915 | -$484,947.17 |
| Pinnacle | 9,873 | 310 | -$437.30 | 3,980 | -$34,107.11 |
| Blend | 9,511 | 243 | -$396.73 | 1,880 | -$48,128.06 |
| Stronger Pinnacle | 9,511 | 251 | -$534.56 | 2,702 | -$46,048.22 |

These models do not all price the same universe. Use the common-cohort plots
for paired comparisons. On that 9,511-print cohort, constrained Kalshi takes 209
prints and loses $446.28; Pinnacle takes 299 and loses $662.74. Blends are
unchanged because the common cohort already equals their priced universe.

The constrained blend has 6 unresolved outcomes and $96.59 still committed;
the unlimited blend has 100 unresolved outcomes and $8,617.29 committed. Its
point-edge totals are +$40.72 and +$3,470.99, respectively, despite negative
known-outcome P&L. Its peak commitments are $2,674.04 and $190,629.03. This is
evidence to investigate calibration, selected flow and concentration; estimated
edge is not money earned. Unlimited funding is a counterfactual exposure
diagnostic, not a return achievable on $10,000.

Under the actual stressed entry rule, Pinnacle and both blends still take zero
prints. Kalshi takes 47 constrained or 123 unlimited, with known-outcome P&L
of -$180.49 or -$121,213.65. The sharp-source models' zero entries therefore
persist across thousands of evaluated prices; the original small sample was
not the only reason for no entries.

Each equity legend includes descriptive annualized daily Sharpe and sample
daily-return variance in bp². Returns use trade-attributed known-outcome daily
P&L / $10,000 reporting base, with idle calendar days included. The constrained
blend has Sharpe -5.98 and daily variance 32,743.19 bp²; unlimited it has -8.50
and about 2.39e8 bp². Seven days, incomplete non-Saturday capture, shared fixtures
and unresolved outcomes make these provisional descriptive statistics.

All executions remain hypothetical full fills at observed public YES-taker
prices. They do not measure whether our RFQ quote would have won. The deployed
pricing, submission or risk configuration has not changed.

## Settlement refresh and diagnostics

A public metadata refresh returned all 1,684 previously unresolved eligible
combo definitions; 1,063 now have native settlement timestamps and values.
The 17 requests had no failures. New input files update only settlement fields;
all 90,100 forecasts, trade terms, identifiers and eligibility decisions were
verified unchanged. Original inputs and reports remain retained. Fill counts
were unchanged in this refresh, while P&L and remaining commitments changed.
The remaining unknown outcomes are not assumed to be future games.

Known settlements after the trade-week end are attributed back to trade time
in the retrospective curves. The unlimited blend therefore reports -$48,128.06
of trade-attributed P&L versus -$46,636.23 actually settled by the window end.
These fields are intentionally separate; no future settlement finances an earlier
trade. See the [forensic review](CFB_FULL_WEEK_DIAGNOSTICS.md) for concentrated
losses and native market-quality checks. All 177 tests pass; final report input
and evaluator-code hashes match, and both portfolio figures were visually checked.

## Reproduce

Collection and pricing are separate and resumable. Raw responses, request
ranges, exact mappings and manifests are retained in
`runs/cfb_full_week_20260907/`. The temporary key file was retained for subsequent
authorized historical work and is not copied into research outputs.

```sh
.venv/bin/python scripts/cfb_full_cohort.py \
  --mapping runs/cfb_full_week_20260907/polymarket_mapping.json
.venv/bin/python scripts/cfb_full_week_replay.py \
  --out runs/cfb_full_week_20260907/replay
.venv/bin/python scripts/refresh_replay_settlements.py
.venv/bin/python scripts/backtest_report.py \
  --input runs/cfb_full_week_20260907/replay_settlement_refreshed/opportunities.json \
  --config config/backtest_stressed.json \
  --out runs/cfb_full_week_20260907/backtests_settlement_refreshed/stressed
.venv/bin/python scripts/backtest_report.py \
  --input runs/cfb_full_week_20260907/replay_settlement_refreshed/opportunities.json \
  --config config/backtest_point_diagnostic.json \
  --out runs/cfb_full_week_20260907/backtests_settlement_refreshed/point_diagnostic
.venv/bin/python scripts/backtest_report.py \
  --input runs/cfb_full_week_20260907/replay_settlement_refreshed/common_opportunities.json \
  --config config/backtest_point_diagnostic.json \
  --out runs/cfb_full_week_20260907/backtests_settlement_refreshed/common_point_diagnostic
.venv/bin/python -m pytest -q
```

New models can provide the same normalized opportunity schema. New inputs or
portfolio configurations require a new experiment output directory. Full
pricing context and per-model exclusion reasons are retained independently of
allocation decisions; each backtest emits curves, daily statistics, fills,
decisions, summaries and input/config/code hashes.

## MLB access check

Direct MLB history calls were made using a native fixture ID published by
OddsPapi. `pinnacle` returned 403 for a restricted bookmaker; `pinnacle+30`
returned 403 with `You do not have access to sport ID 13`. The before/after
account counter did not change. Thus history is quota-free on these calls,
but the current key's cross-sport historical access was denied. This conclusion
comes from the history endpoint itself, not from the live subscription listing
or the separate fixture-discovery rejection.

See `runs/oddspapi_baseball_direct_history_20260907/summary.json` and the two
redacted historical responses. No MLB three-venue performance result is claimed.
The bounded public MLB probe and validation design remain available in
[the MLB plan](MLB_HISTORICAL_VALIDATION_PLAN.md).
