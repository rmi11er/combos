# July 15 NYM–PHI mapping coverage audit

**The mismatch is a real schedule revision, not evidence of two different games.** MLB confirms July 16's start advanced from 7:10 to 6:10pm Eastern because of air quality. [Official MLB notice](https://www.mlb.com/news/mets-phillies-july-16-game-time-change).

The frozen matcher requires event `startTime` to equal the timestamp embedded in the native Kalshi ticker within one second. That compares a mutable current schedule against the contract's original scheduled-game identity. It therefore excludes the NYM–PHI fixture even though the retained contract prose and original schedule agree. This audit does not change that matcher, its frozen baseline, any mapping configuration, or any existing result.

## Retained evidence

| Source | Identity/time evidence |
|---|---|
| Kalshi `KXMLBGAME-26JUL161910NYMPHI-{NYM,PHI}` | Ticker encodes July 16 19:10 America/New_York, or 23:10 UTC. Both contracts' primary/secondary rules explicitly identify the game **originally scheduled** for that clock. |
| PM full-game event `687903`, slug `mlb-nym-phi-2026-07-16` | `gameId=10078738`; `startTime=2026-07-16T22:10:00Z`; `creationDate=2026-07-16T23:10:00Z`; event description still says July 16 at 7:10pm ET. Creation date is not independently a source-observation or creation-availability clock. |
| PM full-game moneyline market `2870228` | Native `gameStartTime=2026-07-16 22:10:00+00`, matching the revised event clock; description retains the original time. |
| PM full-game event's markets | All 22 market records carry the revised 22:10 UTC `gameStartTime`, including moneyline, full-game spreads/totals, NRFI and embedded first-five markets. Thus reading market-level time alone does **not** repair this discrepancy. |
| Separate PM first-five winner event `705612` | Same `gameId=10078738`, original 23:10 UTC start; three first-five winner records. This helps establish shared event identity, not full-game payoff equivalence. |
| Separate PM player-props event `707610` | Original 23:10 UTC start; forty player records; no event `gameId`. These must not supply replacement full-game outcomes. |

The exact archived events are in `runs/mlb_historical_20260907/dated_fee_primary/2026-07-15/exchange/pm_events_complete.json`; native descriptions are in `cohort/underlying_markets.json.gz`. [Audit evidence and input hashes](../runs/july15_mapping_audit_20260907/coverage.json) retain the relevant event objects, mapping diagnostic results and count arithmetic.

## Effect on the July 15 primary opportunity cohort

The frozen replay prices 1,202 eligible prints with Kalshi. Only 392 have PM and therefore reach the four-model common cohort. Missing-map counts in the existing coverage report are **per-leg occurrences**, so 1,148 missing-leg observations must not be reported as 1,148 missing unique prints.

| Missing mapping category | Unique primary prints | YES premium | Payout notional |
|---|---:|---:|---:|
| None: current common cohort | 392 | $10,137.22 | $55,442.34 |
| NYM–PHI only | 343 | $9,713.49 | $61,457.44 |
| NYM–PHI and TB–BOS Game 1 | 338 | $7,002.09 | $56,084.51 |
| TB–BOS Game 1 only | 129 | $2,546.74 | $17,558.52 |
| Entire eligible Kalshi cohort | 1,202 | $29,399.54 | $190,542.81 |

Thus 681 unique primary prints involve the NYM–PHI mapping gap. Of these, 338 still have an independent doubleheader mapping problem. No P&L or outcome was used to classify coverage or diagnose the join.

For a bounded **in-memory diagnostic only**, the original 23:10 UTC clock was supplied to the existing strict matcher for the identified PM full-game event. Seven of the eight requested NYM–PHI contracts then matched all the existing outcome, exact-line, ordinary-payoff prose and fee-schema checks:

- Both moneyline outcomes.
- Phillies and Mets −1.5-run spread outcomes.
- Over 5.5, 9.5 and 10.5 runs.

The eighth, over 8.5 runs (`KXMLBTOTAL-26JUL161910NYMPHI-9`), remains absent from the saved full-game market inventory. Its sole primary print also contains TB–BOS Game 1, so it does not reduce the 343 NYM-only coverage opportunity. Do not interpolate another total or substitute first-five totals.

A narrowly reviewed schedule-revision mapping could therefore make **343 additional prints mapping-complete**, increasing mapping-level coverage from 392 to 735 of 1,202 (32.6% to 61.1%). This is a prospective data-repair ceiling, **not newly priced coverage**: the corresponding PM token histories were not downloaded by the frozen unmatched path. Historical point availability must be established before re-evaluating those prints, and newly reviewed source evidence must retain its retrospective research label.

## Conservative recommendation

Prepare an independent research mapping revision keyed to the exact NYM–PHI fixture and PM full-game event ID, with the official schedule-change reference and original/current clocks retained separately. Keep exact teams, date, outcome, period, line, unique-candidate and rule checks. A stable provider `gameId` and original contract prose can corroborate identity; neither is a blanket replacement for native game-number checks. Do not add a global one-hour tolerance and do not match on same teams/date alone.

For eligibility, original contract identity and current start/status are different fields. Any July 16 replay or forward system must enforce the earlier verified start and actual started status; it must not allow trading until the old ticker clock. The entire July 15 trading window precedes both clocks, so this particular coverage repair cannot admit post-start July 15 prints. The official page displays July 16, 2026 but no intraday publication timestamp in the fetched page. The exact announcement availability time has not been established. The archived PM metadata is a later snapshot, not a versioned schedule history, and cannot establish which schedule was available on July 15. A causal July 15 strategy must not be described as already knowing the later revision. Applying the earlier cutoff retrospectively is a conservative exclusion overlay, not a claim of point-in-time knowledge. Any July 16 print cohort using the original ticker cutoff requires a separate eligibility audit of the intervening hour; no such prints were evaluated in this bounded July 15 audit.

TB–BOS **Game 1 remains a separate unresolved identity**: `KXMLBGAME-26JUL171335TBBOSG1-{TB,BOS}`. The matched evening Game 2 has its own native ticker and PM event. Nothing in the NYM–PHI evidence authorizes substituting that evening event for Game 1, relaxing explicit game numbers, or granting cross-game risk fungibility.

After reviewing the separate mapping revision, collect only the required public PM history into a new output directory, verify its causal intervals, and rerun the four-model common-cohort comparison with baseline versus expanded coverage clearly distinguished. Preserve the frozen original result for reproducibility. Payoff exception and historical fee verification limitations remain unchanged.
