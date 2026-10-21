# Live execution persistence and protocol review

`src/combos/execution_journal.py` persists a deterministic operation key, reservation identity and exact request before a transport call. An atomic claim permits at most one dispatch per operation key, including across competing connections. Timeouts stay unknown; a crash after claim stays inflight. Neither is automatically retried after restart. All sent requests, including successful acknowledgments, remain in the reconciliation inventory. Error text is omitted because it can contain authentication headers.

Four tests pass for concurrent claims, timeout/restart behavior, crash between claim and response, successful acknowledgment and conflicting identities. This proves journal mechanics only. The transport interface must disable internal retries and validate successful responses. There is no authenticated transport, risk-ledger integration, global RFQ replacement policy, fill reconciliation or capital-release implementation in this module. A reservation ID is a link, not proof that funds have actually been reserved. Callers must use a deterministic key; different operation keys are not automatically recognized as the same RFQ action.

The existing shadow risk expiry mechanism must not be used to release exposure for a dispatched live request. Next integrate intent creation/claim with durable risk holds, then quote/accepted-size/order/fill reconciliation. Unknown create responses need authenticated quote lookup and pagination; an empty lookup alone does not prove a delayed submission never reached the exchange. No live orders were submitted during this work.

## Current official API findings

Kalshi describes a maker quote as full RFQ size, with either fixed fractional contracts or exchange-derived size for a target spend. Target-cost sizing normally includes taker fees. Acceptance is followed by maker confirmation; combos have a three-second confirmation window and one-second execution timer. Orders then enter the public book. Thus our partial-sizing historical experiments are hypothetical allocation sensitivities, not directly executable quote sizes. [RFQ guide](https://docs.kalshi.com/getting_started/rfqs)

The create endpoint takes both side bids and rest-remainder behavior, with optional post-only/subaccount settings. Its documented body has no client-generated idempotency key. A transport timeout must therefore be treated as uncertain rather than blindly retried. This retry policy is our implementation inference, not a claimed server guarantee. [Create quote](https://docs.kalshi.com/api-reference/communications/create-quote)

Quote discovery supports the authenticated-user filter, RFQ ID and pagination. Records expose quote/order identifiers, side-specific contract sizes and subaccounts, which the future reconciler must match against the intended quote before confirmation or capital changes. [Get quotes](https://docs.kalshi.com/api-reference/communications/get-quotes)

Use the current RFQ-scoped lifecycle routes when building transport; older quote-only get/delete/confirm routes are marked deprecated in the current navigation. [Get RFQ quote](https://docs.kalshi.com/api-reference/communications/get-rfq-quote) · [Confirm RFQ quote](https://docs.kalshi.com/api-reference/communications/confirm-rfq-quote) · [Delete RFQ quote](https://docs.kalshi.com/api-reference/communications/delete-rfq-quote)

## Persistent risk-hold integration

`src/combos/execution_risk.py` now couples creation of a quote intent with a persistent hold in the same SQLite transaction. It applies a fixed cash/deployment ceiling and canonical contract/combo/fixture buckets, conservatively rounds liabilities upward and limits downward, prevents a second active hold for the same RFQ, and checks idempotent reservation identity. Existing pricing must supply the full worst-case liability including fees and correct canonical buckets; this module does not infer those from a request body.

Sent holds have no timer-based release. Neither transport acknowledgment nor timeout allows local abandonment. An unsent intent can be abandoned atomically with its hold; it then cannot be claimed for dispatch. Serialized transactions cover both orderings of the abandon/dispatch race. Restart preserves all held cash and bucket exposure. Nested journal savepoints allow intent and risk changes to roll back together.

The integration is an accounting foundation, not a live account mirror: it uses an explicit initialized cash balance and has no settlement, external balance refresh, terminal exchange reconciliation, or authenticated dispatch adapter yet. It must not run alongside an unrelated ledger as though their capital were independent. Ten focused tests cover journal dispatch, crash/restart, atomic rollback, duplicate RFQs, risk multipliers, persistent holds, concurrent reservation limits and unsent abandonment.

## Quote identity and returned-size evidence

`quote_reconciliation.py` adds strict matching of a private quote snapshot to the intended RFQ, market, creator user/subaccount, bids, rest/post-only flags and known quote ID. It requires timestamped evidence after preparation and dispatch, bounds returned side quantities by an explicit intended maximum, and rejects missing target-cost size fields rather than estimating them. Fixed-contract RFQs must retain their original count. It checks the intended NO-only quote orientation and rejects a reported YES-side acceptance.

The conservative quantity check bounds both returned side counts. The exact accepted-side/side-size semantics still require authenticated private-flow validation; no automatic confirmation is authorized by this matcher. Its maximum-contract bound is supplied by the caller and is not yet derived from the persistent dollar hold. The next adapter must independently compute fee-inclusive liability and link that to the hold before confirmation.

`QuoteReconciler` binds expected prices/account behavior and preparation time to the durable create intent, rejects never-dispatched intents, checks a known create acknowledgment's ID and writes snapshot assessments as journal events. It leaves dispatch state and risk holds unchanged. Twenty-four combined execution tests pass, including 14 snapshot-matching cases. There is still no authenticated transport or live confirmation path.

The current scoped acceptance endpoint documents `accepted_side` as required, despite its generated examples showing an empty body. Prefer the field schema over that example when building the requester-side test harness. [Accept RFQ quote](https://docs.kalshi.com/api-reference/communications/accept-rfq-quote)

## Fee-inclusive liability tied to the hold

`execution_liability.py` now atomically saves the liability evidence, reserves its cash bound and prepares the NO-only post-only quote intent. It requires a fee-rate ceiling, account balance precision, references for both, and a validity interval. It refuses to assume precision when evidence is missing. Returned size is assessed against the actual persistent hold using current fee evidence; an oversized or insufficiently funded result does not increase or release the hold.

For quantity q, NO limit p and fee-rate ceiling r, the cash bound is q×p + q×r×p×(1−p) + N×u, rounded upward to $0.0001. N=q/0.01 bounds the number of nonzero fills, and u is account balance precision. Per-fill model-fee ceiling plus balance alignment adds no more than u; ignoring rebates is conservative. Total buy debit p+r×p×(1−p) increases with p for 0≤r<1, so fills at improved prices remain covered. This is a cash-reservation bound, not the expected fee used to measure strategy edge.

Example: 10 contracts at NO $0.70 and r=.035 have $7 principal, $.0735 modeled fee and a $.10 worst-fragmentation allowance for a direct-account precision of $.0001: $7.1735 held. Coarser account precision gives a larger bound. Actual fragmentation, accumulators and fees must be measured before replacing this bound with a tighter one.

The fee rounding rules specify six-decimal trade fees, account-specific balance alignment and capped rounding rebates. [Fee rounding](https://docs.kalshi.com/getting_started/fee_rounding) Quantities have .01-contract minimum granularity and prices up to four dollar decimals. [Fixed-point representation](https://docs.kalshi.com/getting_started/fixed_point_migration)

Thirty-two execution tests pass, including fragmented cash-debit comparisons at both account precisions, several prices/rates, quote-size overrun, expired/missing evidence and rejection of non-post-only requests. The current live account's precision still requires verification. This assessment does not authorize confirmation, verify authenticated snapshot provenance, or reconcile fills/settlements.
