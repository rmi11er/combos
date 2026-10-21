# Native NFL seller universe, January 5–12, 2026

**The broad native seller benchmark loses $388,155.61 under the explicit 0.035 maker-fee scenario.** Before fees it loses $33,263.93; modeled maker fees are $354,891.68. This differs substantially from inspecting only the 16,219 common moneyline prints.

The benchmark retains **all 457,147 YES-taker prints** from eight certified complete calendar days, selected from 472,829 pure-NFL native prints. The 15,682 NO-taker prints are excluded consistently with the existing seller-proxy convention. There are no source-price, model-edge, leg-count, phase, ticket-size, capital or concentration filters. It is a hypothetical seller at the observed public price and size, not evidence of our RFQ execution.

YES premium totals **$13,968,262.37** and payout face quantity **$186,655,696**. Face quantity is the sum of maximum contract payouts, not customer winnings. Native settlement obligations in the observed-price counterfactual total $14,001,526.30. Every retained print has a numeric native settlement and timestamp; no outcome is inferred or filled in. The 27 fractional settlements (eight at 0.0400 and nineteen at 0.1400) remain fractional.

## Fee sensitivity

| Maker coefficient | Modeled fees | Known net P&L |
|---|---:|---:|
| 0 | $0.00 | $-33,263.93 |
| 0.0175 | $177,457.03 | $-210,720.96 |
| 0.035 | $354,891.68 | $-388,155.61 |
| 0.07 | $709,760.84 | $-743,024.77 |

These are **unverified January fee scenarios**, not certified historical receipts. The fee function is exactly the existing NFL replay convention: `kalshi_fill_fee(q, 1-YES_price, rate, action="buy", balance_precision=".0001", accumulator=0)`. Cross-venue taker fees are not relevant to this native observed-price benchmark. No cancellation-specific fee refund is inferred from settlement metadata.

## Main marginal cuts at maker coefficient 0.035

| Cut | Prints | Net P&L |
|---|---:|---:|
| structure: Contains same-game legs | 399,990 | $655,754.50 |
| structure: Distinct fixtures | 57,157 | $-1,043,910.12 |
| family: Full-game core | 101,519 | $-1,183,835.43 |
| family: Includes known player prop | 355,628 | $795,679.82 |
| phase: After schedule cutoff | 128,381 | $202,055.49 |
| phase: Pregame schedule proxy | 326,626 | $-559,488.70 |
| phase: Unknown schedule | 2,140 | $-30,722.40 |
| scope: Outside primary structural scope | 433,929 | $-69,713.15 |
| scope: Primary structural scope before source pricing | 23,218 | $-318,442.47 |
| legs: 2 | 122,659 | $-106,935.08 |
| legs: 3 | 94,551 | $-125,940.65 |
| legs: 4 | 75,770 | $8,422.17 |
| legs: 5+ | 164,167 | $-163,702.06 |
| premium: $10–50 | 115,079 | $-219,097.43 |
| premium: $50–250 | 32,605 | $-298,530.49 |
| premium: Above $250 | 6,762 | $191,842.14 |
| premium: At most $10 | 302,701 | $-62,369.83 |

These cuts overlap across dimensions. The same-game and prop-containing profits are not independent discoveries, and neither proves that a corresponding live fair-value model would capture those prices. There is substantial fixture and date concentration.

## Daily results and concentration

| Date | Prints | Net P&L at 0.035 |
|---|---:|---:|
| 2026-01-05 | 4,200 | $-32,308.89 |
| 2026-01-06 | 6,538 | $-37,754.27 |
| 2026-01-07 | 6,432 | $-100,765.61 |
| 2026-01-08 | 7,644 | $-62,510.83 |
| 2026-01-09 | 17,648 | $-275,977.71 |
| 2026-01-10 | 113,886 | $-1,846,716.03 |
| 2026-01-11 | 191,976 | $938,630.83 |
| 2026-01-12 | 108,823 | $1,029,246.90 |

January 10 loses $1.85m; January 11 and 12 recover approximately $0.94m and $1.03m. Many prints share the same playoff outcomes. Removing all prints involving native token `26JAN10LACAR` changes the total from -$388,155.61 to +$1,345,335.24; this is a retrospective concentration diagnostic, not a proposed outcome-based filter.

All 11 native fixture-token contribution/exclusion tables are in the summary. They overlap and are not additive. Two tokens refer to SF–SEA with different scheduled dates (`26JAN17SFSEA` and `26JAN18SFSEA`); this report preserves the native tokens and does not silently merge their identities. The 2,140 schedule-unknown prints involve the latter token. Review potential aliasing before treating native-token concentration as final semantic-game concentration.

The **2,140 unknown-schedule prints are explicitly unknown**, rather than mislabeled in-play from the cohort boolean. Their P&L is -$30,722.40. Actual schedule revisions were not inferred here.

Annualized Sharpe remains unavailable for this unlimited-exposure benchmark. Eight-date descriptive P&L variance is 774,942,610,208.04 USD²; these dates are not independent slate trials.

## Artifacts and verification

- `seller_ledger.jsonl.zst`: all 457,147 native source rows, unchanged original fields plus derived categories and exact Decimal economics at all four fee rates.
- `full_resolution_curves.jsonl.zst`: 396,085 unique actual trade timestamps, globally ordered; cumulative P&L/volume/fees and all fee sensitivities. No resampling or point reduction.
- `summary.json`: totals, days, all cuts, overlapping fixture contributions/exclusions, statistics, fee assumptions, native input hashes, code hashes and codec identity.
- `complete.json`: completed core artifact hashes and row counts.
- `verification.json`: independent full row/curve reconciliation passed.

**Verification passed for every row and every curve point.** All 457,147 retained rows match their original native cohorts; there are no missing or duplicate seller IDs. Independent Decimal premium/settlement/fee/NO-cash identities pass for all four scenarios, every cumulative curve point reconciles, and all 48 input hashes match. Three focused tests cover fractional settlement, unknown-schedule classification and unknown-outcome bounds.

The benchmark completed in 60.15 seconds with 50.8MiB peak RSS. No provider requests, plots, live orders or frozen pipeline edits occurred. All foreground benchmark and verification processes finished.

Reproduce into a new output directory:

```sh
.venv/bin/python scripts/nfl_native_universe_report.py \
  --root runs/nfl_playoffs_history_20260907 \
  --through 2026-01-12 \
  --out runs/NEW_NATIVE_NFL_OUTPUT

.venv/bin/python scripts/verify_nfl_native_universe.py \
  --out runs/NEW_NATIVE_NFL_OUTPUT
```

Reusable workflow: `check_cohort`/chunked hashes from the dated MLB workflow, the existing exact cash-fee helper, and the standalone verified artifact codec adapter. The old MLB report cannot consume raw NFL cohorts unchanged because its schema, fee readiness and classification keys differ; no false `pure_mlb` labels or imputed settlements were introduced.
