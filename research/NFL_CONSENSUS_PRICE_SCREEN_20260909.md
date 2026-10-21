# NFL Pinnacle/Polymarket agreement coverage

Added an optional `--consensus-screen` to the attribution replay. This measures
price geometry in every baseline priced RFQ, including entries without future
observed marks. It uses the existing frozen hypothesis thresholds: anchor
points within 0.75 cents, Kalshi on the same side of both, and Kalshi 0.5–3
cents from a relative-liquidity-score anchor capped at 75% per anchor source.

This is not activation of `ConsensusAnchor`: it uses the baseline's recorded
relative liquidity scores, not that module's independently validated source
inputs/excess-age formulation. Payoff equivalence, fee evidence and Pinnacle
stake currency remain unresolved production gates. No candidate fair, quote,
selection or risk setting was changed.

On the three-minute NFL capture, all 65,995 baseline records and 1,348 observed
marks reproduce exactly. Across 687 priced RFQs there are 1,879 leg occurrences
and 51 distinct market/side pairs. The screen passes on 542 leg occurrences,
13 market/side pairs and 10 distinct markets. 515 RFQs (75.0%) contain at least
one passing leg.

| Legs | Priced RFQs | At least one passing leg |
|---|---:|---:|
| 2 | 322 | 233 |
| 3 | 225 | 156 |
| 4 | 140 | 126 |

Of passing leg occurrences, 433 have Kalshi below the anchor in the customer's
selected-outcome orientation and 109 have Kalshi above. A lean toward the
anchor would therefore raise the selected leg's fair more often than lower it
in this sample, holding other inputs fixed. For a seller that can mean a higher
required YES price and fewer qualifying historical prints, not automatically
more trading. Multiple changed legs can interact in the combo product.

This establishes opportunity to test the proposed signal, not sharpness or
profitability. Repeated RFQs, complementary sides, shared games and unchanged
prices sharply limit independence. The quiet capture has no venue-midpoint
movement in its observed markouts; it cannot establish which source was right.
Evaluate subsequent venue prices and eventual outcomes across independent
slates before promoting a conditional lean. Missing three-source historical
Pinnacle remains a gap; the frozen August exchange-only study does not test it.

Artifacts: `runs/nfl_consensus_price_screen_20260909`.
Eight focused screen/attribution tests pass, including YES/NO symmetry.

## Fixed 25% lean sensitivity

The workflow now also calculates an independent-leg combo point after moving
each passing leg 25% from its existing blended point toward the recorded-score
anchor. Nonpassing legs retain their original point. This is a fixed-fraction
sensitivity, not the gated candidate's agreement/freshness-scaled lean and not
a bound on all possible per-leg adjustments (different leg effects can cancel).

Across all 687 priced RFQs, the signed mean change is +0.02461 cents per combo
contract, median absolute change 0.03343 cents, 99th absolute percentile 0.09740
cents, and signed range [-0.08280,+0.10845] cents. No absolute change exceeds
the existing 0.3-cent hurdle. Median absolute moves by leg count are 0.05875
cents (two), 0.03148 cents (three) and 0.02011 cents (four).

Frequent signal occurrence therefore does not imply a large price adjustment
from an already blended fair. These changes could still affect rounded quotes
or marginal selections; quote-grid/fee/risk/acceptance effects were not simulated
here. No claim of additional fills, P&L or accuracy follows. Nine focused tests
pass after adding inactive-leg and product-economics coverage.

Artifacts: `runs/nfl_consensus_lean_sensitivity_20260909`, including the complete
per-decision screen and `sensitivity_summary.json`. All original baseline and
observed markout outputs again reproduce exactly.
