# NFL forward-test parameter decision

Until independent acceptance and markout data are available, use the
following as a reversible shadow/forward-test configuration:

| Parameter | Value | Reason |
|---|---:|---|
| Capital base | $10,000 | User-specified strategy capital |
| Maximum committed capital | $5,000 | Preserve half the capital for model/feed uncertainty |
| Per underlying contract | $500 | Avoid one leg dominating the book |
| Per combo | $500 | Prevent a large single RFQ from consuming capacity |
| Per fixture | $500 | Limit correlated exposure within one game |
| Minimum net edge | 0.3¢/share | Existing sweep's provisional middle point |
| Legs | 2–4 | Requested live scope |
| Timing | Pregame only | Pinnacle feed is 30 seconds delayed |
| Player props | Disabled | No subscribed Pinnacle player-prop feed |
| Disagreement multiplier | 0.5 | Halve risk when Kalshi diverges materially from the sharp pair |
| Hard disagreement halt | 5¢ | Avoid treating stale/news-driven divergence as value |
| Blacklist action | Log/watch/review | Do not auto-sanction on a tiny sample |

These are operational starting points, not claims of profitability. The edge
charge should be applied after fee-expanded fair value and should vary with
liquidity, freshness, leg count, and disagreement. The first sweep should
compare 0.1¢, 0.3¢, 0.5¢, 1.0¢, and a spread/liquidity-scaled charge while
holding the risk limits fixed. Promotion requires positive markout-adjusted
edge across a held-out pregame window and clean capital reconciliation.

The recommended-limit shadow run is archived at
`runs/nfl_verified_candidate_shadow_recommended_capture_20260910b`; the
runtime itself correctly records these values. No live order submission is
enabled yet because the execution adapter and provider limit-unit semantics
remain unverified.
