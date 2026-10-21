# CFB fair-value pilot — September 7, 2026

Execution update: the historical pilot and reusable reports are now complete.
See [results, assumptions and reproduction commands](CFB_FAIR_PILOT_RESULTS.md).
The original predeclared plan below is retained for comparison with execution.

Status: planned; no historical Pinnacle request or backtest result yet. The
process currently has no OddsPapi key; the prior temporary credential files
were deleted after their authorized probes. Existing code supports cached,
read-only `/v4/historical-odds` acquisition and raw history iteration.

## Access evidence

The active captured subscription covers football sport 14, bookmaker
`pinnacle+30`, no player props or in-play, with 100,000 monthly requests.
The live polling config routes only NFL tournament 31; this is a collector
selection, not evidence that football historical access is NFL-only. Discover
CFB tournament/fixture IDs separately without changing the NFL live universe.
The account response does not expose a historical entitlement flag.

OddsPapi's current [historical endpoint documentation](https://oddspapi.io/en/docs/get-historical-odds)
states availability since January 2026, one fixture per request, up to three
bookmaker filters and a 5-second cooldown. History includes price, maximum
stake, active state and createdAt; exchangeMeta can be present.
Their [quota documentation](https://oddspapi.io/en/docs/requests-and-quota)
says history is free of monthly request charges, while fixture/catalog discovery
is billable. This does not prove that either Pinnacle slug or earlier CFB data
will be returned to this key. A successful bounded probe must establish that.

Probe one completed CFB fixture from August 31–September 6 before bulk fetch.
Check the entitled `pinnacle+30` slug and the provider's archival slug semantics;
do not silently substitute one or add delay twice. Check history preceding the
September 7 subscription start, exact non-player lines, both sides, inactive
transitions, limits, record ordering/completeness and timestamp meaning. Never
filter away inactive observations. Cache finished histories by request and hash.

## Predeclared pilot

Use the existing August 31–September 6 Chicago-time CFB week. Select approximately
20 fixtures across days and market families without looking at price gaps or
outcomes. Begin with full-game half-point spreads/totals and moneylines, then
separately report exact period/team-total coverage. Score legs first; compare
2–4-leg distinct-fixture pregame combos on the same eligible timestamps.
Keep the deployed NFL scope unchanged; CFB needs its own reviewed mappings.

Compare on a common cohort:

1. Existing Kalshi-only midpoint/candle baseline, respecting interval availability.
2. Delayed, de-vigged Pinnacle alone as a diagnostic benchmark.
3. Existing guarded three-venue model, where contemporaneous depth exists.
4. Predeclared stronger-Pinnacle sensitivity, separately from production policy.

The production delayed Pinnacle contribution is currently capped at 20%; its
reputation for sharpness does not negate 30-second delay. Test a stronger prior
as a hypothesis instead of tuning on the reported evaluation sample. Freeze the
joint/correlation engine across fair-model comparisons so its changes cannot
masquerade as improvements to the leg fair.

Reconstruct what was available as of each decision, including source delay,
publication semantics and REST polling phase. If archived createdAt already
represents delayed dissemination, do not add the same 30 seconds again. Report
an additional polling/latency sensitivity. Do not equate quiet-price age with
verified snapshot age. Never use subsequent closing prices as model inputs.

## What counts as improvement

- Leg Brier/log scores and reliability summaries against actual outcomes;
  proper handling of fractional/void payouts, and small-sample uncertainty.
- Error to later pregame prices/closing fair, with an exchange benchmark as well
  as Pinnacle so the test does not reward Pinnacle merely for resembling itself.
- Subsequent adverse movement for quotes accepted by each hypothetical filter.
- Coverage, rejection reasons, fee-adjusted combo price gaps, YES consideration,
  payout notional and risk-constrained proposed economics. Keep correlation
  reserve separate. Retain $10k/$100 underlying/$100 combo/$250 fixture caps,
  no ticket or probability filter, and the whole-request-or-decline rule.

Many combos share the same underlying games. Report uncertainty clustered by
fixture/day; thousands of combos do not supply thousands of independent outcome
observations. A small first week is a sanity check, not validation of durable
profitability. Public traded prices do not identify RFQ quote acceptance or fills.

## Historical data gap

Our retained Polymarket histories contain prices, not historical top-of-book
sizes; Kalshi candle inputs also do not reconstruct every executable book.
If provider exchangeMeta supplies both sides and size with verified units, use
it. Otherwise run an explicitly labeled price-only sensitivity with predeclared
weights and spread assumptions, and report missing depth rather than inventing
historical liquidity or using today's sizes. It cannot validate the exact live
weighting/fee-expanded book model. Sustained three-venue shadow capture remains
the primary source for that validation and should proceed alongside this pilot.
