# Complete-date MLB universe report

Run independently of the frozen model batch:

```sh
.venv/bin/python scripts/mlb_dated_universe_report.py \
  --cohort runs/mlb_historical_20260907/dated_fee_primary/2026-07-01/cohort \
  --out runs/morning_research_20260908/universe_july1
```

Repeat `--cohort` for multiple completed dates. Each cohort must contain its completed `summary.json` and `universe_trades.jsonl.gz`; original source manifests must be readable and match their hashes. The workflow verifies contiguous complete-date source windows, census row timestamps, pure-MLB row counts, and archived per-row P&L. Identical rows are deduplicated by trade ID; conflicting duplicates and repeated cohort dates fail. SQLite stores dedup identities on disk; streaming aggregates avoid retaining the full trade frame.

The scope includes all pure-MLB YES-taker prints: every leg count, same-game structure, core/prop/other market family, and schedule phase, independently of fair-model availability. Opposite/unknown taker direction counts remain explicit. Fees come directly from dated archived rows with their verification state. Unknown settlements receive payoff bounds, including their fees. No capital filter or assumed own RFQ fills are applied.

Outputs:

- `universe.png` / `.svg`: eventual P&L at trade time, volume, unknown bounds and five categorical cuts.
- `summary.json`: overall, date, cut and overlapping-fixture aggregates; fixture-removal outcome bounds; input and script hashes; fee references and assumptions.
- `curves.jsonl.gz`: five-minute **incremental** aggregate contributions (sum cumulatively to reproduce the curve).
- `REPORT.md`: scope and accounting notes.

Observed-date dollar P&L sample variance is shown only with two or more complete dates and fully resolved outcomes. No unobserved days are inserted, no calendar-gap returns fabricated, and no Sharpe is claimed for an unlimited-exposure benchmark without a funding denominator. Fixture totals overlap and must not be added as independent contributions.

July 1 initial run: 221,498 YES-taker prints, $9,233,275.76 YES premium, $123,008,798.86 payout notional, $220,930.74 archived scenario maker fees and $1,704,234.97 net seller P&L. All outcomes known. Removing every combo involving LAD–ATH flips P&L to −$285,057.43; removing MIA–COL leaves $38,771.73. This substantially broadens the primary-model intersection but does not remove the fixture concentration concern.

Five targeted tests cover unknown bounds, all-scope retention, dedup/conflicts, source integrity, sparse-date variance, and corrupted accounting/counts. July 1 PNG was rendered and visually inspected.
