# Causal research RFQ markouts

Added RFQScenarioConsumer.revalue() to price an existing RFQ against current market
state without consuming a duplicate event. Existing arrival pricing delegates to
this method. The new ResearchMarkouts scheduler labels10/30/60-second horizons;
replay_research_markouts.py schedules all694 captured sharp-peer candidates,
including research risk rejections, and verifies exact entry scenario parity first.
Later events are applied only after earlier due horizons are valued. Equal-time
events may be consumed before an inclusive final horizon flush. Sequence-prefix
watermarks protect against backdated publication receipt fields.

|Horizon|Observed|Unavailable|Capture-end censored|Mean adverse move, cents/contract|
|---|---:|---:|---:|---:|
|10s|576|85|33|+0.000909|
|30s|464|90|140|-0.000398|
|60s|309|64|321|-0.000188|

Positive adverse move means YES fair rose after the request, increasing a hypothetical
YES seller's liability. quote_minus_future_fair_cents subtracts the entry single-fill
fee per contract from ask minus later fair. Neither measure establishes a fill,
realized profit or predictive alpha. Later fair uses the same liquidity/freshness
model and can move as weights age even if venue prices are unchanged. Observed-only
averages have missingness selection and no independent-game confidence interval.

The capture is September9 03:17–03:19 CDT, a quiet overnight period. These very small
moves do not establish that the30s Pinnacle delay is harmless, nor that flow is toxic.
Missing exchange coverage and unavailable Pinnacle snapshot timing remain explicit
labels, never zero moves. More active/slate-diverse capture and paired external-price
markouts are needed. No labels are automatically sent to CreatorService or used to
ban creators; these retain creator IDs and decision sequence for later grouped review.

17 focused scheduler/quote/worker tests passed. Full replay verifies694 exact entry
scenarios and2,082 unique entry/horizon labels. A separate timing audit checks every
available event prefix is at/before the horizon, each Pinnacle source sequence is
available, and every censored label lies beyond the end of capture.1,349 marks are
observed. Venue normalization and fair probabilities are not independently rederived
by this timing audit. This is an offline reusable replay, not yet a scheduled durable
live markout consumer.

Implementation: src/combos/research_markout.py, scripts/replay_research_markouts.py.
Results/source hashes: runs/nfl_research_markouts_20260909.
Pre-refactor pricing source: runs/research_markout_20260909/rfq_scenario_consumer_before.py.
No account activity, creator thresholds, frozen August model or risk limits changed.
