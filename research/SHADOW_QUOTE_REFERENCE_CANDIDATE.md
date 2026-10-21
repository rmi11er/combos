# Explicit shadow quote reference

The shadow engine now separates its charged probability reserve from the joint model's uncertainty output. The default remains `stressed_upper_v1`. An opt-in runtime field can select:

```json
"quote_reference": {
  "model": "independent_marginal_reserve_v1",
  "marginal_fraction": 0.25
}
```

This charges against `point + fraction * (independence_upper - point)`, then adds the existing required edge and fee-aware grid pricing. It matches the pricing-reference formula in the July marginal-reserve experiment. The fraction is an explicit uncalibrated assumption, not a confidence level. No production configuration is promoted by this change.

The candidate requires the current explicitly identified pairwise-moment model's independence benchmark; it refuses to reinterpret an arbitrary future joint model's upper bound. Original joint bounds, dependence diagnostics, leg observations, disagreement guards and risk multipliers remain intact. Decisions record the quote reference, its uncovered stress, and separate point/reference/stressed economics. Maximum loss and capital reservations remain based on actual quote price, quantity and fees, independent of the chosen probability reference.

Outstanding quotes use the same selected reference when checking whether a move requires cancellation. The policy manifest is included in the engine identity and the initial reference is retained in reservation context. Existing event stores cannot silently resume under changed policy identity; use a fresh experiment store for a new candidate. Outcome markouts remain point-fair movement diagnostics.

Validation: 27 focused quote-reference, runtime and deployment-cap tests passed. These cover preserved uncertainty, rejected invalid fractions/unsupported joint models, candidate quote admission, heartbeat survival below full stress, restart-preserved reservations, cancellation on a real fair move, and existing runtime/risk behavior. These synthetic checks establish policy mechanics, not profitable calibration, customer acceptance, or healthy real-source coverage. Historical fee and Pinnacle coverage limitations remain.
