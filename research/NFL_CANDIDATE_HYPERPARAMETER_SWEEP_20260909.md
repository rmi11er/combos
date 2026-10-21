# NFL candidate edge/risk sweep

The workflow `scripts/sweep_nfl_quote_hyperparameters.py` replayed the
September 9 trace against the 154-mapping initial candidate runtime. It tested
edge floors of 0.1¢, 0.3¢ and 0.5¢ per combo contract and equal per-contract,
per-combo and per-fixture caps of $250, $500 and $1,000.

All nine policies saw the same 17 candidate-scope RFQs reach complete pricing.
The results were:

| Edge | Cap | Reserved | Risk rejected | Peak reserved |
|---:|---:|---:|---:|---:|
| 0.1¢ | $250 | 11 | 6 | $372.79 |
| 0.1¢ | $500 | 11 | 6 | $637.64 |
| 0.1¢ | $1,000 | 17 | 0 | $1,776.45 |
| 0.3¢ | $250 | 11 | 6 | $369.26 |
| 0.3¢ | $500 | 11 | 6 | $623.35 |
| 0.3¢ | $1,000 | 17 | 0 | $1,750.60 |
| 0.5¢ | $250 | 11 | 6 | $365.83 |
| 0.5¢ | $500 | 12 | 5 | $643.95 |
| 0.5¢ | $1,000 | 17 | 0 | $1,726.01 |

The apparent increase in admission at a higher edge is mechanical: a larger
edge charge generally reduces the quote quantity and therefore can fit under a
fixed cash/risk cap. It is not evidence that customers would accept the wider
quote or that the strategy earns more.

For the initial shadow policy, retain the 0.3¢ floor and $500 limits. The
$1,000 case should remain a controlled ablation until a larger RFQ census and
actual acceptance/fill markouts show that the added exposure is justified. The
experiment is not a live-policy change and has no settlement P&L.

Artifact: `runs/nfl_candidate_hyperparam_sweep_20260909_v3/summary.json`.
