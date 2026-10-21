# July 11 All-Star identity interruption

The exchange stage fails locally while constructing collection windows because `identity()` recognizes only the 30 club codes. `ALNL` has no unique decomposition in `TEAM_NAMES`; both `KXMLBGAME-26JUL142000ALNL-AL` and `...-NL` therefore raise `unresolved_fixture_or_doubleheader_identity`. This is an unsupported exhibition-team identity, not evidence of corrupt ordinary-game data or missing provider history. The failure happens before this stage's provider discovery loop.

## Affected scope

Using precisely the acquisition eligibility predicate on the completed native candidate file (distinct fixtures, 2–4 legs, YES taker):

| Scope | Prints | YES premium | Payout face |
|---|---:|---:|---:|
| All eligible | 28,473 | $1,479,842.72715 | $7,441,747.80 |
| Contains All-Star AL/NL leg | 4 | $69.02308 | $444.03 |
| No All-Star leg | 28,469 | $1,479,773.70407 | $7,441,303.77 |

The broader candidate file has 29 AL/NL-containing prints ($242.09226 premium/$59,912.38 face), including ineligible sizes/structures. Neither count represents a full-universe impact estimate. The four exact affected print IDs, leg selections and classifications are retained in the evidence folder. Figures use native trade economics, without repricing or selecting by outcomes.

## Cached matching evidence

The completed July 9 exchange catalog already contains `mlb-al-nl-2026-07-14`, titled MLB All-Star Game. Its structured start is **July 15 00:00 UTC**, matching the native July 14 20:00 New York clock. Full-game moneyline outcomes are **American League / National League** and the market was created July 9. A distinct first-five-innings winner event is also present; that partial-game contract must remain excluded.

Two additional obstacles exist beyond the team-code dictionary:

- Mapping aliases must recognize American League→AL and National League→NL, with exhibition identity explicit rather than confusing them with club names.
- Existing moneyline prose validation searches literally for `... win the game`; retained All-Star rules say `... wins the game`. Merely adding the two codes will still leave this mapping unmatched. Any validation extension should accept only reviewed grammatical variants while retaining exact outcome identity, full-game scope and start checks.

The full-game PM market has `feesEnabled: true`, schedule **rate .03, exponent 1, takerOnly true**. This is supported by the existing fee parser, but historical effective-date applicability is still unverified. Do not assume zero PM fees for this event. Successful catalog identity does not prove a causal price state existed at each affected print; history must still be acquired/validated through the ordinary mechanism.

## Payoff caveats

Native rules resolve to YES if AL/NL wins; delayed games remain open within two days, while cancellation or rescheduling beyond two days permits fair-price settlement. PM rules resolve to the winning league; postponement remains open until completion, while cancellation without makeup or a tie resolves 50–50. Thus ordinary declared-winner identity is plausible, but exceptional payoff parity is explicitly unverified and differs in the saved text. The cached description does not independently certify special All-Star tie-breaking procedures. Do not infer complete payoff equivalence from matching league labels or final outcomes.

## Safe recovery options for root review

Preserve the frozen batch and original failure evidence. A separately versioned recovery workflow can either (a) explicitly exclude unsupported exhibition fixtures from cross-venue pricing, record the four omitted prints and allow the other 28,469 eligible prints to proceed, while retaining the entire native universe; or (b) support an explicitly reviewed All-Star identity/rule adapter with source aliases and fee schedule, acquire causal histories, and retain exceptional-payoff limitations. A blanket catch-and-ignore of unknown ticker identities would hide future coverage defects and is inappropriate.

Option (a) is the smaller bounded recovery; option (b) retains the four pricing candidates if its safeguards pass. Neither requires deleting native records, changing reported native P&L, altering ordinary-game mapping, or editing frozen scripts. No recovery process was started by this audit.

Evidence directory: `runs/morning_research_20260908/july11_identity_review/` contains `counts.json`, `affected_eligible_prints.json`, `cached_pm_candidates.json`, and `input_hashes.json`. Inputs are July 11 completed native cohort files and the completed July 9 PM catalog. No provider calls, August outcomes or frozen code edits were used.
