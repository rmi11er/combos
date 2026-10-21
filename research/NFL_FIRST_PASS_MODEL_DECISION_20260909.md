# NFL first-pass model decision

This note records the current bounded decision for the first NFL shadow/live
candidate. It is based on the 37,646-RFQ trace captured on September 9, 2026
and the source-weight comparison in
`runs/nfl_trace_source_weights_20260909/summary.json`.

## What the trace says

There were 275 RFQs priced by every compared model. The captured sharp-peer
policy (the existing liquidity/freshness weighted blend) is the reference.
Changing to equal source priors moved fair by a median 0.013 cents and changed
one capacity admission. Giving PM/Pinnacle a stronger prior moved fair by a
median -0.010 cents and also changed one admission. A delayed-Pinnacle-light
variant moved fair by a median 0.048 cents, with a 95th percentile of 0.442
cents, and changed three admissions. These are model-difference diagnostics,
not profitability evidence: the trace has no observed RFQ acceptance or fill
selection.

The current trace assigns median leg weights of approximately 45.2% Kalshi,
30.3% Polymarket and 27.4% Pinnacle under the reference policy. The source
weights are liquidity/freshness driven rather than fixed; therefore a fixed
“Polymarket is sharper” override would discard information in the book state.

## First-pass policy

The provisional candidate remains:

* three-source liquidity/freshness weighted fair;
* Pinnacle at the documented 30-second delivery delay;
* 0.30 cents per combo contract minimum net edge;
* 2–4 legs, pregame only, no player props;
* full RFQ size only;
* $500 per underlying contract, $500 per combo, $500 per fixture, and at most
  $5,000 committed against the $10,000 strategy budget;
* halve those risk limits when a source-disagreement halt is active;
* creator blacklist in log-and-review mode, with no automatic sanctions.

The edge charge and risk limits are deliberately provisional. The next OOS
study must sweep edge, leg count, source priors, disagreement size and each
risk cap jointly. We should promote a configuration only after acceptance and
fill-selection data, not from observed prints alone.

## Promotion gates

This policy must remain shadow-only until the startup gate reports all of the
following: positive and atomic available cash; reconciled shared account
activity; verified Pinnacle payoff and stake-currency mappings for every
enabled leg; current venue fee metadata; cancellation/hold reconciliation;
and independent OOS acceptance markouts. Integer-line spreads/totals and
exceptional settlement states remain excluded until their push/void model is
implemented and reviewed.

Source artifact hashes and exact counts are in the comparison summary. This
document is descriptive and does not enable order submission.

The saved OddsPapi snapshots contain numeric Pinnacle `limit` values for all
4,220 observed outcomes (range $375–$120,967 as represented by the feed), but
contain no currency or unit field. The audit therefore does not treat those
numbers as verified USD stake limits. See
`runs/nfl_pinnacle_limit_audit_20260909.json`; the missing currency/unit
metadata remains a promotion gate.

## Live OddsPapi probe

On September 9, a read-only probe confirmed an active `pinnacle+30` NFL
subscription with a 100,000-request monthly limit. The entitlement reports no
player props, no live odds and no WebSocket access. A two-poll, 30-second
freshness run consumed three vendor requests (account/catalog/two odds polls
plus the closing account read is reflected in the vendor count) and returned
16 fixtures on each poll. The vendor reported a roughly 30.3–30.7 second
publication lag for changed timestamps, but the freshness verdict was
`inconclusive_membership_changes_only`; this does not prove healthy upstream
price freshness.

The first poll matched all 154 candidate selectors. The second matched 152;
two Cincinnati–Tampa Bay total lines disappeared from the current Pinnacle
snapshot. The exact keys are retained in
`runs/nfl_candidate_selector_audit_20260910_v2.json`. The collector must
therefore treat selector disappearance as a temporary per-leg unavailability,
not carry forward the last quote or silently substitute a nearby line.

A five-poll extension over 122 seconds returned identical economic snapshots
for the first four polls, then restored the two Cincinnati–Tampa Bay lines on
the fifth. The freshness audit still found no economic price changes and
classified the response evolution as membership-only. This supports content
hash caching and per-leg selector revalidation on every new snapshot; it does
not justify assuming that a stable response means Pinnacle is current.

The collector was then exercised for 65 seconds against a fresh event store.
It made three Pinnacle odds polls and produced 462 normalized observations;
the initial implementation recorded 141 active observations per poll. After
the selector-rebind fix, each snapshot emits a selector-coverage audit and
reuses only the reviewed payoff/limit metadata while replacing the native
market/outcome IDs. Missing or inactive lines remain inactive per leg and do
not terminate the collector. A concurrent no-order runtime also collected
Kalshi and Polymarket observations, but this short window contained no
candidate RFQ that reached complete three-source pricing, so it provides an
integration test rather than an execution or P&L result.
