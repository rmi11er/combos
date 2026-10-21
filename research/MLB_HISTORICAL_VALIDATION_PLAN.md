# MLB historical validation plan — September 7, 2026

Latest implementation and results: [MLB model research](MLB_MODEL_RESEARCH_20260907.md).
The retained MLB cohort now contains 318,536 prints, with complete-day paired
Kalshi/Polymarket model portfolios and all-universe charts. Pinnacle baseball
history was freshly rechecked and remains HTTP 403 despite zero quota cost.
July-onward multiweek collection remains a planned extension; the pilot notes
below describe earlier work and should not be used as current coverage counts.

Update: direct MLB `historical-odds` access was tested. `pinnacle+30` returned
403, `You do not have access to sport ID 13`; `pinnacle` returned a restricted-
bookmaker 403. These history calls consumed no quota. Evidence is in
`runs/oddspapi_baseball_direct_history_20260907/`. This supersedes the earlier
unverified-entitlement status below. The supplied temporary key file remains
available; baseball history access is the blocker, not a missing credential.

The next historical study should establish whether better single-leg estimates
improve pricing on a representative combo cohort. It cannot establish executable
RFQ profitability from public trade prints alone. Keep Wednesday's supervised
shadow collection running in parallel with historical research.

## What the CFB pilot established

The saved pilot contains 23 comparable YES-taker prints on September 5, involving
22 two-leg combos and one three-leg combo. That is an intersection of selected
fixtures, exact mappings, active prior price states and trade-side eligibility,
not a week of complete strategy opportunities. Twenty fixtures were initially
selected from existing exchange mappings; 103 exact three-venue leg mappings
survived. Seventy mapped combo definitions yielded 68 pregame prints before the
remaining exclusions. See [the pilot report](CFB_FAIR_PILOT_RESULTS.md).

The $10,000 capital and concentration limits did not cause the zero-entry result:
all 23 prints failed the configured stressed reservation-price test first. The
blend's small fixture-balanced Brier improvement has an interval containing no
improvement. Neither the point-edge total nor the unfiltered reference's positive
realized P&L establishes attainable market-making returns.

The existing weekly tape also has different acquisition designs: Saturday is a
census, while other days contain four sampled 15-second cells per hour. Those
sampling weights support volume estimation, with uncertainty; multiplying
sampled fills by 60 does not reproduce a chronological risk-constrained strategy.
Use complete selected days for portfolio backtests, and keep sampled opportunity
estimates separate. See [the volume methodology](CFB_WEEKDAY_VOLUME.md).

## Access and work that can begin now

The cached OddsPapi sports catalog identifies baseball as **sport 13**. The saved
active account response covers **sport 14 (American football)** with
`pinnacle+30`, no in-play/player-prop access, and no WebSocket access. This process
has no `ODDSPAPI_API_KEY`. The temporary key used for CFB acquisition was deleted.
These are observations about saved configuration and this process, not a fresh
account entitlement check; no secret values belong in research artifacts.

Football history on `pinnacle+30` was successfully acquired before the account's
subscription start; `pinnacle` returned 403. That does not demonstrate baseball
entitlement. OddsPapi documents historical odds since January 2026, fixture/book
queries, price/limit/activity timestamps, and a five-second history cooldown.
Its quota documentation says history does not consume the monthly request count;
entitlement and cooldown still apply. [History endpoint](https://oddspapi.io/en/docs/get-historical-odds),
[request accounting](https://oddspapi.io/en/docs/requests-and-quota).

We can now define the MLB cohort, inspect public exchange metadata and payoff
rules, prepare exact mappings and run an exchange-only baseline once data is
collected. A valid three-venue MLB test requires a securely supplied current key
and confirmation that baseball history is entitled. Start with one historical
MLB fixture and verify both sides, alternate lines, inactive updates and earliest
available timestamps before a batch download. Do not purchase or upgrade a plan
as part of this research task. Provider timestamps, delayed archive semantics,
limit currency and limit units remain explicit validation items.

Evidence: `runs/oddspapi_smoke_20260907/02_sports.json.gz`,
`runs/oddspapi_smoke_20260907_retry/03_account.json.gz`, and
`runs/cfb_fair_pilot_20260907/acquisition.json`.

## Cohort and acquisition design

Use July 1 through September 6, 2026, inclusive in America/Chicago, with a saved
UTC conversion. Initially collect regular-season, no-player-prop MLB combos and
classify every leg, leg count, side, fixture and pregame/in-play status. The
production-like evaluation is pregame, 2–4 legs, distinct fixtures, full-game
moneyline and exact half-point run-line/total markets. Report same-game combos
and broader exploratory cohorts separately; the example MLB SGP chart is a
different joint-probability problem from distinct-game parlays.

1. Enumerate public combo trades and recover definitions for the target dates
   **before selecting underlying fixture histories**. Retain all quantities,
   timestamps and both trade sides; explain each pricing-direction exclusion.
   Deduplicate by exchange trade ID and reject conflicting duplicate payloads.
2. If complete July–September acquisition is too large, select complete days
   across every week using a fixed, outcome-blind rule. Fetch every print on each
   selected day and all legs of its eligible combos. Report sampled dates and
   avoid pretending the gaps are a continuously traded portfolio.
3. Form the union of required underlying legs; fetch their metadata, bid/ask
   histories, Polymarket token histories and exact Pinnacle fixtures/markets.
   Include history before the first decision, so a missing start-of-window state
   is not confused with a genuinely unavailable market.
4. Save a coverage funnel by date and leg count: all prints; recovered definition;
   eligible scope; exact payoff match; each venue present; prior state; active
   state; freshness scenario; quote guard; edge; risk; hypothetical fill;
   settlement known. Include YES premium and payout notional at every stage.
5. Compare all fair models on the same complete-data intersection. Also report
   incremental coverage by source combination. Distinguish a better estimator
   from a source combination that simply prices a different set of trades.
6. Store immutable raw responses and manifests with query ranges, status,
   pagination completeness, retrieval time, checksums, source availability time,
   rule versions, mappings and configuration hashes. Key derived cohort caches
   by the selected-universe hash; the current pilot's unconditional reuse of
   `combo_cohort.json.gz` must not silently carry over into a new universe.

Kalshi partitions old markets, trades and candles into historical endpoints.
Read `/historical/cutoff`, route each query by its relevant cutoff and merge
without duplication across the boundary; a successful live-endpoint response
alone does not prove coverage. Its candle schema provides prices/bid/ask and
volume, not the historical top-of-book sizes required by our forward model.
[Historical data routing](https://docs.kalshi.com/getting_started/historical_data),
[historical candles](https://docs.kalshi.com/api-reference/historical/get-historical-market-candlesticks).

## Exact MLB payoff mapping

For every native market, archive the actual contract text and model its payoff
under ordinary outcomes and exceptional settlement. An identical team and line
is insufficient. Canonical identity must contain fixture ID, original schedule,
actual start, home/away role, doubleheader game number, period, market family,
selection, strike, equality convention and rule version. Do not join only on
team names and calendar date.

Current Pinnacle rules say ordinary baseball bets have action regardless of
starting pitcher. They distinguish moneyline minimum innings from full-game
run-line/total completion, have suspension/continuation exceptions, and require
G1/G2 doubleheader identification. First-half markets refer to five innings.
Verify those rules against each archived offering instead of importing an
assumed listed-pitcher convention. [Pinnacle baseball rules](https://www.pinnacle.com/en/future/betting-rules/).

The mapping review must resolve:

- Rain-shortened, postponed, suspended and resumed games, including each venue's
  deadlines and whether a market voids, pays an exchange-specific value or
  follows an official result. Pinnacle's source probability can be conditional
  on action when an exchange contract's payoff is unconditional.
- F5/inning ties and integer totals/run lines. A push refund is not automatically
  an exchange NO payoff or a 50/50 settlement. Begin with reviewed binary
  full-game/half-point lines; add richer settlement states deliberately.
- Doubleheaders and pitcher changes as identity/news events. Preserve schedule
  revisions known at the decision time; do not use a later schedule to permit a
  quote that was not known to be pregame when sent.
- Extra innings, venue/home-side changes, All-Star/exhibition rules and abnormal
  scheduled game length. Exclude All-Star/exhibition games from the first
  regular-season study.
- Leg-side complements and maker trade direction. Share risk buckets only when
  statewise payoffs are equivalent; similar team exposure can also consume a
  broader fixture bucket without claiming perfect hedge credit.
- Combo leg cancellation and settlement aggregation. Do not assume that a
  combo's exceptional payout is the product of nominal binary leg outcomes.

## Timing, liquidity and the delayed sharp source

Reconstruct as-of states with separate timestamps for source price change,
provider publication, our receipt and decision. A quiet last price is not a
dead connection; an old successful poll does not prove an old price remains
active. Carry forward only within an explicit history convention, obey inactive
updates, and never replace a latest inactive state with an earlier active quote.

The 30-second delayed subscription is useful as a sharp prior, but cannot certify
the current price after news. Test the existing fixed blend against a delayed
Pinnacle anchor updated by causally observed exchange moves over the same lag.
Estimate lag correction and uncertainty on training data, with safeguards for
thin-book noise and correlated exchange errors. Evaluate stationary periods
separately from disagreement, volatility, suspension and close-to-start periods.
Do not treat a Polymarket or Pinnacle reputation prior as empirical proof.

Historical depth/spread imputation must remain labeled and run as sensitivity
scenarios. Preserve actual historical observations when available. Never use
today's book sizes for historical decisions or enable imputation in forward/live
pricing. The existing zero/30/60-second additional archive-delay scenarios do
not settle whether the provider has already applied the subscription lag.

## Validation and performance reporting

Use July for model fitting and reserve calibration, August for forward validation,
and September 1–6 as a final locked comparison after choices are frozen. If
September outcomes have already influenced model selection, disclose that and
reserve genuinely future shadow observations as the untouched test. Use weekly
rolling train/next-week validation inside development to avoid one lucky split.
Keep the model/configuration trial register and all failed variants.

Score single-leg probability calibration, paired Brier/log-loss differences,
joint outcome calibration by leg count, source disagreement and time-to-start.
Closing-price agreement is source-dependent diagnostic evidence, not a substitute
for outcome calibration or attainable fills. Only use later prices as labels,
never as input to the earlier decision.

For uncertainty, aggregate repeated lines within a fixture for single-leg scores.
Use day/slate or multi-day block resampling for portfolio P&L and report paired
model differences. Combos sharing fixtures are dependent: independently
resampling each public print badly understates uncertainty. Bootstrap complete
blocks with their joint trades, outcomes and portfolio replay where feasible;
report sensitivity to block length and avoid claiming the number of prints is
the effective sample size. Doubleheaders and common weather/news are further
reasons to retain date-level grouping.

For each pricing model keep entry rules identical between the $10,000 constrained
portfolio and the uncapped exposure diagnostic. The constrained run enforces
canonical underlying, combo and fixture limits and recycles cash only at actual
settlement. Kalshi distinguishes determination from paid settlement, so game end
or a known winning result is not an acceptable cash-release timestamp.
[Market lifecycle](https://docs.kalshi.com/getting_started/market_lifecycle).

The equity legend should state daily return/P&L variance units, sample length,
Sharpe convention and annualization. Include zero-activity calendar days in a
complete observation window. A zero-variance or very short series should show
Sharpe unavailable, with its reason. Settlement-only equity misses open-position
valuation risk; label it and report committed capital, open exposure and eventual
settlement runoff. Add defensible mark-to-market curves when historical marks
exist. An uncapped portfolio normalized to $10,000 is an exposure diagnostic,
not a return achievable with $10,000: report peak financing need separately.

Keep customer YES premium, payout face notional, maker cash spent, fees,
expected point edge, reservation-price edge, settled P&L and fill counts
separate. Payout notional is face value, not how much customers won.

Public prints permit a counterfactual: buying NO at an observed YES-taker print
if our reservation price would have allowed it. They do not reveal whether our
RFQ response would win, adverse selection conditional on acceptance, quote
lifetime, queue priority or creator history. Even a profitable uncapped chart
cannot estimate the true fill rate. Forward RFQ logs must retain seen requests,
decision features, quoted price/size, response latency, acceptance/confirmation,
cancellation and subsequent market moves to calibrate those mechanisms.

## If the plots are weak

Diagnose in order: data coverage and payoff correctness; marginal calibration;
fee/spread/delay reserve decomposition; joint uncertainty; execution selection;
then concentration and capital efficiency. A zero-entry curve is different from
a curve that trades and loses. Do not reduce every reserve until entries appear.
Replace overlapping worst-case guards with separately measured error/markout
reserves only when development data supports the change, and re-evaluate on the
locked period. For same-game baseball, a coherent joint score/inning model is a
separate research track; a cross-game rho sensitivity does not validate SGPs.

The decisive next output is a coverage-complete MLB cohort with paired model
scores and auditable settlement ledgers, alongside Wednesday's real RFQ decision
logs. Until those exist, weak CFB curves are grounds to investigate the pipeline
and reservation rule, not enough evidence either to abandon the idea or fund it.
