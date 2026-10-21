# July 9 native MLB universe audit

The broad seller proxy loses **$1,575,735.269000 net** across 275,489 YES-taker prints. It already loses **$1,319,182.235610 before fees**. The result reproduces independently; an identified CHC–BAL clock-token inconsistency affects classification sensitivity, not settlement arithmetic or portfolio P&L.

## Full-row verification

All 314,083 pure-MLB rows were checked without sampling: 275,489 YES-taker prints included, 38,594 NO-taker prints excluded. IDs are unique, prices complementary, quantities positive, and direction agrees with native taker-outcome fields. All rows lie in the full July 9 Chicago census; all 24 contiguous source manifests match hashes and sample weight one.

Native finalized status, settlement values/timestamps, leg counts and market-token classifications match every row. Settlements occur after trades; binary result fields agree. All outcomes are known, including 114 fractional included settlements, preserved exactly. No unknown outcomes were imputed as zero.

Every fee matches independently reconstructed .035 quadratic maker fee, six-decimal ceiling and direct-account $0.0001 buy-NO cash alignment with zero prior carry. Historical coefficient applicability, participant precision and real fill grouping remain unverified scenarios. Fees are charged once. Aggregate float display drift is less than $0.0001; the exact totals below are unaffected.

| Metric | Exact dollars |
|---|---:|
| YES premium | 10,657,183.442090 |
| Payout face notional | 157,788,651.300000 |
| Native settlement obligation | 11,976,365.677700 |
| Gross seller P&L | -1,319,182.235610 |
| Maker fees | 256,553.033390 |
| Net seller P&L | -1,575,735.269000 |
| Sum of NO cash debits | 147,388,020.891300 |

Face notional is contracts at maximum payout, not customer winnings. Summed cash is turnover, not simultaneous capital. This broad unlimited public-print seller proxy is not our actual executions, funded model or RFQ win-rate estimate.

## Fixture omissions

All native-token one-fixture omission portfolios remain negative. PHI–CIN has the largest losing membership (−$1,509,169.979); even removing all its prints leaves −$66,565.29. Contributions overlap and cannot be summed as additive attribution.

| Native fixture | Membership prints | Membership net | Net after omission |
|---|---:|---:|---:|
| 26JUL091910PHICIN | 122,373 | $-1,509,169.98 | $-66,565.29 |
| 26JUL092005LAATEX | 110,369 | $-1,219,747.58 | $-355,987.69 |
| 26JUL091840ATHDET | 103,991 | $-1,143,686.70 | $-432,048.56 |
| 26JUL091945MILSTL | 94,057 | $-941,346.35 | $-634,388.92 |
| 26JUL091235ATLPIT | 67,919 | $-264,596.47 | $-1,311,138.80 |
| 26JUL091310KCNYM | 58,999 | $-208,872.08 | $-1,366,863.19 |
| 26JUL091340CLEMIN | 51,792 | $-182,193.03 | $-1,393,542.24 |
| 26JUL091410BOSCWS | 51,178 | $-132,277.14 | $-1,443,458.13 |

## Native disjoint cuts

### legs

| Category | Prints | Net P&L |
|---|---:|---:|
| 2 | 68,428 | $-810,262.16 |
| 4 | 41,724 | $-247,959.60 |
| 5+ | 111,637 | $13,826.11 |
| 3 | 53,700 | $-531,339.62 |

### phase

| Category | Prints | Net P&L |
|---|---:|---:|
| Pregame schedule proxy | 143,381 | $-332,066.49 |
| After scheduled start | 132,108 | $-1,243,668.78 |

### structure

| Category | Prints | Net P&L |
|---|---:|---:|
| distinct | 204,029 | $-1,860,860.58 |
| same_game | 71,460 | $285,125.31 |

### family

| Category | Prints | Net P&L |
|---|---:|---:|
| player_prop | 52,942 | $99,553.37 |
| core | 210,234 | $-1,714,778.07 |
| other | 12,313 | $39,489.43 |

### premium

| Category | Prints | Net P&L |
|---|---:|---:|
| 10-50 | 82,243 | $-408,589.64 |
| >250 | 5,779 | $-611,746.40 |
| <=10 | 160,671 | $-50,351.97 |
| 50-250 | 26,796 | $-505,047.26 |

Each disjoint cut sums exactly. Phase True is the native scheduled-start proxy; False means after scheduled start. Neither is independent actual-first-pitch validation. July 9 denotes trade date, not all game dates.

## CHC–BAL clock-token identity sensitivity

Retained metadata directly associates `26JUL091335CHCBAL` market tickers with `26JUL091835CHCBAL` event tickers. This is the sole differing event/market token pair: 2,927 leg occurrences across native combo definitions. It affects 2,356 universe rows, of which 2,266 YES-taker prints have net **+$1,926.010200**. The production classifier follows market tickers; the original audit's event-token assumption was corrected in the separate audit, not in frozen production data.

That explicit native market-to-event association supports an exact, narrow retrospective semantic identity sensitivity, rather than treating matching team names alone as evidence. It does not establish schedule knowledge at trade time, actual kickoff/first pitch, or payoff equivalence. No other dates, teams or potential doubleheaders are merged.

| Alias partition | YES prints | Net P&L |
|---|---:|---:|
| old_only | 1,394 | $-7,597.24 |
| new_only | 57,810 | $-79,963.53 |
| both | 872 | $9,523.25 |
| union | 60,076 | $-78,037.52 |
| distinct_to_same | 193 | $2,663.18 |

The union counts each trade once: 60,076 prints, −$78,037.517700. Removing it leaves **−$1,497,697.751300**. Merging only these aliases reclassifies 193 formerly distinct prints (+$2,663.179500) as same-game. Semantic totals become **203,836 distinct prints / −$1,863,523.758500**, and **71,653 same-game prints / +$287,788.489500**. Baseline total P&L is unchanged. The label 193 is an ex-post classification correction only; no pregame cutoff or pricing eligibility was repaired.

## Evidence and research implication

The substantial gross loss survives fee removal and every individual fixture omission. Together with sign changes across other July dates, this favors fixed cohort/model comparisons and fixture-aware calibration research rather than promoting sell-all or a single daily slice.

`runs/morning_research_20260908/universe_july9_audit/{verify.py,verification.json,REPORT.md}` retains exact row checks, hashes, every cut and omission. `chc_bal_semantic_overlay.json` preserves native examples, narrow allowlist and additive-safe alias partition. Native benchmark plots/summary under `universe_july9` were not changed. Audit runtime 10.89 seconds, peak macOS RSS 1.82 GiB. No provider calls, August data, frozen-source edits or surviving jobs.
