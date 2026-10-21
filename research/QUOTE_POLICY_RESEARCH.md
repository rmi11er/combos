# Quote policy: research implementation and shadow instrumentation

`src/combos/quote_policy.py` implements a composable research quote policy. It separates the probability forecast, pricing reserves, actual single-fill maker cash fees, minimum profit, and commercial markup. It does not submit orders, alter the current pricing configuration, or replace the shadow engine's selected quote.

The implementation is research-ready. A competitive acceptance model is **not** included, calibrated or enabled. Missing acceptance inputs never become an assumed 50% probability.

## Economic formulation and units

All probabilities and prices are dollars per $1 payout contract. For quantity `q`, fair YES probability `f`, seller YES ask `a`, maker fee `F(q, 1-a)`, reserve amounts per contract `r_j`, and required minimum profit per contract `π`, the quote floor is:

```
smallest valid a such that
q × (a − f) − F(q, 1 − a) − q × sum(r_j) >= q × π
```

The submitted instrument is a **NO bid** at `1 − a`. The policy enumerates the valid native NO price grid and mirrors it into seller YES prices. It does not assume that an asymmetric grid is unchanged by complementation. A complementary YES ask is an economic representation; the returned native quote is `yes_bid = 0` and `no_bid = 1 − a`.

Four named reserve components must be supplied, including explicitly identified zero assumptions when appropriate:

- `uncertainty`: uncertainty around the fair forecast.
- `dependence`: incremental joint-probability protection beyond the marginal uncertainty calculation.
- `adverse_selection`: protection for customer-conditioned outcome risk.
- `inventory`: additional compensation for consuming exposure capacity.

Additional named components are allowed. Duplicate names and negative reserves are rejected. This version supports nonnegative inventory protection; it does not implement signed hedge credits or an inventory optimizer. A reserve's `calibrated` flag is logged separately from its amount. An uncalibrated guard must not be described as a statistically estimated confidence bound.

Commercial markup is supplied separately as additional YES ask above the calculated floor, rounded upward to the next valid mirrored grid price. The ledger records both the requested markup and the actual achieved markup. Commercial markup is not hidden inside the fair forecast or called a fee.

Actual maker cash fees are computed with the existing `fees.kalshi_fill_fee` implementation, including its cash precision and rounding. The caller must supply the applicable fee rate, account precision, provenance, and information-availability time; expired fee terms are rejected. This policy explicitly assumes a **new order filled once for its full quantity with zero previous rounding accumulator**. Arbitrary partial-fill sequences require subsequent per-order fee reconciliation and are not represented as already known exact fees. Quantity must be on the 0.01-contract grid.

A small quantity can materially change the minimum valid quote through cash alignment. A test with 0.01 contracts and zero nominal rate demonstrates that the smooth theoretical floor can leave zero actual cash profit; the exact cash-aware floor advances to the first grid price meeting the minimum profit.

## Components and returned ledger

The public interface consists of:

- `FairSignal`: probability, availability timestamp, source reference.
- `Reserve`: name, per-contract amount, availability timestamp, source reference, calibration flag.
- `MakerFeeTerms`: rate, account precision, provenance, availability, optional expiry, explicit fill assumption.
- `QuoteRequest`: fixed quantity, decision ID/time, fair signal, reserve tuple, fee terms, native price ranges, minimum profit and policy provenance.
- `QuotePolicy.evaluate(request, commercial_markups, acceptance_model=None)`.

The result includes a floor and a candidate ledger containing seller YES ask, native NO bid, customer YES premium, maker NO principal, maximum loss, gross point margin, each reserve in dollars, each maker fee component, minimum required profit, residual margin, commercial markup, acceptance-model context when available, and any optimizer selection. It declares `orders_enabled = false`.

Candidate `eligible` means pricing and information eligibility only. Capital, canonical underlying exposure, fixture, creator, pregame, quote-lifetime and cancellation controls remain external. A price candidate is not an authorization to reserve risk or send an order.

## Acceptance-aware selection requires more than a fill probability

The optional `AcceptanceModel` protocol provides a versioned manifest and a candidate-specific `AcceptanceEstimate`. To select a quote by expected profit, an estimate must include:

- Calibrated probability of **full requested quantity RFQ acceptance**.
- A calibrated conditional YES probability **given acceptance of that candidate**.
- Candidate identity, model version, calibration references and scope reference.
- Forecast availability and training-data availability timestamps no later than the decision, with training data also available no later than the forecast itself. The calibrated attestation must be the boolean `True`, not a truthy string or integer.

A public print crossing a proposed floor is not this acceptance label. Partial fills, a different candidate's estimate, future-trained forecasts, missing conditional outcome forecasts, uncalibrated estimates and missing provenance are rejected for optimization.

For eligible candidates the objective is:

```
P(full acceptance) × [q × (YES ask − P(YES settles | acceptance)) − maker fee]
```

The conditional outcome forecast is necessary because accepted customer flow can be more informed than the overall market. Optimizing an acceptance probability against an unconditional fair can systematically reward quotes that attract toxic flow.

Reserve guards are not subtracted again as if they were realized expenses. Their role is candidate eligibility; actual conditional expected P&L uses the conditional outcome forecast and maker fee. The no-quote alternative has zero incremental profit. If every usable candidate has nonpositive expected profit, no quote is selected.

The calibration fields are provenance requirements and caller attestations, not an automatic certification of a fitted model. An actual implementation needs a reviewed calibration artifact, feature/label definitions, appropriate out-of-sample validation, and verification that its scope covers the current RFQ. No such fitted model is supplied here.

The request contains no eventual public execution price, settlement result or future markout. Request-time provenance and timestamps are validated before eligibility is computed. The policy also checks acceptance-model metadata for future information. These checks complement, rather than replace, auditing the model implementation and its training dataset.

## Optional shadow integration

The broader [shadow policy study](SHADOW_POLICY_STUDY.md) now provides runtime-config wiring, separate MLB/NFL profiles, source-disagreement logging and alternative point-model candidates even when the baseline stressed floor has no feasible price. The original injected sidecar described below remains supported and unchanged.

`ShadowEngine(..., quote_policy_audit=None)` retains the previous behavior by default. Injecting a `ShadowQuoteAudit` records a sidecar candidate ledger in the existing compressed `decision` event, and adds the sidecar configuration and component hash to the engine's version identity.

The sidecar decomposes the current pricing result as follows:

- Uncertainty = existing joint upper − joint point.
- Dependence = existing stressed upper − joint upper.
- Existing extra strategy edge remains a separate `strategy_signal` component.
- Adverse selection and inventory default to explicitly labeled, **unestimated zero assumptions** for this decomposition.

This is an audit of current arithmetic, not evidence that those reserves are calibrated. The sidecar is opt-in and requires explicit fee-metadata availability, account precision and policy provenance. Example wiring, with variables supplied from verified deployment metadata:

```python
from combos.quote_policy import ShadowQuoteAudit

audit = ShadowQuoteAudit(
    fee_terms_available_at=verified_fee_terms_available_at,
    balance_precision=verified_account_balance_precision,
    policy_available_at=policy_configuration_available_at,
    policy_reference=policy_configuration_reference,
    commercial_markups=(0.0, 0.005, 0.01),
)
engine = ShadowEngine(store, config, quote_policy_audit=audit)
```

No deployment configuration was changed to enable this example. The sidecar does not alter the existing selected quote, quantity, reservation, risk checks, cancellation or revalidation. Its errors are logged as unavailable audit results while the original shadow decision continues.

Only RFQs with an explicit contract count are audited. Target-cost RFQs require quantity to be recomputed for each candidate price; applying a fixed quantity across those candidates would misstate their requested spend. Such RFQs currently receive an explicit `target_cost_requires_candidate_dependent_quantity` sidecar status. Existing shadow handling of those RFQs remains unchanged.

## What the existing logs can support

The existing decision event already stores the RFQ and creator IDs, selected legs, price-source context, source/receive/decision timestamps, chosen quote, size model, risk result, creator policy and configuration version. The sidecar adds the candidate floors, complete component ledger and acceptance-model provenance when supplied. Existing markout events record hypothetical quote markouts with an explicit warning that their benchmark is the same pricing model, not an independent measure of value.

These logs can support:

1. Reproducing quote floors and explaining which reserve or fee moved a price.
2. Measuring snapshot health, processing latency, information gaps, rejection reasons and hypothetical quote markouts.
3. Checking whether observed public prints would clear a proposed floor at matching historical information times, labeled a **capacity/price-crossing test**, not a quote-win model.

A shadow quote was not presented to the customer. It cannot be labeled accepted or rejected by that customer. An RFQ deletion is not proof of acceptance of our quote. A simulation fill is also not an observed acceptance label.

A future real acceptance dataset must join our submitted quote ID to the parent RFQ, quantity, candidate/price, send/acknowledgment times, acceptance/execution events, partial fills, cancellation/expiry and observed response window. It must retain quotes that did not execute and distinguish an observed non-acceptance from censoring or collection failure. Decisions skipped for risk, scope or missing data are not negative acceptance examples. The conditional outcome model additionally needs matured outcome labels whose availability precedes each training cutoff. Existing logs provide much of the decision context, but these real exposure-to-customer labels are currently missing.

## Validation and remaining work

The focused policy, runtime and fee suites pass **48 tests**. Added tests cover exact fractional-quantity cash floors, asymmetric native NO grids, component/markup separation, no default acceptance probability, future-data and missing-calibration rejection, candidate/label mismatches, conditional outcome requirements, no-quote dominance, preservation of selected shadow quotes and risk reservations, and isolation of sidecar failures.

Before enabling a competitive policy, the remaining work is empirical: calibrate the delayed-anchor fair and separate reserve terms; obtain valid customer acceptance and conditional outcome labels; include candidate-dependent target-cost sizing; validate fill-level fee reconciliation; enforce risk at the selected candidate; and measure sidecar/optimizer latency under actual RFQ load. This implementation provides an inspectable boundary for those components without treating them as already solved.
