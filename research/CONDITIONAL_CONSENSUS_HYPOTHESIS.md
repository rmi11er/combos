# Conditional Pinnacle/Polymarket agreement hypothesis

The user's proposed mechanism is now recorded as an explicit research hypothesis: individual-market makers' inventory and customer flow can shift Kalshi quotes, and trading costs can allow those quotes to remain displaced. When delayed Pinnacle and current Polymarket agree on the same payoff while Kalshi differs modestly, their agreement may be a better conditional probability anchor. The user's conversations with individual-market makers motivate testing this mechanism. Our data do not yet establish its prevalence, causal explanation or profitability.

This is conditional, not a universal ranking of venues. Measured depth, spread, effective market-specific fees, timing, market family and sport matter. In the current retained MLB metadata, some Polymarket markets have a 0.05 fee coefficient while Kalshi MLB uses 0.035 in the dated assumption; Kalshi is not always the venue with the higher fee. Full-game moneylines, run lines, totals, props and NFL need separate evaluation. Inventory skew is a latent explanation unless actual inventory or credible flow measurements are available.

## Implemented candidate

New leaf module [consensus_anchor.py](../src/combos/consensus_anchor.py), configuration [conditional_consensus_research.json](../config/conditional_consensus_research.json), and tests are separate from the running MLB batch and live engine. No existing pricing, execution, risk, replay or frozen configuration file was changed. The module is not wired into either pipeline and sends no orders. It returns a research candidate, source evidence, normalized weights, features and activation/nonactivation reasons. It never overrides a quote guard or claims executable edge.

The typed request requires three distinct observations with the same canonical payoff and explicit matching rule basis. The source's quoted YES/NO orientation is normalized, including interval endpoints and depth sides. Each mapping must have verified evidence available by the decision. Mismatched fixture, period, line, suspension/void rules, unresolved equivalence or future mapping evidence prevents activation. A common text label is not a substitute for a verified mapping adapter.

Live exchange inputs require actual two-sided top-of-book payout capacity, raw bid/ask and verified effective market-specific fee metadata. The module uses the existing finite-size `venue_cash_v2` fee implementation to reconstruct conservative taker-fee-expanded intervals and reconciles them against supplied intervals. Kalshi account balance precision is explicit. The existing Polymarket conservative rounding bound covers its unverified nearest-rounding tie convention; the module does not claim that convention was empirically validated. Pinnacle uses de-vigged paired odds and their bookmaker-margin band, with verified USD stake limits converted to payout capacity and no invented extra taker fee.

Price and depth snapshot information times must be causal and within the fixed age limits. Available timestamps must reflect the 30-second Pinnacle delay. Last price-change time is recorded separately and can be old without making a verified recent snapshot stale. Stamping an old price with a recent receipt time cannot satisfy these requirements. Live imputed capacity always blocks activation.

Historical mode additionally supports the user's explicitly acknowledged depth scenarios. A request must name its historical assumption reference; each imputed source must carry a basis, reference and `historical_assumption` capacity kind. Missing Polymarket depth must equal canonical Kalshi bid/ask payout capacity after side normalization. If Kalshi depth is also missing, an explicitly fixed two-sided capacity scenario can be supplied—for example the existing shared 1,000-payout-dollar assumption—with Polymarket equal to it. There is no automatic imputation and no Pinnacle limit imputation. These assumptions and their use are returned as source/features evidence, and the identical request in live mode is rejected. Effective fees and raw books still require their own evidence; an assumed depth does not certify an unverified historical fee schedule or a recorded price as an actual book midpoint.

Missing Pinnacle produces an explicit unavailable three-source hypothesis, never a two-exchange result relabeled as consensus. Current MLB historical Pinnacle entitlement and exact mapping remain unresolved, so this module has not been validated on a three-source MLB history. Its fee/book/clock requirements also mean the existing unverified-fee historical cohort cannot establish this mechanism by itself, even when its allowed depth scenario is recorded correctly. A separately labeled historical fee/book-assumption adapter would be required to relax those evidence gates; no observations are silently relabeled as verified here.

## Fixed research formulation

For each anchor venue, compute a spread/depth proxy:

`score_v = min(bid_depth, ask_depth)^0.5 / max(fee_expanded_width_cents, 1) × freshness_v`.

Freshness halves every 60 seconds of additional information/depth age. For Pinnacle the known 30-second delay is the age floor; only excess age receives an extra freshness penalty. The delay is still retained in the logged information ages and publication-lag features, and any source older than the maximum allowed age is rejected. The two anchor weights are normalized and capped at 75% each, implying a minimum 25% share for either anchor. These are transparent proxies, not measured executable liquidity or learned sharpness probabilities.

The fixed initial activation conditions are:

- Pinnacle and Polymarket point probabilities differ by less than 0.75 cents.
- Kalshi lies on the same side of both anchor points.
- Kalshi differs from their weighted anchor point by 0.5–3 cents.
- All source, pregame, mapping, depth, timing and fee evidence passes validation.

Agreement strength is `1 − anchor_point_gap / 0.75c`. Multiply it by the minimum source freshness factor, then by a maximum lean of 25%. This value is an **unfitted heuristic strength**, not a statistical confidence or fill probability. If the resulting lean is α and normalized baseline venue weights are b:

`effective_weight_v = (1 − α) × b_v + α × anchor_weight_v`,

where the anchor gives Kalshi zero weight. Effective weights sum to one, and the supplied baseline point must reconcile to the recorded baseline weights and canonical source points. The candidate point is the resulting weighted probability. Its lower/upper envelope contains both the original baseline and all three source intervals: point leaning cannot silently narrow uncertainty or imply that existing reserves should be removed.

Fee-expanded intervals may overlap when the signal activates. This is intentional: the user's mechanism specifically concerns a point displacement that trading costs might allow to persist. The module records whether Kalshi overlaps both anchor bands, the directional point discrepancy, interval gaps, raw and fee-expanded widths, actual fee contexts and source clocks. **An overlapping fee band does not establish mispricing or positive net execution edge.** Quote pricing would still need independently validated fees, markup, uncertainty, correlation, inventory, risk and acceptance modeling.

## Historical and forward validation plan

Keep the existing frozen MLB comparison as the baseline. Once genuine three-source history and matched dated fee/depth evidence are available, record signal features for every eligible decision without filtering by eventual outcomes. Compare baseline versus fixed conditional candidate on the same paired cohort, with inactive cases retained as unchanged predictions. Report activation coverage and reasons, not just profitable activated trades.

Evaluate individual-leg and joint calibration, paired Brier/log loss and probability residuals, grouped by sport, market family, disagreement direction/size, fee-band overlap, time to start and measured source depth. Use held-out time blocks and fixture-level clustering; avoid treating repeated prints of the same fixture as independent observations. Keep fixture overlap out of development/validation folds and retain all fixed parameter trials rather than choosing the best after observing outcomes.

Measure subsequent Kalshi/Polymarket movement and next Pinnacle refresh separately at fixed horizons, using their actual availability clocks. Does isolated Kalshi move toward the old anchor, or do the anchors subsequently follow Kalshi? Distinguish stale information, fee/friction bands and broader news episodes. Where possible add order-flow imbalance and reproducible inventory proxies before attributing a cause. Do not infer that the 30-second Pinnacle delay broadly causes adverse selection without these measurements.

Then evaluate seller P&L, unknown-outcome bounds and calibrated edge at common printed prices, with fixed entry policies and matched exposure. Public-print replay still cannot determine whether customers would accept the new quote; shadow logs and actual quote lifecycle evidence are a separate requirement. Any MLB/NFL parameter or risk-limit decision needs broader independent data. This experiment does not promote a model automatically.

## Validation

```sh
.venv/bin/python -m pytest tests/test_consensus_anchor.py -q
```

Thirty-two tests pass, covering exact fee-interval reconciliation, lower Kalshi than Polymarket fee coefficients, activation inside overlapping bands, normalized/bounded weight changes, conservative envelopes, missing Pinnacle, source disagreement, modest-gap limits, canonical/opposite-side equivalence, future/stale data and mappings, live real depth, explicit historical equal-Kalshi and shared-fixed-depth scenarios, delayed publication, old price-change times, effective fee schedules, published configuration parity and no execution authorization. All test evidence is synthetic and labeled as such. No historical performance claim follows from these tests.
