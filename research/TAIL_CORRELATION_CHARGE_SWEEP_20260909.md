# Tail-only correlation charge sweep

Policy held fixed: Kalshi model, 0.30¢ edge after fee, `$500/$500/$1,000` limits, `$250` ticket cap, exact moneyline offset, $10,000 capital. Only the correlation treatment varies.

| MLB treatment | Reserve threshold | Eligible | Accepted | Mean P&L / eligible row | Funded P&L | Funded max drawdown |
|---|---:|---:|---:|---:|---:|---:|
| No correlation charge | none | 4,853 | 2,127 | 44.08 | $9,883 | -$1,671 |
| Reject largest 5% reserve | 22.26% | 4,480 | 2,079 | 42.96 | $10,871 | -$1,834 |
| Reject largest 2% reserve | 23.14% | 4,643 | 2,108 | 45.93 | $11,338 | -$1,834 |
| Reject largest 1% reserve | 23.91% | 4,765 | 2,116 | 44.67 | **$11,560** | -$1,671 |
| Reject largest 0.5% reserve | 24.50% | 4,838 | 2,104 | **46.22** | $10,926 | -$1,671 |

Absolute reserve cutoffs of 0.5–2% are too aggressive for this model: most two-to-four-leg rows exceed them. The meaningful interpretation is percentile-based: rejecting only the top 1–2% of reserve values modestly improves funded P&L in this sample without materially changing accepted volume. That is encouraging as a tail-risk screen, but the improvement is small relative to selection uncertainty.

The result does not support charging the full stressed reserve on every combo. A simple policy candidate is **reject the top 1% of correlation-reserve values, leave typical combos at the normal 0.30¢ hurdle, and log a correlation surcharge diagnostic**. Validate this on additional held-out slates before applying it to live shadow admission.

Full machine-readable results are in [`tail_correlation_charge_sweep.json`](../analysis/offsetting_allocation_v1/tail_correlation_charge_sweep.json) and [`tail_correlation_charge_sweep.csv`](../analysis/offsetting_allocation_v1/tail_correlation_charge_sweep.csv). Executable: [`sweep_tail_correlation_charge.py`](../analysis/sweep_tail_correlation_charge.py).
