# Maker quote/order/fill ownership evidence

Kalshi's RFQ guide explicitly maps creator_order_id to the maker's order and
rfq_creator_order_id to the requester's order:
https://docs.kalshi.com/getting_started/rfqs
Order identity and fixed-point fields are documented at:
https://docs.kalshi.com/api-reference/orders/get-order

src/combos/execution_ownership.py now validates that distinction. It first matches
the private quote to ExpectedQuote, requires an executed NO-side quote, then checks
the resulting order's maker order ID, user, subaccount, exchange, market, direction,
limit price, quantities and chronology. It never attributes the requester order to
our strategy. Fill matching checks that ownership tuple, maker status, quantity
bound and execution price at or better than the NO limit. Reported fill fees remain
recorded evidence, not recomputed theoretical fees.

Thirty-seven ownership/quote/fill tests pass. They reject requester orders, wrong
users/subaccounts/sides/exchanges, oversized quantities and taker fills; a valid
maker fill at an improved price matches. This is synthetic contract validation,
not verification against a privately executed strategy quote. Timestamp and
accepted-side semantics remain subject to validation on actual private traffic.

No cash is released by these functions. The matcher does not itself authenticate
payloads, durably establish strategy ownership, or prove cumulative fill completion.
Next bind its evidence to the dispatched execution journal and reconcile deduplicated
cumulative fills plus terminal order state before updating holds. Authenticated
account funding/precision and the complete order-confirm/cancel lifecycle remain
required before live deployment. No quote or order was submitted for this work.
