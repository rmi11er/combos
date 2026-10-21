# Liquidity- and disagreement-dependent edge charge

Added `combos.dynamic_edge` as a pure, deterministic shadow-policy function.
It starts at 0.3¢ per combo contract and adds separate, logged components for:

- venue disagreement above 2¢;
- minimum observed two-sided payout depth below $1,000;
- delayed-source uncertainty padding above the normal 0.5¢.

The total is capped at 1.0¢. `ResearchQuoteConsumer` uses it only when an
explicit `dynamic_edge` policy block is supplied; existing fixed-policy replays
remain byte-for-byte unchanged. Every decision records the edge components and
the source liquidity evidence. This supports the requested hyperparameter and
fair-model experiments without silently changing the live or frozen pipelines.

The candidate policy is
`config/dynamic_edge_shadow_policy_20260909.json`: $10,000 hypothetical
capital, $500 contract/combo/fixture limits, and no automatic promotion. The
charge is a risk/uncertainty markup, not a claim that thin books or disagreement
predict adverse settlement. Sweep its slopes and cap on independent NFL slates,
then evaluate accepted and filled RFQs separately.

Fourteen focused tests pass across dynamic edge, creator sniffer, attribution
and consensus screening. No quote or order was submitted.
