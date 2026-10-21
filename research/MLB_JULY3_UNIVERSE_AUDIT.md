# July 3 native MLB seller-universe: independent audit

The broad public-print seller proxy loses **$2,884,545.061800 after the archived maker-fee scenario**. Independent Decimal arithmetic reproduces the result. This is not a simulated 10k-capital strategy, actual maker execution, a pricing-model result or evidence that every market maker lost money.

## Full-row verification

All 197,843 pure-MLB rows were checked without sampling. There are 178,933 YES-taker prints and 18,910 NO-taker prints excluded from the seller proxy. Native `taker_side` and `taker_outcome_side` agree on every row; YES rows have `taker_book_side=bid`. Prices are complementary, quantities positive, trade IDs unique, and all records lie in the complete July 3 Chicago calendar day. The 24 contiguous hourly census manifests match their retained hashes.

Every row's native combo metadata agrees with settlement value, finalized status, settlement timestamp, leg count, fixture-token membership and same-game/distinct classification. Settlements occur after their trades. No unknown outcome was assigned a zero or imputed; binary outcomes also agree with native result fields. Fractional settlement values are preserved exactly, rather than being coerced into wins/losses.

Independent fee arithmetic ceilings the quadratic fee at six decimals and then aligns the hypothetical buy-NO debit to direct-account $0.0001 cash precision, with zero prior order carry. All archived fees match exactly. This audits implementation of the retained **unverified historical .035 maker-rate scenario**, not the exchange fee effective date, participant-specific precision, actual fill grouping or rebates. The scenario remains unverified; we made no new documentation/provider calls.

| Quantity | Exact dollars |
|---|---:|
| YES premium | 6,793,116.380250 |
| Payout face notional | 109,232,721.320000 |
| Actual native settlement obligation | 9,512,004.781000 |
| Gross seller P&L before fees | -2,718,888.400750 |
| Maker fees | 165,656.661050 |
| Net seller P&L | -2,884,545.061800 |
| Sum of hypothetical NO cash debits | 102,605,261.600800 |

Payout face notional is quantity, not customer winnings. Native customer settlement obligation is $9,512,004.781000. With **zero fees**, this seller proxy still loses $2,718,888.400750; fees cannot explain away the loss. Of the included prints, 36,289 settle at one, 142,522 at zero, and 122 fractionally. Fractional rows contribute $-14,849.179900 net.

Reference JSON totals differ only through floating-point accumulation (largest $0.00001059 on $102.6m summed NO cash; net difference $0.000000169). We allowed $0.0001 aggregate comparison tolerance for float displays; every row's fee and native settlement comparison is exact. Largest archived per-row float-P&L deviation is $0.000000000005.

## Fixture concentration and leave-one-out

Fixture membership is overlapping; these rows must never be summed as an additive P&L attribution. Leave-one-out removes every print involving the listed native fixture token once. All **54** native-token leave-one-out portfolios remain negative. This does not establish independent observations: many prints share the same underlying outcomes, and the fixture token labels have not received a separate schedule-alias review.

| Native fixture | Included prints | Membership net P&L | Net after excluding fixture |
|---|---:|---:|---:|
| 26JUL032145MILAZ | 75,591 | $-1,980,639.68 | $-903,905.38 |
| 26JUL032210SDLAD | 83,461 | $-1,652,347.47 | $-1,232,197.60 |
| 26JUL032015TBHOU | 54,553 | $-1,354,968.36 | $-1,529,576.70 |
| 26JUL031905MINNYY | 67,386 | $-1,069,512.47 | $-1,815,032.59 |
| 26JUL031845PITWSH | 64,932 | $-1,057,833.58 | $-1,826,711.48 |
| 26JUL031915NYMATL | 53,772 | $-1,020,412.77 | $-1,864,132.30 |
| 26JUL032140MIAATH | 61,339 | $-804,140.92 | $-2,080,404.15 |
| 26JUL031910BALCIN | 55,832 | $-633,297.78 | $-2,251,247.28 |
| 26JUL032210TORSEA | 58,521 | $-411,137.01 | $-2,473,408.06 |
| 26JUL032138BOSLAA | 50,872 | $-397,923.86 | $-2,486,621.21 |

## Disjoint cuts


legs:

| Cut | Prints | Net P&L |
|---|---:|---:|
| 3 | 34,192 | $-822,247.27 |
| 5+ | 79,186 | $-724,674.12 |
| 4 | 27,205 | $-452,472.62 |
| 2 | 38,350 | $-885,151.04 |

phase (phase is scheduled-start proxy):

| Cut | Prints | Net P&L |
|---|---:|---:|
| True | 99,068 | $-1,627,674.54 |
| False | 79,865 | $-1,256,870.52 |

structure:

| Cut | Prints | Net P&L |
|---|---:|---:|
| distinct | 129,737 | $-2,953,514.99 |
| same_game | 49,196 | $68,969.93 |

family:

| Cut | Prints | Net P&L |
|---|---:|---:|
| core | 130,702 | $-2,965,489.72 |
| player_prop | 38,362 | $30,878.65 |
| other | 9,869 | $50,066.01 |

premium:

| Cut | Prints | Net P&L |
|---|---:|---:|
| <=10 | 104,911 | $-190,165.32 |
| 10-50 | 53,054 | $-702,214.59 |
| 50-250 | 17,107 | $-846,001.18 |
| >250 | 3,861 | $-1,146,163.97 |

Every disjoint cut sums exactly to the full Decimal total. Same-game, player-prop and other-family slices are positive here, while distinct-fixture/full-game core slices drive losses. These are ex-post descriptions, not approved selection policies. Both pregame and after-scheduled-start slices lose, as do all four leg-count and premium cuts. The <=$10 slice loses less in dollars but is not profitable on this day.

## Interpretation and retained evidence

This materially weakens any claim that selling every MLB print is uniformly profitable. A large print count does not create hundreds of thousands of independent bets; shared fixtures produce clustered settlement risk. The next comparison should use the completed exchange/model common cohort, preserve its coverage denominator, and evaluate selections and rejected prints alongside this broad benchmark. Do not conflate this full native universe with the narrower 2–4-leg pregame model universe or use the losing fixtures as a hindsight exclusion policy.

The standalone audit uses no production economics or classification imports. `verify.py` is retained beside `verification.json`, including all input hashes, exact cuts, all 54 leave-one-out records and verification timing. No production source or prior artifact was edited; no provider calls, August data, models or plots were used. Runtime was 7.67 seconds, peak macOS RSS 1.50 GiB while reading retained native metadata. No child/background processes remain.
