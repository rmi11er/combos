# Larger MLB validation and parallel NFL work

The expanded study is running under the frozen [31-date plan](../config/mlb_validation_20260907_expanded.json). Every second complete day from July 1 through August 30 is included: 16 July development dates and 15 August validation dates. The previously inspected September 5 result is a separately labeled reference. The original five-date screen is a subset and is only a pipeline check, not sufficient evidence to choose risk limits.

## Comparisons fixed before older results

Kalshi, Polymarket, fixed 50/50 per-leg probabilities and fixed 25/75 per-leg probabilities are compared on the same complete-source intersection. The fixed blends are explicitly exchange-only experiments; they are not substitutes for the requested three-source liquidity-weighted model. MLB Pinnacle history remains unavailable under the recorded API access response.

For each complete date, the entry sweep compares selling every priced print with 0, 0.1, 0.3 and 0.5 cents of net edge per combo contract, and a distinct 0.3 cents per leg variant. The current model uses **0.3 cents per combo contract after maker fees**. Every alternative runs with unlimited funding and with the same $10,000 initial funding / $100 underlying / $100 combo / $250 fixture limits. A separate fixed risk sweep is also saved for each date; it does not select or deploy new limits.

Source coverage, selected/rejected outcomes, unresolved-outcome bounds, fees, model edge, YES premium, payout notional, peak cash, concentration and drawdown remain separate metrics. Whole-day acquisition and native metadata completeness are mandatory before a date becomes a replay. The benchmark is every priceable eligible 2–4-leg, distinct-game, full-game pregame YES-taker print on the comparison universe. Broader all-leg/phase trade classifications remain in the underlying daily cohort and are not confused with the model's universe.

The price models and comparison grid are frozen before examining the older dates. July is the development block; August is held out. Shared underlying fixtures are purged across that boundary, and an interim report explicitly marks purging provisional until development acquisition is complete. Missing primary models cannot silently turn validation into a different-source comparison. The old September two-model result remains diagnostic.

The per-date reports are independent funded-day experiments. A separate longitudinal replay now supplies the requested continuing-capital view: each model and threshold gets one ledger spanning all observed dates, so an unsettled position continues to consume cash on the next date and settlements during gaps release cash causally. It does not reset $10k each morning. It trades only on the observed dates; this is not a full-calendar opportunity census. Gaps are never inserted as zero-return observations in statistics. Eventual known settlement P&L is attributed back to trade time for review, while actual settlement time governs cash release. Descriptive variance uses the appropriate funding basis; neither print count nor the visible smoothness of a curve establishes significance.

## Risk policy decision deferred

The user explicitly requires a much larger dataset before setting risk limits. The September sweep diagnoses accounting and capacity only. Even selling every priced print under current limits deploys only about $1,792 that day, so dropping the price filter alone cannot fill the capital budget. Choosing caps or thresholds by that day's P&L would be an invalid use of the sweep.

Select acceptable game/underlying loss and drawdown budgets using broader development data, then assess held-out exposure and results. Idle cash is not evidence of a pricing mistake or a reason to force deployment. Existing $10k is initial funding, with actually settled profits reinvestable; a separate hard maximum committed-cash ceiling is not currently imposed. That policy distinction remains part of the pre-launch review.

## Running jobs and outputs

- `scripts/mlb_public_day_acquire.py` is collecting the original five full dates, sharing public Kalshi read pacing with other collectors.
- `scripts/mlb_collection_queue.py` waits for those dates to complete, then collects the additional 26 dates under a distinct immutable acquisition plan. Its bounded additional request budget is 400,000 public GETs; a budget exhaustion leaves coverage incomplete and requires review/resume.
- `scripts/mlb_historical_batch.py` consumes complete dates as they arrive, performs metadata recovery, exchange acquisition, dated-fee replay, model plots, entry sweeps, risk sweeps and versioned multi-date validation. It never turns partial pages into a smaller backtest. Permanent mapping/data/budget failures stop with retained logs; transient retries are bounded.
- `scripts/mlb_longitudinal_sweep.py` independently watches completed, hash-verified batch outputs and writes continuing-ledger comparisons across the observed dates. Its fixed-grid and current-0.3c-versus-sell-all plots have separate funded and unlimited versions, retaining cumulative known P&L, model edge and committed cash. Unknown-outcome bounds and observed-date P&L variance remain explicit. Eight tests include positions retained across dates and settlements releasing cash during unobserved gaps; four synthetic charts were visually checked and are labeled synthetic.

The principal status files are:

- `runs/mlb_historical_20260907/daily_acquisition/expanded_queue_status.json`
- `runs/mlb_historical_20260907/dated_fee_primary/batch_status.json`
- `runs/mlb_historical_20260907/daily_acquisition/acquire.log`
- `runs/mlb_historical_20260907/historical_batch.log`
- `runs/mlb_historical_20260907/longitudinal/watch_status.json`

Longitudinal `latest.json` points to the newest completed immutable output version; each version includes `funded.png`, `unlimited.png`, `selection_funded.png`, `selection_unlimited.png`, summary metrics and compressed decision/fill/curve ledgers. A watcher with no ready input correctly reports waiting rather than publishing empty performance as a completed historical result.

Per-date outputs go to `runs/mlb_historical_20260907/dated_fee_primary/YYYY-MM-DD/`, with `common_model_report`, `entry_sweep` and `risk_capacity` subdirectories. `batch_status.json` points to the latest cumulative validation. A running or complete tape collector does not by itself establish completed pricing, backtesting or stable edge.

Code, input and policy hashes plus code snapshots make the job reviewable. A changed frozen dependency stops the batch instead of silently mixing implementations. Independent NFL scripts are outside the MLB dependency snapshot. The full suite passed **337 tests** at launch.

Integration checks subsequently raised the complete suite to **412 passing tests**. The first complete July day exposed two operational issues before pricing: child interpreter symlink resolution lost the virtual environment, and sequential current-first metadata routing would exceed the original per-attempt budget for 506,899 combo definitions. Child stages now preserve the venv path; old-date metadata uses four workers, historical-first routing with fallback, and a bounded 15,000-request allowance per attempt. Existing caches and prior attempt snapshots were retained. The frozen dependency list now covers the actual imported MLB modules, with an import-closure test, so separately developed unused models cannot invalidate the running baseline.

The NFL acquisition also exposed the historical candle schema: native historical `close: "0.3600"` is a dollar price, while recent captures use `close_dollars`. The shared parser now validates endpoint/schema provenance, rejects ambiguous unit representations and conflicting aliases, and logs parse failures. All 143,562 retained NFL candle states across 20 tickers parse under the reviewed schema. This prevents valid older data from silently becoming missing-price exclusions.

The user's [conditional Pinnacle–Polymarket consensus hypothesis](CONDITIONAL_CONSENSUS_HYPOTHESIS.md) is implemented as a separate, unfitted research component. Agreement between those sources can reduce Kalshi's normalized weight when its price differs modestly, including within overlapping fee bands. It preserves conservative uncertainty and requires explicit timestamp, payoff and capacity evidence. Historical depth assumptions need acknowledgment and provenance; live imputation remains prohibited. Neither the running frozen baseline nor production weights are changed by this unused component.

## Historical fee uncertainty

All 32 dated fee files are schema-valid, with 83 overrides reconciled to cached native fee-change evidence. Kalshi's [fee-change endpoint](https://docs.kalshi.com/api-reference/exchange/get-series-fee-changes) supports retrieving historical records. Known records establish dated overrides; periods before the first available record remain assumptions. The baseline research scenario uses a 0.035 combo-maker parameter, 0.07 July leg taker / 0.035 later where applicable, and native PM market schedules with unverified historical effective dates. Raw evidence is retained under `historical_fee_evidence` and `exchange/series`.

These are explicitly **unverified research scenarios**, not a claim that September terms applied in July. Fee sensitivity is supported through dated scenario overrides and replay recomputation; additional fee scenarios are not yet automatically queued by the primary batch. Historical cash-rounding conventions and ordinary-game payoff mappings also remain declared assumptions. Fee/payoff verification and sensitivity belong in any profitability conclusion.

## NFL parallel task

A separate agent is acquiring the analogous 2025-season NFL Wild Card and Divisional study: trading January 5–18, 2026, with fixtures limited to the first two playoff rounds. Round dates are January 10–12 and January 17–18, respectively. [Official NFL dates](https://www.nfl.com/news/2026-national-football-league-important-dates).

The agent is checking Pinnacle historical access on the subscribed football feed, exact Kalshi/PM matches and dated fees before claiming three-source coverage. Historical NFL and MLB models, mappings, performance and eventual risk settings remain separate. Only public/historical research acquisition is authorized here; no orders, subscription changes or new live limits are being applied.
