# July 5 native MLB universe audit

Sunday's broad public-print seller proxy returns **+$1,931,852.344200 after the archived fee scenario**. This is a new development diagnostic, not an out-of-sample certification or a funded strategy result. It reverses July 3's sign; neither day supports a claim that selling every MLB print is reliably profitable or unprofitable.

## Independent full-row checks

All 207,677 pure-MLB rows were audited: 187,774 YES-taker prints included and 19,903 NO-taker prints excluded. Trade IDs are unique; native outcome/taker direction fields agree; YES/NO prices sum to one; all quantities and prices are valid. All rows lie in the complete July 5 Chicago calendar-day census. The 24 contiguous hourly source manifests match their hashes, with census weight one.

Every retained native combo settlement value, finalized status, settlement timestamp, leg count, distinct/same-game classification and fixture membership agrees with its ledger row. Settlement follows trade time. All outcomes are known: 164,657 YES-taker prints settle at zero, 23,068 at one, and 49 fractionally (30 at .15, 16 at .19, 3 at .13). Fractional obligations are preserved exactly; no unknown outcome was imputed as zero.

Independent Decimal arithmetic reproduces each fee using micro-dollar fee ceiling then $0.0001 direct-account NO-debit alignment with zero prior order carry. Historical .035 maker-rate effective-date applicability and actual participant precision/fill grouping remain **unverified scenario assumptions**, not newly certified exchange facts. The calculation uses no production fee/economics imports.

| Metric | Exact dollars |
|---|---:|
| YES premium | 7,527,404.522450 |
| Face payout notional | 107,227,109.430000 |
| Actual native settlement obligation | 5,411,550.527900 |
| Gross seller P&L | 2,115,853.994550 |
| Maker fee scenario | 184,001.650350 |
| Net seller P&L | 1,931,852.344200 |
| Sum of hypothetical NO cash debits | 99,883,706.557900 |

Face notional is contracts at a $1 maximum payout; it is not what customers won. Summed NO cash is turnover in hypothetical full-print commitments, not simultaneous required capital. Eventual P&L is attributed to trade time. Fee verification is exact; original float aggregation differs by at most $0.00000777 across totals, immaterial to the result.

## Fixture omission

All 63 native-token fixture-omission portfolios remain positive. The largest contributing membership is SD–LAD July 5: +$1,313,302.668000 on 67,012 prints. Removing every print with that fixture still leaves +$618,549.676200. Membership overlaps; these profits must not be added together. This is ex-post deletion, not an actionable fixture-selection rule, and native tokens are not a separate semantic schedule-alias audit.

| Fixture | Prints involving fixture | Membership net | Net omitting fixture |
|---|---:|---:|---:|
| 26JUL051920SDLAD | 67,012 | $1,313,302.67 | $618,549.68 |
| 26JUL051500PHIKC | 56,049 | $671,437.86 | $1,260,414.48 |
| 26JUL051600MILAZ | 50,608 | $637,310.26 | $1,294,542.09 |
| 26JUL051600SFCOL | 45,475 | $620,042.21 | $1,311,810.13 |
| 26JUL051230NYMATL | 62,812 | $581,791.36 | $1,350,060.99 |
| 26JUL052130BOSLAA | 60,981 | $534,351.28 | $1,397,501.06 |
| 26JUL051400CWSCLE | 51,630 | $492,343.24 | $1,439,509.11 |
| 26JUL051700TORSEA | 42,854 | $491,664.19 | $1,440,188.15 |
| 26JUL051530TBHOU | 44,142 | $443,324.46 | $1,488,527.88 |
| 26JUL051630MIAATH | 50,813 | $401,932.46 | $1,529,919.88 |

## Disjoint cuts

### legs

| Category | Prints | Net P&L |
|---|---:|---:|
| 3 | 34,210 | $451,892.76 |
| 4 | 27,519 | $203,660.95 |
| 5+ | 79,750 | $816,809.32 |
| 2 | 46,295 | $459,489.31 |

### phase

| Category | Prints | Net P&L |
|---|---:|---:|
| False | 104,443 | $679,264.41 |
| True | 83,331 | $1,252,587.94 |

### structure

| Category | Prints | Net P&L |
|---|---:|---:|
| distinct | 131,954 | $1,308,632.15 |
| same_game | 55,820 | $623,220.19 |

### family

| Category | Prints | Net P&L |
|---|---:|---:|
| core | 138,145 | $1,426,411.03 |
| other | 10,856 | $116,374.03 |
| player_prop | 38,773 | $389,067.28 |

### premium

| Category | Prints | Net P&L |
|---|---:|---:|
| 10-50 | 55,590 | $481,327.42 |
| <=10 | 109,707 | $220,422.64 |
| 50-250 | 18,365 | $510,460.51 |
| >250 | 4,112 | $719,641.77 |

All displayed cuts sum exactly to the full total and all are positive. Phase is only the retained native scheduled-start proxy, not independently verified actual first pitch. July 5 is the trade date, not a requirement that all legs take place that Sunday.

## Implication and artifacts

The paired July 3/5 broad totals sum to **−$952,692.717600**, before considering other certified dates. The opposite signs and clustered underlying outcomes reinforce the need for longer fixed-cohort research, common-model comparisons and fixture-aware uncertainty. Do not conclude stable Sunday edge from this one Sunday or extrapolate a funded return from unlimited full-print exposure. Public trades are a seller benchmark, not proof of RFQ win probability or actual maker executions.

The existing `scripts/mlb_dated_universe_report.py` produced `runs/morning_research_20260908/universe_july5/{summary.json,curves.jsonl.gz,universe.png,universe.svg,REPORT.md}`. Its chart was visually inspected: six readable panels, explicit unverified fee label, no one-day Sharpe or variance invented. Chart points are five-minute aggregates; `curves.jsonl.gz` stores increments, not cumulative values. Native full-resolution rows remain in the cohort.

Separate `universe_july5_audit/verify.py` and `verification.json` retain all hashes, exact arithmetic, all cuts and all 63 omission records. Audit runtime 7.39 seconds, peak macOS RSS 1.56 GiB during native metadata loading. No provider calls, August data, prior-artifact changes or frozen-source edits. All foreground work finished.
