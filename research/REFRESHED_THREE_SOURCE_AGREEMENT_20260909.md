# Refreshed capture and conditional source agreement

The combined 90-second run completed with both exchange refresh mechanisms and
the delayed Pinnacle collector. All collection, drain, archive and review processes
exited successfully. It saved three Pinnacle raw snapshots, 18 Polymarket REST
batches, 1,770 successful book-verification events, 30 rejected checks and 43,003
RFQ decisions. No orders were submitted; mapped RFQs still encountered the
unresolved Pinnacle payoff pricing gate. No processing-backlog skips were recorded.

Of the 30 verification rejections, 24 were REST/WS ladder mismatches and six had
an intervening book update. None renewed freshness. The 24 mismatches need a
separate timing/depth investigation; successful quiet-book examples do not imply
universal REST/WS agreement.

At 83 Polymarket heartbeat checkpoints, mean simultaneous eligible Kalshi and
Polymarket coverage was 67.24 keys under native age and 223.78 under the verified
Polymarket candidate. Both comparisons include the same Kalshi snapshot refreshes;
this is not a controlled estimate of Kalshi refresh benefit. A key counts only
when both exchange books have positive two-sided depth and meet their freshness
conditions using causally available events.

The diagnostic obtained 1,464 repeated moneyline comparisons across all 32 mapped
team contracts. Define an agreement occurrence as Pinnacle and Polymarket within
1 cent of each other, on the same side of Kalshi, and each at least 0.5 cents away
from Kalshi. There were 383 occurrences across eight team contracts and five games.
Within these occurrences, median absolute PM–Kalshi difference was 1.00 cent and
Pinnacle–Kalshi difference 0.90 cents.

This confirms the proposed disagreement pattern exists in the captured prices.
It does not establish predictive superiority: repeated observations are not
independent, complementary team contracts overlap, and Pinnacle's proportional
de-vig moneyline value is conditional on a decisive result while exchange ties
pay 0.5. No tie adjustment, calibrated weighting or profitability conclusion is
claimed. Exchange fee-expanded widths are retained for each comparison, but the
agreement rule uses point prices and is a diagnostic threshold, not a quote rule.

Artifacts: `runs/nfl_refreshed_three_source_capture_20260909` and
`runs/nfl_refreshed_source_agreement_20260909`. Reusable analysis:
`scripts/capture_source_agreement.py`. Original source/config hashes and causal
snapshot references are retained. The capture has stopped.

Next compare explicit three-source fair scenarios on the same stream, keeping
liquidity-unit and payoff assumptions visible. Measure RFQ-level source coverage
and candidate quotes, then collect markouts/outcomes on additional independent
slates before promoting the observed agreement heuristic.
