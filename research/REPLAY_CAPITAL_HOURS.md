# Replay capital-hours

The reusable `scripts/replay_capital_hours.py` integrates the post-event committed-cash curve over actual elapsed hours, including overnight and days with no new fills. It independently reconciles that integral against each fill’s NO purchase cost plus maker fee, held from execution until actual settlement or the reporting endpoint. Eventual P&L attribution does not release capital.

Three focused tests cover settlement timing, incomplete cycles, and reconciliation failure. All 16 NFL portfolios through January 12 reconcile. This analysis uses the existing unverified 0.035 maker-fee scenario and public-print participation assumption.

| Regime / policy | Model | Dollar-hours committed | Average occupied cash | Net P&L / 1,000 dollar-hours |
|---|---|---:|---:|---:|
| funded_selection | exchange_blend_equal | 12,435.99 | $64.77 | $0.542 |
| funded_selection | exchange_blend_pm75 | 16,672.13 | $86.83 | $-3.054 |
| funded_selection | kalshi | 17,072.93 | $88.92 | $-0.124 |
| funded_selection | polymarket | 21,746.73 | $113.26 | $-5.136 |
| funded_sell_all | kalshi | 32,486.73 | $169.20 | $-1.937 |
| unlimited_selection | exchange_blend_equal | 5,479,315.50 | $28,538.10 | $7.524 |
| unlimited_selection | exchange_blend_pm75 | 6,416,467.73 | $33,419.10 | $6.026 |
| unlimited_selection | kalshi | 5,983,940.58 | $31,166.36 | $10.235 |
| unlimited_selection | polymarket | 7,784,750.14 | $40,545.57 | $2.895 |
| unlimited_sell_all | kalshi | 87,595,020.93 | $456,224.07 | $-3.412 |

The ratio is descriptive occupied-cash efficiency, not annualized return. It is withheld when positions remain open or outcomes unresolved. Unlimited portfolios need far more than $10k; their ratios do not establish scalable funded performance. The four sell-all model rows are identical and displayed once.

The funded selected portfolios use only approximately $65–$113 on average over this eight-day window, consistent with the previously identified structural exposure ceiling. These January NFL measurements cannot rank MLB versus NFL today; apply the same calculation to the complete MLB continuous replay, then examine live competing demand.

Reproduce with:

```sh
.venv/bin/python scripts/replay_capital_hours.py \
  --ledger runs/nfl_moneyline_replay_20260907/jan5_12/fee0.035_funded_selection.json.gz \
  --out runs/NEW_CAPITAL_HOURS.json
```
