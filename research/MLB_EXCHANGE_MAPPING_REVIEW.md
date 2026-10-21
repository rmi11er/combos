# MLB exchange mapping review — September 7, 2026

The reviewed exchange join retains **935 matched underlying contracts** and **220 unmatched contracts**, with no changes to the original matched tokens. The added checks guard against plausible mapping mistakes before pricing. They do not select mappings on favorable realized outcomes.

`scripts/mlb_exchange_acquire.py` now validates:

- The exact timezone-aware scheduled start and ordered native away/home team identity. An old Polymarket slug date is not used as a schedule substitute.
- Ordinary full-game resolution language, rejecting first-five/individual-inning and other partial-game text even when `sportsMarketType` says moneyline.
- Both exchange machine lines against actual normal-game resolution language, including half-point totals, signed spread handicaps, and the complement outcome.
- Distinct numeric outcome tokens and known team identities.
- Explicit doubleheader game numbers when present. Exact distinct game times remain the primary join when Polymarket does not label a game number; conflicting explicit numbers are rejected, and multiple same-time candidates remain ambiguous.
- A known fee enablement flag and, for enabled fees, a finite rate in [0,1), exponent 1, and `takerOnly: true`.

The native example `KXMLBGAME-26SEP041410DETCLEG1-CLE` matches the 18:10 UTC Detroit/Cleveland event. Its Polymarket slug still contains June 14, but the structured start is September 4. Game 2 has a separate 23:15 UTC start and separate tokens. Seven reviewed mappings carry native G1/G2 identifiers. These mappings remain flagged as ordinary-completed-game matches, not proof of exceptional-settlement equivalence or historically available schedule metadata.

## Fees must stay market-specific

Of the 935 matches, **923 currently report a 0.05 Polymarket taker fee parameter and 12 report 0.03**. The assumption that every MLB market should use 0.03 would be wrong for the archived metadata. The reviewed mapping preserves each market's actual schedule and retains `historical_fee_effective_date_verified: false`.

Archived Kalshi GAME, SPREAD and TOTAL series each report multiplier 0.5, which yields the current individual-contract taker parameter **0.035** under the repository's quadratic fee formulation. That is distinct from the combo seller's maker fee. GAME additionally reports individual-contract maker fees, whereas SPREAD and TOTAL report quadratic taker fees only. Neither current series metadata nor current Polymarket metadata by itself proves the historical effective date.

## Independent corroboration

For 916 matched legs, the selected Polymarket token currently has a 0/1 outcome price and Kalshi has a settlement value. **All 916 agree; none disagree.** Nineteen have nonbinary/unresolved current Polymarket prices. Current token prices are not treated as authoritative settlement records, and outcome agreement was never used by the matcher. This is useful corroboration after a deterministic identity/payoff join, not a replacement for one.

Artifacts under `runs/mlb_historical_20260907/exchange/`:

- `polymarket_mapping_reviewed.json`: reviewed mapping for research pricing.
- `mapping_review_summary.json`: counts, fee distribution, mapping changes and source hashes.
- `mapping_outcome_audit.json`: complete corroboration rows and doubleheader markers.

Fourteen focused tests pass. They cover wrong/missing timezones, different fixture times, postponed slugs, doubleheader conflicts/ambiguity, partial games, invalid token pairs, unsupported fee schedules, spread sign/complement mistakes, and mismatched total thresholds. The existing acquisition flow was preserved; no collector was restarted and no additional API calls were needed for this review.
