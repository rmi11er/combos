# Conditional liquidity-weighted fair

The fair is not an equal-weight average. Each venue receives a score proportional
to two-sided payout capacity raised to 0.5, divided by fee-expanded spread (with
a floor), discounted for age and adjusted by configured venue multipliers.
Weights are capped. Capacity is a liquidity proxy, not a guarantee of execution.

`config/weighting.json` enables `consensus_lean_enabled`. After normal source
validation, if PM and Pinnacle point fairs differ by at most 0.75 cents and Kalshi
is at least 0.5 cents outside both on the same side, the model:

- Does not apply the generic moderate-disagreement penalty to Pinnacle.
- Transfers up to 25% of Kalshi's resulting base weight to PM/Pinnacle in
  proportion to their liquidity scores, subject to their remaining weight caps.
- Keeps all freshness, payoff, hard-disagreement and risk guards intact.

No three-source lean is inferred from two available sources. No caps are relaxed;
the transfer can be smaller or zero when external venues have no headroom.
Agreement is a price signal, not proof that the sources are independent or right.
Delayed or imputed source data still limits the interpretation of liquidity.
The thresholds are policy hypotheses, not statistically validated parameters.

Each leg records `consensus_lean` with source point fairs, detection, base/final
weights and the point adjustment in cents. This changes fair value, not an extra
reserve or fee. Quote-reference selection remains a separate runtime setting;
this weighting change does not by itself switch stressed-upper quoting to
point-fair quoting. Correlation-tail filtering remains separate and unchanged.

Frozen manifests without the new flag retain the previous behavior. Existing
shadow performance artifacts have NOT been repriced with this new policy and
must not be represented as its results. No run was restarted by this change.
