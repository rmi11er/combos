# NFL locked shadow policy reconciliation

The authoritative policy is
`config/tonight_shadow_mlb_nfl_three_source_loose_20260909.json`. The NFL
candidate generated from it is
`runs/nfl_authoritative_locked_candidate_20260910_v2/runtime.json`.

The candidate now has 154 exact full-game mappings: 65 spreads, 87 totals,
and 2 team totals. It records the policy hash and remains explicitly shadow
only. Its risk values are $500 per canonical contract, $500 per combo, $1,000
per fixture, and $10,000 maximum committed capital. Gross ticket liability is
capped at $250. The source policy's no-cash-credit moneyline offset rule is
retained as a research-ledger requirement; it is not silently applied to cash
availability by the shadow engine.

The shadow engine now enforces the ticket cap by rounding quantity downward to
the hundredth of a contract and records both requested and capped quantity.
It also stores the fair point at quote publication and performs a last-look
fair revalidation immediately before a simulated fill. A quote is cancelled
and the fill rejected when the absolute liquidity-weighted three-source fair
point move exceeds the configured `last_look.max_fair_move_cents` threshold,
currently 1.0¢. The invalidation event records the signed fair move, initial
fair, threshold, and current pricing context.

Replaying the archived 90-second NFL input under the locked fail-closed
candidate produced zero quotes: all 77 fully mapped cross-fixture RFQs were
rejected by `pinnacle_payoff_mapping_unreviewed`, as required by the policy.
For diagnostic purposes, an assumption-enabled replay removed that review
block and produced zero quotes under the authoritative 15-second exchange /
5-second combo freshness gates; a research-only replay with exchange age 60
seconds and combo age 15 seconds produced 25 quotes. These are separate
findings: the first is the intended payoff-review halt, while the latter is a
freshness sensitivity. Neither authorizes changing the locked policy.

Focused tests cover last-look rejection and ticket-cap sizing; the full
repository test suite completed successfully after this reconciliation.

### Moneyline offset ledger

The locked runtime now carries the authoritative `moneyline_offset` policy into the
shadow engine. For an exact, reviewed full-game moneyline mapping on distinct
fixtures, contract and fixture caps are checked by payoff side: the larger of the
positive-side and negative-side committed losses must remain below the cap. This
allows an opposing-side offset without algebraic netting. Combo exposure and cash
commitment remain gross, and any partial, ambiguous, non-moneyline, or non-full-game
mapping remains gross-risk-only. Reservations record the signed rows in a separate
ledger so the offset is auditable and does not change available cash.
