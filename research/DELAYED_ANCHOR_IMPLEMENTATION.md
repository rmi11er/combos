# Delayed Pinnacle anchor with current exchange innovations

`src/combos/delayed_anchor.py` provides a replaceable, research-only point estimator. It does not change the deployed fair, reserve calculation, risk limits or quote selection. The fixed defaults are hypotheses, not fitted parameters.

For decision time `t` and Pinnacle's verified effective information time `s`, it computes:

```
logit(fair_t) = logit(Pinnacle_s)
             + beta * sum_v w_v * [logit(exchange_v,t) - logit(exchange_v,s)]
```

The two exchange weights sum to one. Thus the same news moving both exchanges is not added twice. The baseline is the exchange state already received by `s`; later-arriving records are excluded even when they claim an earlier source timestamp. This conservative receipt-time convention deliberately does not reconstruct an unavailable baseline retrospectively.

Weights use the smaller of current and baseline two-sided depths, raised to power 0.5, divided by the wider fee-expanded interval in cents (with a one-cent floor). Polymarket receives a 1.5 score multiplier, implementing the user's sharpness prior explicitly rather than presenting it as an established fact. Both intervals must already include their applicable taker-fee uncertainty. The component does not silently add a second fee expansion.

The default correction strength is 0.5. It rejects disagreement exceeding five cents between the two exchange probability innovations. The point result retains the anchor, both baselines and current states, weights, mapping version, clock provenance, clipping status, and policy parameters. These controls are configurable but have not been optimized on this CFB week.

## Information requirements

- Verified effective information timestamps and separate availability timestamps.
- Identical canonical payoff and mapping version across sources.
- Active two-sided exchange books with actual positive depth; historical imputation is forbidden.
- No stale or future state, no fallback through a suspension, and no post-cutoff decision.
- Current exchange information must be at or after the anchor information time; even a custom low-delay anchor cannot produce a negative-horizon innovation.
- A versioned, locally accumulated exchange history; `asof` lookup makes no network request.

Default exchange and baseline maximum ages are 15 seconds; anchor maximum age is 90 seconds; the pregame cutoff is 60 seconds. The intended anchor is the approximately 30-second delayed feed. The local history implementation is a research store; durable retention and its production adapter remain separate concerns.

Crucially, **last price change is not the same as effective feed information time**. An old unchanged price may still be valid, but neither a successful HTTP response nor subtracting 30 seconds from receipt proves that the upstream state is current. Existing Pinnacle normalization labels upstream freshness unverified. Those observations cannot become verified estimator inputs merely through a field rename.

## Boundary and validation

The estimator returns `uncertainty_bound: null`, `quote_authorized: false`, and `calibrated: false`. It supplies no automatic dependence or adverse-selection bound. The quote-policy module accepts these components separately; calibrating them requires appropriate data and independent evaluation.

Tests cover common-news normalization, correction strength, availability-time exclusion, suspension handling, clock and mapping failures, missing/imputed depth, exchange disagreement and pregame cutoff. The tests establish arithmetic and information controls, not predictive improvement. Historical data in this CFB study cannot resolve 30-second exchange innovations reliably; see the walk-forward report for actual markout coverage.

Before comparing this model forward, establish verified Pinnacle payoff mappings and information clocks, accumulate synchronized real exchange depth, and freeze its parameters alongside the current blend. Compare both forecasts on the same eligible RFQs, keeping decision reasons and subsequent independent marks. Quote-win probability and conditional outcomes require separate evidence; public prints are not our own acceptance labels.
