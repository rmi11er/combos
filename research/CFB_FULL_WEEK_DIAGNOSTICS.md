# First full-cohort CFB replay: forensic diagnostics

## Completed outcome refresh — use these results

The settlement-snapshot issue below was addressed with **17 public batch GETs**:
all 1,684 unresolved eligible combo records were retrieved, 1,063 supplied new
settlements, and 621 remain unresolved in the exchange response. No request
failed. The exporter changed only `settled_at` and `yes_settlement`; all 90,100
priced evaluations retain identical forecasts, prices, quantities, fees and
risk buckets. Every non-settlement row field was compared against the original.
Fill counts were unchanged when the portfolios were rerun.

| Refreshed diagnostic | Fills | Known trade-attributed P&L | Remaining unresolved fills |
|---|---:|---:|---:|
| Point Kalshi, uncapped | 12,915 | **−$484,947.17** | 328 |
| Point blend, uncapped | 1,880 | **−$48,128.06** | 100 |
| Point blend, constrained | 243 | **−$396.73** | 6 |
| Stressed Kalshi, uncapped | 123 | **−$121,213.65** | 8 |
| Stressed Kalshi, constrained | 47 | **−$180.49** | 7 |

The refreshed stressed Kalshi loss still comes from extended markets:
−$121,265.88 across 100 fills, versus +$52.23 across 23 full-game fills. The
repeated first-half combo discussed below still contributes −$84,546.18.
The refreshed ten largest point-blend losses total −$34,368.41; the largest is
−$7,740.31 on a 22,123-share Mississippi/Notre Dame moneyline combo. Its selected
leg outcomes and pregame timing passed the same bounded checks. Updated top-loss
contexts are saved in `cohort/forensic_refreshed_top_losses.json`.

The remaining uncapped blend positions can add at most $2,872.58 under the loose
standalone payout bound, so their outcomes cannot reverse the currently negative
blend result. The earlier before-refresh bounds and largest-loss rankings below
are retained solely as evidence of what the incomplete snapshot showed.

Use `backtests_settlement_refreshed/{stressed,point_diagnostic,common_point_diagnostic}`
for the current plots and metrics. Frozen-price inputs and raw outcome evidence
are under `replay_settlement_refreshed/`; `refresh_summary.json` records the source,
response and refresh-code hashes. The matured-outcome refresh priority is
**complete**; remaining unresolved outcomes must continue to be reported explicitly.

Reproduce the refresh/export with
`.venv/bin/python scripts/refresh_replay_settlements.py`. Cached successful batches
are reused. This preserves the original replay and never reprices a trade.

## Retained forensic snapshot before the refresh

This review uses the first completed full-cohort reports under
`runs/cfb_full_week_20260907/backtests/`. Results below are **before refreshing
older combo settlement snapshots**. It inspected the ten largest known losses
for point-entry Kalshi, point-entry blend and stressed-entry Kalshi, their raw
pricing contexts and native leg outcomes. No parameters or live settings changed.

## What is actually driving the losses

| Unlimited-exposure diagnostic | Fills | Known outcome P&L | Of which extended periods/team totals | Unresolved fills |
|---|---:|---:|---:|---:|
| Point-entry Kalshi | 12,915 | −$437,052.34 | −$335,717.73 | 915 |
| Point-entry blend | 1,880 | −$28,539.22 | Not in this three-venue cohort | 292 |
| Stressed-entry Kalshi | 123 | −$121,235.74 | −$121,283.60 | 10 |

The stressed Kalshi full-game subset has **23 fills and +$47.86** known P&L;
the extended-market subset has 100 fills and −$121,283.60. These are different
market-quality problems, not evidence that delayed Pinnacle caused the large
Kalshi losses: those Kalshi-only evaluations use no Pinnacle inputs.

One two-leg first-half combo accounts for **20 stressed entries and −$84,546.18**,
about 70% of the stressed Kalshi loss. Its legs are North Carolina Central to win
the first half against Elizabeth City State and East Tennessee State to win the
first half against Tusculum. At one representative entry,
`0721b118-ca41-a33a-58ff-d38b33052847`, on September 5 at 06:47:36 UTC:

| Native selected team | First-half YES bid/ask | Same-time full-game YES bid/ask |
|---|---:|---:|
| North Carolina Central | 4c / 15c | 95c / 96c |
| East Tennessee State | 4c / 15c | 94c / 95c |

The first-half quotes' candle ages were about 277 and 397 seconds; full-game
quotes were about 97 seconds old. The public combo YES price was **3.8c** for
**6,157.63 shares**. Buying NO at that print costs $5,931.52 including the modeled
fee. Both first-half contracts and the combo subsequently settled YES, losing
that amount. Several distinct public trade IDs repeat the same quantity and
price. They are recorded executions, not duplicate rows with the same ID; they
do not establish distinct independent customers or independent bets.

The native ticker, rules, selected side and settlement agree in this example.
The source files themselves contain the 4c/15c books. The direct evidence is an
extreme disagreement between related full-game and first-half prices, plus
repeated uncapped exposure. It does **not** establish whether those period books
were thin, manipulated, inaccessible, or simply poor forecasts: historical depth
and contemporaneous execution evidence are absent. Full-game win and first-half
win are different payoffs, so their disagreement is not a strict arbitrage proof.

The ten largest individual point-Kalshi losses total −$106,243.33. The ten largest
point-blend losses total −$26,656.83, approximately 93% of its currently known net
loss. The selected ten worst losses are a diagnostic, not a random sample from
which to estimate forecast bias. Whole-print quantities range into tens of
thousands of shares: these are deliberately uncapped exposure experiments, not
the expected ticket sizes or funding of the $10,000 strategy.

## Settlement and chronology checks

All inspected losing combos' selected leg outcomes agree with their recorded
YES settlement. All inspected entries precede the saved earliest game start.
The ten largest point-Kalshi losses were 7.4–644 minutes before kickoff;
point-blend losses were 17.8–637 minutes before kickoff. No sign reversal,
after-kickoff entry, or incorrect selected-side outcome was identified in this
bounded review. This does not certify every mapping or historical schedule.

The maker-side calculation is consistent: `q × (YES price − YES settlement) −
maker fee`. Retrospective P&L is attributed to trade time for the requested
performance view. Funding and risk release still use actual combo settlement
times, not that retrospective attribution. No accounting defect explaining these
large losses was found in the reviewed paths.

**The outcome snapshot needs completion before interpreting final P&L/Sharpe.**
Among the point-Kalshi run's 915 unresolved fills, **545 fills across 240 combos**
already have every native underlying leg marked settled in the refreshed leg
files. The corresponding point-blend count is **182 fills across 56 combos**, out
of 292 unresolved fills. Their saved combo records still lack settlement times.
Thus some missing outcomes reflect older combo metadata, not only future games.
Refresh those combo records and use exchange settlement timestamps; do not infer
spendable cash from leg settlement times or silently assign unresolved P&L zero.

Before that refresh, the unresolved point-Kalshi positions have aggregate
standalone payout bounds of −$102,254.92 to +$100,604.24 additional P&L. Even the
optimistic bound leaves this uncapped Kalshi ledger negative. The blend's bounds
are −$28,651.36 to +$67,445.53, enough to change its final sign. These are loose
statewise bounds, not forecasts, and shared outcomes make them jointly restrictive.

## What the three-venue comparison does and does not show

On the same 9,511-priceable-print candidate cohort, point Kalshi accepts 844
prints with −$4,620.61 known P&L, while the blend accepts 1,880 with −$28,539.22.
This is a strategy comparison on the same candidates but different selected
trades and exposures. It does not establish that either estimator has better
probability calibration. The broad Kalshi −$437,052 figure must not be compared
directly with the narrow blend −$28,539 figure as evidence of superior blending.

For the ten largest blend losses, native Kalshi candle ages have a median of
107 seconds and maximum 348 seconds; Polymarket state ages have a median of
97 seconds and maximum 119 seconds. Pinnacle raw update ages have a median of
2,284 seconds and maximum 46,870 seconds. Those Pinnacle ages are **last archived
state-change ages**, not observed broken-heartbeat durations. They cannot by
themselves prove the odds were stale or show that the subscription's 30-second
delay caused a loss. Assess that with subsequent exchange markouts, exact archive
availability semantics and source-update logs.

The largest blend loss, −$5,059.41, is one 6,875-share Nevada moneyline plus UCLA
spread combo, priced at 27.1c YES. Its net point edge estimate was only +$43.57;
the stressed-edge estimate was −$256.28. Both legs won. That single realization
is compatible with ordinary binary payout variance; evidence of systematic bias
requires all held-out forecasts and conditional fill outcomes, not the worst loss.

## Research priorities if these curves remain weak

1. **Finish outcomes and separate scopes.** Refresh expired combo snapshots,
   retain unresolved exposure explicitly, and evaluate full-game and extended
   markets separately. Preserve the all-available and common candidate cohorts.
2. **Audit related-market consistency before trusting a midpoint.** The documented
   4c/15c first-half books against 94c–96c full-game favorites are a concrete
   calibration target. Build a coherent period/score model or measured consistency
   diagnostic; do not assume a low nominal spread or recent candle makes a quote
   informative. Forward depth and executable book checks are essential.
3. **Calibrate lag and quote reserves separately.** Treat delayed Pinnacle as a
   prior, test exchange changes as a causal update, and measure subsequent markouts
   conditional on disagreement, volatility, liquidity and time to kickoff. Charge
   for measured uncertainty once rather than loosening every guard to create fills.
4. **Separate estimator error from exposure concentration.** Repeated bets on the
   same half-time outcomes are one clustered risk. The constrained runs limit the
   damage sharply, but limits do not repair an inaccurate fair. Evaluate accepted
   loss distributions, fixture concentration and full-print sizing explicitly.
5. **Measure actual RFQ selection in shadow.** Public prints do not demonstrate
   that our quote would have won that size. Record requests, source books, quote
   latency, cancellations, accepts and markouts. Repeated public prints alone do
   not establish creator spam or justify a creator blacklist.
6. **Validate on held-out days and MLB only after these checks.** Score calibration
   on all matched leg snapshots, including unaccepted candidates; assess portfolio
   uncertainty by day/slate and shared fixtures. Seven-day annualized Sharpe on
   retrospective, incompletely settled, partly sampled data is descriptive, not a
   launch criterion. MLB SGPs require their own joint-outcome model.

Evidence: `cohort/forensic_top_losses.json`, `replay/pricing_context.jsonl.gz`,
`backtests/*/unconstrained_fills.csv`, and the native candle and market files
referenced by each pricing context. The first-half example uses
`data/raw/candles/KXNCAAF1H-26SEP05ECSUNCCU-NCCU.json.gz` and
`data/raw/candles/KXNCAAF1H-26SEP05TCETSU-ETSU.json.gz`; its same-time full-game
comparators are in `kalshi_parts/`.
