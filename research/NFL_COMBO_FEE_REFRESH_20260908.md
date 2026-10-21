# Current NFL combo fee metadata refresh

Six public API responses refreshed the two configured combo-series records: current series fee metadata, fee-change schedules and one active sampled market grid per series. The fee-bearing `KXMVECROSSCATEGORY-SHARD1` returns `quadratic_with_combo_maker_fees` at multiplier 1, preserving maker coefficient .035. `KXMVECROSSCATEGORY0-SHARD1` returns `quadratic` at multiplier 1, preserving zero maker fees. The official published fee schedule also describes the nonstandard combo maker multiplier; it excludes uncorrelated NFL combos from that generic combo line.

Both sampled markets retain `center_deci_edge_centi_cent`: .0001 price increments at the edges and .001 in the center. A sampled grid is not proof that every future RFQ market shares the grid; actual market metadata must still be checked before execution.

Only `combo_terms` metadata in `config/runtime_nfl_week1.json` changed. Existing fee rates, price ranges, risk limits, mappings and strategy parameters are unchanged. Verification times were refreshed, expiry is bounded by 24 hours and any future scheduled fee change, and source hashes/references were retained. The previous configuration is saved in the evidence directory. No trading process or order submission was started.

The handoff-loaded preflight no longer reports the API-key or combo-fee-expiry blockers. All 454 mappings remain excluded for unreviewed Pinnacle payoff parity, so there are still zero configuration-eligible fixtures. The mapping check reports its first exclusion; stale individual-leg fee metadata still needs refreshing after/alongside payoff review. Current public-series fee confirmation does not certify January/July historical fee applicability or account-specific execution rounding.

The official PDF was inspected through the web tool. A separate native PDF download returned HTTP429 and was not retried; the six public API responses were successful and retained.

[Official fee schedule](https://kalshi.com/docs/kalshi-fee-schedule.pdf) · [Refresh evidence](../runs/morning_research_20260908/nfl_combo_fee_review/verification.json) · [Updated preflight](../runs/morning_research_20260908/nfl_preflight_refreshed_combo_fees.json)
