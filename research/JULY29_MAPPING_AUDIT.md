# July 29 mapping coverage audit

**All 112 unmatched contracts are missing exact selected-outcome/line combinations in the retained PM catalog.** The saved data supports no July 15-style clock repair. No unmatched contract lacks a same-team event at the exact native scheduled clock, and none fails because the full-game market family itself is absent. The excluded set consists of **87 total lines and 25 team-specific spread lines**; every required moneyline maps successfully.

The frozen exchange inventory has 448 required contracts, 336 matched. The completed replay contains 43,830 primary eligible prints, all Kalshi-priced, with 40,906 priced by PM and both fixed blends. This audit reads only July 29 native metadata, retained PM events, mapping, pricing contexts and replay rows. It does not examine August outcomes, change matching, or request new data.

## Unique-print coverage

| Category | Unique primary prints | YES premium | Payout notional |
|---|---:|---:|---:|
| Common priced | 40,906 | $2,030,287.48 | $11,279,744.17 |
| Exact line missing only | 830 | $74,217.66 | $308,177.99 |
| Exact line missing plus another leg without prior PM price | 803 | $80,007.31 | $259,424.68 |
| No prior PM price only | 1,291 | $106,787.94 | $401,491.31 |
| Entire eligible Kalshi cohort | 43,830 | $2,291,300.38 | $12,248,838.15 |

The mutually exclusive rows reconcile exactly to the primary universe. Mapping gaps affect **1,633 unique prints**; no-prior-price gaps affect **2,094**, with **803 overlapping**. Consequently, 2,924 prints are excluded from the common cohort. The existing `exact_PM_mapping_missing: 2210` and `no_prior_state: 2866` figures count **leg occurrences**, not unique excluded prints; they must not be added or presented as trade counts.

Missing spreads occur on 481 unique prints and missing totals on 1,187; these also overlap. Contract-level coverage (75%) understates print-level common coverage (93.3%) because many missing alternate lines appear relatively infrequently. The priced cohort nevertheless covers a lower share of YES premium, so print coverage alone does not establish representative economics.

## What is missing

The audit follows the frozen matcher through exact team identity, exact event time, market family and the **selected team's signed handicap**, before inspecting payoff/fee validation. All 112 exclusions occur at the exact outcome/line step, before a candidate payoff/fee failure. There are zero classified missing-fixture, missing-family, schedule-discrepancy or candidate-rule/fee-schema cases in this unmatched set.

Examples:

- `KXMLBSPREAD-26JUL291545MILSF-MIL4` asks for Milwaukee to win by more than 3.5 runs. The exact PM event exists, but its available Milwaukee handicaps are −2.5, −1.5, +1.5 through +9.5. Milwaukee −3.5 is absent. A PM market with numeric `line=-3.5` exists for the **other team**; its Milwaukee outcome is +3.5, not the required −3.5. Matching the bare number would introduce a payoff error.
- `KXMLBTOTAL-26JUL292138HOULAA-8` needs over 7.5. The exact event's retained totals are 8.5, 9.5, 10.5, 11.5 and 12.5; none represents that payoff.
- `KXMLBTOTAL-26JUL291945CHCSTL-11` needs over 10.5. Saved total lines stop at 9.5.
- `KXMLBSPREAD-26JUL291310ATLNYMG1-NYM4` needs Mets −3.5 in Game 1. The exact 17:10 UTC full-game event exists, but that line does not. The nearby second-game/rescheduled event retains an older slug date and a different clock; it must not supply a substitute line.

“Absent” here means absent from the **retained catalog snapshot**. This audit does not establish that a line never existed historically, that no provider can recover its native token, or that the existing discovery query is a complete market-version history. There is no evidence permitting an invented token, nearest-line substitution, first-five/full-game interchange, or a global clock tolerance.

## Concentration of mapping-related exclusions

These are unique affected primary prints per fixture, restricted to prints with a missing contract in that fixture. Counts across rows **overlap** when a combo contains missing lines in several games.

| Fixture | Affected unique prints |
|---|---:|
| Houston–Angels, July 29 | 276 |
| Milwaukee–San Francisco, July 29 | 267 |
| Cubs–St. Louis, July 29 | 193 |
| Arizona–Pittsburgh, July 29 | 182 |
| Boston–Athletics, July 29 | 155 |
| Kansas City–Minnesota, July 29 | 126 |
| Toronto–Washington, July 29 | 116 |
| Cleveland–Cincinnati, July 29 | 116 |
| Seattle–Dodgers, July 29 | 114 |
| Philadelphia–Miami, July 29 | 108 |
| Atlanta–Mets Game 1, July 29 | 107 |
| Colorado–San Diego, July 29 | 102 |

Twenty-five fixtures contribute missing-line occurrences overall. The largest individual exclusion is Milwaukee −3.5, on 158 prints. All fixture/contract counts, supported signed lines, exact event slugs, nearby clocks, and every unpriced print's mapping/history categories are retained in [audit evidence](../runs/july29_mapping_audit_20260907/evidence.json), together with source hashes.

## Recommendation

Preserve the July 29 baseline mapping decisions. Unlike July 15 NYM–PHI, this audit finds no identity mismatch that a narrow schedule-revision overlay could repair. Do not loosen doubleheader matching or use an opposing team's similarly numbered handicap.

For future historical coverage work, first investigate whether native market-version archives expose the missing exact side/line tokens. That is a catalog/history-discovery question and must retain exact payoff proof. For the 1,291 prior-price-only prints, distinguish insufficient seed capture from genuinely unavailable early source states using request intervals and first native source times before spending requests or extending carry-forward. Current missing histories must remain unavailable, not filled with later prices.

Research can continue with the paired 40,906-print cohort and the broader Kalshi-only universe, explicitly reporting the difference. Any future score-distribution or line-interpolation model would be a separate modeled fair, requiring validation; it cannot be labeled a directly matched PM price. No repair was implemented or forecast to restore a particular number of prints from the present evidence.

Verification: all 112 missing legs were classified; the 2,210 mapping leg-occurrence total reconciles to the frozen coverage report; context-based unique-print categories match presence/absence in PM replay exactly; category counts sum to 43,830; quoted input hashes were retained. No P&L or eventual game outcome was used to select, classify or prioritize a mapping repair.
