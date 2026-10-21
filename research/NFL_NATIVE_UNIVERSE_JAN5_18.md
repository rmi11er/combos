# Full January 5–18 NFL native seller-universe benchmark

The complete 14-day native seller proxy earns **+$3,111,351.383800 under the .035 maker-fee scenario**, but most of this gain is associated with SF–SEA and with same-game/player-prop combos. The native primary structural scope loses **$182,661.271600**. The broad positive curve must not be mistaken for validation of the intended pregame game-market model.

## Full retained-data verification

The independent verifier reconciles all **982,703 YES-taker rows** to original native cohorts, all **819,658 full-resolution timestamp curve points**, and exact premium, fees, P&L and NO-cash identities under all four fee scenarios. All 84 benchmark input hashes and three completed artifact hashes match. There are 1,016,915 total native prints; 34,212 NO-taker prints are excluded. No sampling or source rows were dropped. Unique ordering is `(trade timestamp, trade ID)`.

All included outcomes are known; **65 fractional settlements** remain exact. **87,048 unknown schedules** remain unknown, not relabeled as in-play or pregame. Verification uses the existing fee helper to independently reconcile ledgers and curves, not a separate certification of its exchange applicability. January maker rates, participant balance precision and per-print fee grouping remain explicit unverified scenarios. No provider calls or retrospective fee certification were performed.

| Metric | Exact dollars |
|---|---:|
| YES premium | 29,091,651.789000 |
| Payout face notional | 396,423,283.000000 |
| Maker fees (.035) | 742,676.525200 |
| Net seller P&L (.035) | 3,111,351.383800 |
| Summed hypothetical NO cash | 368,074,307.736200 |
| Native settlement obligation | 25,237,623.880000 |

Face notional is maximum contractual payout, not customer winnings. Summed NO cash is turnover, not concurrent capital. Eventual settlement P&L is attributed at trade time; this is not spendable equity.

| Maker coefficient scenario | Net P&L |
|---|---:|
| 0 | $3,854,027.91 |
| 0.0175 | $3,482,665.61 |
| 0.035 | $3,111,351.38 |
| 0.07 | $2,368,723.20 |

## Daily attribution

| Chicago trade date | Net P&L (.035) |
|---|---:|
| 2026-01-05 | $-32,308.89 |
| 2026-01-06 | $-37,754.27 |
| 2026-01-07 | $-100,765.61 |
| 2026-01-08 | $-62,510.83 |
| 2026-01-09 | $-275,977.71 |
| 2026-01-10 | $-1,846,716.03 |
| 2026-01-11 | $938,630.83 |
| 2026-01-12 | $1,029,246.90 |
| 2026-01-13 | $-23,854.69 |
| 2026-01-14 | $141,345.12 |
| 2026-01-15 | $146,035.27 |
| 2026-01-16 | $242,806.67 |
| 2026-01-17 | $1,930,266.70 |
| 2026-01-18 | $1,062,907.93 |

The curve suffers a large first-week decline and recovers in the second week; January 17 alone contributes +$1.930m. The first eight dates through January 12 were −$388,155.614. This is not a uniformly rising equity curve. Daily descriptive P&L variance is 7.4681e11 USD²; Sharpe remains unavailable because the unlimited benchmark lacks a funded-return denominator and shared playoff games limit independent evidence.

## Native disjoint cuts

Native structure is based on token identity, with the separate semantic correction below. No schedule or scope classification was silently altered.

### legs

| Cut | Prints | Net P&L (.035) |
|---|---:|---:|
| 2 | 255,336 | $805,883.76 |
| 3 | 194,108 | $499,685.23 |
| 4 | 183,557 | $636,864.02 |
| 5+ | 349,702 | $1,168,918.38 |

### structure

| Cut | Prints | Net P&L (.035) |
|---|---:|---:|
| Contains same-game legs | 853,622 | $3,560,852.10 |
| Distinct fixtures | 129,081 | $-449,500.71 |

### family

| Cut | Prints | Net P&L (.035) |
|---|---:|---:|
| Full-game core | 211,007 | $-371,597.44 |
| Includes known player prop | 763,860 | $3,512,719.11 |
| Other NFL family | 7,836 | $-29,770.28 |

### phase

| Cut | Prints | Net P&L (.035) |
|---|---:|---:|
| After schedule cutoff | 244,949 | $1,331,516.70 |
| Pregame schedule proxy | 650,706 | $895,103.18 |
| Unknown schedule | 87,048 | $884,731.50 |

### scope

| Cut | Prints | Net P&L (.035) |
|---|---:|---:|
| Outside primary structural scope | 943,425 | $3,294,012.66 |
| Primary structural scope before source pricing | 39,278 | $-182,661.27 |

### premium

| Cut | Prints | Net P&L (.035) |
|---|---:|---:|
| $10–50 | 241,562 | $916,388.45 |
| $50–250 | 68,752 | $806,147.02 |
| Above $250 | 14,230 | $747,040.23 |
| At most $10 | 658,159 | $641,775.68 |

## Retrospective SF–SEA semantic overlay

Exact allowlist: `26JAN18SFSEA → 26JAN17SFSEA`. Retained January 12 metadata has 110 native single-game combo definitions combining both token dates, and the retained playoff schedule has one SF-at-SEA divisional fixture. This supports semantic fixture identity for concentration; it does not certify mapping knowledge at trade time, contract payoff equivalence, or a corrected start cutoff.

The generic overlay's last-cohort evidence assumption fails with January 18 metadata, which lacks the older mixed-token examples. A separate adapter pins the already reviewed January 12 evidence while scanning all 14 cohorts. Existing scripts and failed empty output directory remain unchanged; the reviewed overlay has its own directory and source hashes.

| Disjoint SF–SEA alias partition | Prints | Net P&L (.035) |
|---|---:|---:|
| Jan17_only | 99,828 | $1,901,700.82 |
| Jan18_only | 39,818 | $194,317.56 |
| both | 47,230 | $690,413.95 |
| union | 186,876 | $2,786,432.32 |

The union counts each print once. It earns **+$2,786,432.324300**, about 89.6% of full net; removing the whole SF–SEA semantic fixture leaves **+$324,919.059500**. This is overlapping membership concentration, not additive attribution across games. All ten semantic single-fixture omissions remain positive, but the largest omission removes most of the result.

9,990 formerly native-distinct prints become semantic same-game. Their +$188,512.445700 moves structure categories: **863,612 same-game prints earn +$3,749,364.541300; 119,091 distinct-fixture prints lose $638,013.157500**. Total P&L is unchanged. All 87,048 unknown schedules remain unknown, including those associated with the alias; no inference turns identity evidence into causal schedule availability.

| Semantic fixture | Membership net | Net omitting fixture |
|---|---:|---:|
| 26JAN10GBCHI | $-1,579,604.43 | $4,690,955.82 |
| 26JAN10LACAR | $-1,733,490.86 | $4,844,842.24 |
| 26JAN11BUFJAC | $-1,093,625.56 | $4,204,976.95 |
| 26JAN11LACNE | $48,330.14 | $3,063,021.25 |
| 26JAN11SFPHI | $-273,018.88 | $3,384,370.27 |
| 26JAN12HOUPIT | $417,305.12 | $2,694,046.27 |
| 26JAN17BUFDEN | $628,086.51 | $2,483,264.87 |
| 26JAN17SFSEA | $2,786,432.32 | $324,919.06 |
| 26JAN18HOUNE | $817,219.65 | $2,294,131.73 |
| 26JAN18LACHI | $1,335,585.40 | $1,775,765.99 |

## Implications and artifacts

The full native benchmark supports investigating the wider universe, especially same-game and prop structure, but does not justify quoting those correlations at independent-leg fair values. The native full-game-core and primary-structural slices remain negative. Compare the separate four-model exchange replay on its exact denominator; do not use the broad 982,703-print count to describe moneyline pricing coverage or RFQ win probability.

Outputs: `runs/nfl_native_universe_20260908_jan5_18/` (compressed ledger, full-resolution curves, summary/completion and `plots/native_universe.png/.svg`). The unchanged plot workflow verifies every endpoint and daily increment; all timestamps are retained, with rendering path simplification disclosed. The generated chart was visually inspected: fee scenarios and full-volume axes are readable, variance/Sharpe caveats explicit.

Audit: `runs/morning_research_20260908/nfl_native_jan5_18_audit/{verify.py,verification.json,sfsea_overlay.py}`. The verifier adapter changes only the old Jan5–12 hardcoded count assertions to complete Jan5–18 manifest counts. Overlay: `runs/morning_research_20260908/nfl_native_jan5_18_sfsea_reviewed/summary.json`. Native ledger/curve artifacts and all frozen scripts remain unchanged. No provider calls, August data or surviving background jobs.
