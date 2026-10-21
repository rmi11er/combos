# Spread compensation and calibration research workflow

Run the reusable, configuration-driven workflow:

```sh
.venv/bin/python scripts/spread_calibration_study.py \
  --config config/spread_calibration_study.json \
  --out runs/spread_calibration_20260907
```

The initial completed study and its methods are in [REPORT.md](../runs/spread_calibration_20260907/REPORT.md). Plots decompose observed seller net P&L into price-minus-fair compensation after maker fees and fair-minus-settlement residuals. All three share the same known-outcome observations and payout weights. Raw and fee-expanded spread variants preserve all covered prints without strategy filters. Each source model has available-coverage and common-model-coverage views.

The workflow writes PNG/SVG figures, results.json with bins/full coefficient vectors, regressions.csv with slopes, a readable report, and a completion manifest with hashes. Its quantity-weighted regressions include spread alone and spread with traded-price and categorical-leg-count controls. Leave-one-fixture-out refits remove every affected combo to measure influence. Their ranges are not confidence intervals; no IID standard errors or p-values are emitted. Algebraic checks enforce the P&L decomposition in rows, bins and regression coefficients. Rank deficiency and missing outcomes are explicit.

For additional historical datasets, add named opportunity/feature file pairs to the configuration. Paths can be absolute or repository-relative. These features are produced by the paired-moneyline acquisition/analysis step; this workflow neither collects history nor changes the running frozen batches. It is ready to rerun when new feature files are available, but is not an automatic watcher. For a joint longer-window regression, supply a deduplicated combined replay/features pair rather than treating separate daily coefficients as one regression.

Keep sport/model definitions and held-out windows explicit. The initial inputs are CFB August 31–September 6 (partial tape outside Saturday) and MLB September 5. Fixed coefficient specifications are diagnostic, not learned production pricing. Price conditioning may introduce mechanical/selection associations, and settlement residuals do not by themselves prove customer toxicity. Wider-market compensation, probability errors, outcome concentration and subsequent markouts need separate interpretation.

Validation:

```sh
.venv/bin/python -m pytest tests/test_spread_calibration_study.py tests/test_spread_profitability.py -q
```
