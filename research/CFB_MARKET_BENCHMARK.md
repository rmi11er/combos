# Full available CFB seller benchmark — September 7, 2026

Taking the opposite side of **every retained CFB YES-taker print** produces **−$3,166,689.75 of known net P&L**. The loss is broader than our model-selected trades. However, **8,706 prints remain unresolved with enough premium to reverse the final total**; this cannot establish that every seller or the industry lost money.

The benchmark includes all leg counts, full games, periods, team totals, same-game combinations, and started games. It has no fair model, entry edge threshold, ticket cap, or capital/risk limits. There were **335,947 pure-CFB prints**, split into **298,747 YES-taker** and **37,200 NO-taker** prints. We benchmark the YES-taker seller side for consistency with our strategy. All observed leg families are nonplayer families; no player-prop restriction was applied.

| Measure | Full available YES-taker cohort |
|---|---:|
| YES premium | $26,442,476.55 |
| Payout notional | $192,892,121.43 |
| Prints with known official outcomes | 290,041 |
| Known gross seller P&L | −$2,868,493.82 |
| Maker fees on known outcomes | $298,195.94 |
| Known net seller P&L | −$3,166,689.75 |
| Unresolved prints | 8,706 |
| Unresolved YES premium | $9,697,107.28 |
| Unresolved payout notional | $14,892,236.82 |
| Possible eventual total net P&L | −$8,377,906.35 to +$6,514,330.47 |

The final interval is a mechanical payout bound, not a forecast or confidence interval. Unknown outcomes remain explicitly unknown; they are not inferred from constituent legs. Pending outcomes are heavily concentrated in two-leg and period/in-play volume. Distinct public trade IDs can repeat the same market, price and quantity; the export preserves them rather than silently deduplicating economic terms.

Among known outcomes, full-game-only combos contributed −$2,491,637.70; period extensions −$524,416.45; team-total extensions −$132,452.18; and combined period/team-total extensions −$18,183.42. These subsets have different unresolved exposure. Pregame known P&L was −$1,546,953.75, started-game P&L −$1,613,418.08, and unknown-start P&L −$6,317.92. Pregame labels use verified cached schedules; schedule revisions are not reconstructed.

## Interpretation of the curve

`curves.csv` reports $10,000 plus known eventual net P&L attributed to the trade time. This is an **unlimited seller benchmark**, not a funded strategy equity curve, spendable balance, or industry account statement. It assumes we could replace every observed counterparty at the printed size and price. It does not include seller hedges, other positions, rebates, or the opposite-direction prints. The $10,000 is only a reporting origin.

Saturday is a full public-print census. Other weekdays contain the saved sampled intervals only, at **weight one**. No 60× volume expansion enters executions or P&L. Most retained prints are Saturday prints; the continuous chart does not imply complete weekday portfolio observation. Each 30-minute curve point is the **right edge** of its observation bin, and the last point is September 7 at 00:00 America/Chicago.

## Outcome refresh and validation

All 214,074 traded CFB combo definitions were found in existing native metadata, with zero missing or unreviewed fee exclusions in the YES benchmark. The earlier eligible-cohort settlement refresh was reused. We then requested only unresolved YES-traded combo metadata: **8,612 tickers, 87 batches, 88 public GET attempts including one retry, no remaining request failures**. Original metadata and the pre-refresh benchmark are preserved. No historical prices changed.

The newly obtained settlements intersect **zero** still-unresolved rows in `replay_settlement_refreshed/opportunities.json`; the model comparison requires no additional outcome rewrite. Validation of all 298,747 exported rows found no duplicate trade IDs, timestamp-order errors, P&L mismatches, or cumulative-total/bin-timestamp discrepancies.

## Reusable outputs

Run `.venv/bin/python scripts/cfb_market_benchmark.py` for a cached rebuild, or add `--refresh-outcomes --max-requests 110` for a bounded public settlement update. Outputs are in `runs/cfb_performance_audit_20260907/market_benchmark/`:

- `per_trade.csv.gz`: normalized trade terms, fee, official outcome/time, P&L, legs, fixture identities, scope, phase, and source provenance.
- `curves.csv`: 336 half-hour cumulative P&L, premium, payout-notional, and unresolved-count points.
- `breakdowns.csv`: day, leg count, phase, and market-family subtotals.
- `summary.json`, `manifest.json`, and `outcome_refresh/`: coverage, hashes and preserved native responses.
- `unresolved_diagnostics.json`: exact final-outcome bounds, concentration, and validation results; `replay_outcome_updates.json`: intersection check against frozen priced inputs.
- `before_new_outcome_refresh/`: the prior benchmark, which had −$2,722,476.71 known net P&L and 11,924 unresolved prints.

`audit_benchmark.py` in the output directory independently reconciles the export and checks intersections. Maker fees and trade-side conventions are documented in [the fee accounting audit](CFB_FEE_ACCOUNTING_AUDIT.md).
