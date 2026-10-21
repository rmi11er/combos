# NFL shadow research backlog

This backlog extends the current RFQ combo-quoter configuration. The first
priority is to verify that charged edge survives realistic execution; later
work can improve fair value, dependence modeling, and bankroll allocation.

## First cycle: use the shadow stream

September 10 addition: prioritize volume-conditioned markouts and a research-only
0.10c inventory-relief hurdle experiment. See
`research/VOLUME_INVENTORY_EXPERIMENT_20260910.md` for causal versus descriptive
day-volume buckets, matched risk-accounting controls, and the strict definition
of a reducing trade. Round-spend remains a retained feature; discount testing is
tabled. These are research priorities, not authorization to change live pricing.

1. **Charged edge versus realized markout.** For every hypothetical fill,
   compare quoted edge, fully charged edge, and 1-second, 5-second,
   30-second, 5-minute, and settlement markouts. Cut results by leg count,
   price, time-to-start, venue, side, and blacklist state.
2. **Edge decay and quote half-life.** Measure the probability that an
   opportunity remains executable after 1, 5, 15, and 30 seconds, and edge
   lost per unit of delay.
3. **Stale-reference and lead-lag signals.** Identify which of Kalshi,
   Polymarket, Pinnacle, and the composite fair value moves first, and test
   whether a source move predicts subsequent Kalshi repricing.
4. **Order-book imbalance and microprice.** Test bid/ask imbalance, spread,
   depth, recent trade direction, queue depletion, and price-change intensity
   against short-horizon markouts.
5. **Fill-probability model.** Estimate fills as a function of distance from
   touch, displayed depth, quote age, event phase, leg count, trade intensity,
   and market direction.
6. **Blacklist counterfactual.** For every rejected opportunity, retain its
   hypothetical edge, markout, maximum adverse excursion, correlation regime,
   and whether blacklisting avoided a loss or discarded a winner.
7. **Correlation-charge attribution.** Decompose the quote into independent
   fair value, correlation charge, uncertainty charge, adverse-selection
   charge, and fees; evaluate outcomes by charge size.

## Medium-term pricing research

8. **Dynamic dependence.** Estimate dependence conditional on same-game versus
   cross-game, team/division, weather, injury/news state, game phase, and time
   to kickoff. Keep the current 0.05 value as a conservative floor until
   these estimates are stable.
9. **Tail dependence and copulas.** Compare Gaussian and t-copulas with
   empirical joint frequencies; focus on extreme game-script, injury, and
   weather states rather than average correlation alone.
10. **Parlay markup versus fair-value error.** Separate individual-leg error,
    dependence error, and market-level parlay markup.
11. **Calibration by price and time-to-expiry.** Build reliability curves for
    legs and combos by price bucket, expiry bucket, leg count, and
    favorite/longshot status.
12. **Probability shrinkage.** Compare raw probabilities with beta-binomial,
    isotonic, Platt-style, and hierarchical calibration; propagate posterior
    uncertainty into the quote charge.
13. **Dynamic source weighting.** Weight sources using both recent accuracy and
    publication latency, not accuracy alone.
14. **News and lineup shocks.** Measure cancellation speed, adverse selection,
    venue leadership, fair-value recovery time, and blacklist response around
    major information events.

## Longer-term portfolio and bankroll research

15. **Fractional Kelly under uncertainty.** Use Kelly as a benchmark, then
    shrink for probability, dependence, fill, fee, and settlement uncertainty.
16. **Risk contribution.** Allocate by marginal fixture, team, leg-overlap,
    correlation, and stress-loss contribution rather than ticket count.
17. **Common-shock stress tests.** Model stale feeds, exchange gaps, source
    outages, mapping errors, correlated favorite moves, and delayed settlement.
18. **Drawdown-aware bankroll simulation.** Bootstrap by slate or date while
    preserving within-slate correlation; report drawdown, recovery, ruin, and
    capital-growth probabilities under several Kelly fractions.
19. **Selection-bias audit.** Compare all opportunities, policy-eligible
    quotes, hypothetical fills, observed trades, and blacklisted cases.
20. **Constrained portfolio optimization.** Optimize across combos subject to
    fixture, team, market-family, leg-overlap, liquidity, committed-capital,
    and worst-case-loss limits.

## Suggested order of implementation

1. Charged edge versus markout
2. Fill probability and quote-age decay
3. Blacklist counterfactual
4. Correlation-charge attribution
5. Calibration by price and expiry
6. Source lead-lag
7. Fixture-level risk contribution
8. Fractional-Kelly bankroll simulation

The shadow run should preserve every decision as an order-like record:
timestamp, quote, available depth, source ages, charges, policy state, and
counterfactual outcome. This makes the same dataset useful for both pricing
and execution research.

## Canonical references

- Grant, Johnstone, and Kwon, “Optimal Betting Strategies for Simultaneous
  Games,” *Decision Analysis* (2008):
  https://pubsonline.informs.org/doi/10.1287/deca.1080.0106
- Avellaneda, Reed, and Stoikov, “Forecasting Prices from Level-I Quotes in
  the Presence of Hidden Liquidity” (2011):
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1691401
- Croxson and Reade, “Information and Efficiency: Goal Arrival in Soccer
  Betting,” *The Economic Journal* (2014):
  https://academic.oup.com/ej/article-pdf/124/575/62/25833204/ej0062.pdf
- Moshrefi, “Prices, Probabilities, and Parlays: Systematic Bias in Sports
  Prediction Markets” (2026), directly relevant Kalshi evidence:
  https://arxiv.org/abs/2607.14430
