# July 11 selected-ledger audit

All eight portfolios pass native price/quantity/payoff/fee joins, admission hurdle, selected/rejected reconciliation, fills and funded risk checks. Baseline is 0.3 cents per combo contract after fees; printed prices and full ticket quantities are retained.

| Model | Unlimited net | Modeled compensation | Funded net | Worst single-fixture omission, unlimited |
|---|---:|---:|---:|---:|
| exchange_blend_equal | $5,594.92 | $2,175.16 | $82.28 | $-8,938.69 |
| exchange_blend_pm75 | $14,091.42 | $2,749.90 | $105.77 | $-9,216.54 |
| kalshi | $-2,899.08 | $1,787.42 | $10.95 | $-11,540.94 |
| polymarket | $13,250.34 | $4,148.69 | $-76.22 | $-29,090.29 |

Fixture omissions are overlapping influence diagnostics, not confidence intervals. Funded daily accounts cannot be added into a continuous portfolio. Maker fee applicability remains an unverified scenario; public prints are hypothetical fills.

[Full audit evidence](../runs/morning_research_20260908/july11_selected_audit/verification.json). Root reverified all source and audit-script hashes.
