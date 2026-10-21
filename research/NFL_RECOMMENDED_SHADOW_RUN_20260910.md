# NFL recommended-limit shadow run

Run directory: `runs/nfl_verified_candidate_shadow_recommended_capture_20260910b`.

This 90-second run used the explicit research configuration in
`runs/nfl_verified_candidate_shadow_recommended_20260910/runtime.json`:
$10,000 capital, $500 per underlying/combo/fixture, and $5,000 maximum
committed capital. It ran the Kalshi and Polymarket collectors, the dynamic
Pinnacle `pinnacle+30` selector-rebinding collector, creator monitoring, and
the shadow decision engine. No order adapter was enabled.

The run processed 58,250 RFQs, including 2,663 2–4-leg non-player NFL RFQs,
286 with every leg mapped, and 77 mapped cross-fixture RFQs. Decision coverage
was complete. It observed all 235 candidate mappings on each of Kalshi,
Polymarket, and Pinnacle. Processing lag was 0.121 seconds median, 0.200
seconds p99, and 0.249 seconds maximum. The database consumed 196.9 MB and
all consumers drained cleanly.

No complete quote was emitted in this window. The rejection reasons were 35
Polymarket freshness failures, 38 Kalshi freshness failures, and 4 missing
Pinnacle observations among otherwise eligible decisions; the remaining RFQs
were outside scope or lacked reviewed mappings. This is an operational
coverage result, not evidence that the fair model has no edge. The earlier
125-second run produced five complete quotes, so quote coverage is sensitive
to arrival timing and should be measured over full pregame windows.

OddsPapi historical probing was also performed for one reviewed playoff
fixture. The `historical-odds` endpoint returned HTTP 404 with the current
subscription, despite successful account and fixture discovery. Therefore a
matched NFL Pinnacle historical backtest cannot yet be claimed. The archived
evidence is in `runs/nfl_oddspapi_history_probe_20260910/summary.json`.

The provider's numeric limit fields still have no documented currency or unit
in the returned payload. The USD stake interpretation remains a shadow-only
assumption. Live trading stays gated until that meaning, payoff semantics,
account precision, and quote submission/fill reconciliation are verified.
