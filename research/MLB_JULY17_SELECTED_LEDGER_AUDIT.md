# July 17 selected-ledger audit

All eight portfolios pass native price/quantity/payoff/fee joins, admission hurdle, selected/rejected reconciliation, fills and funded risk checks. Baseline is 0.3 cents per combo contract after fees; printed prices and full ticket quantities are retained.

| Model | Unlimited net | Modeled compensation | Funded net | Worst single-fixture omission, unlimited |
|---|---:|---:|---:|---:|
| exchange_blend_equal | $2,490.67 | $246.55 | $61.11 | $644.61 |
| exchange_blend_pm75 | $1,100.75 | $338.15 | $8.36 | $-854.43 |
| kalshi | $711.26 | $200.14 | $69.44 | $-1,092.41 |
| polymarket | $-16,068.02 | $1,033.26 | $153.60 | $-21,113.35 |

Fixture omissions are overlapping influence diagnostics, not confidence intervals. Funded daily accounts cannot be added into a continuous portfolio. Maker fee applicability remains an unverified scenario; public prints are hypothetical fills.

[Full audit evidence](../runs/morning_research_20260908/july17_selected_audit/verification.json). Root reverified all source and audit-script hashes.
