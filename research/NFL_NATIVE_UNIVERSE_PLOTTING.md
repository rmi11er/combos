# Native NFL benchmark plots

Reusable offline workflow:

```sh
.venv/bin/python scripts/plot_nfl_native_universe.py \
  --run runs/nfl_native_universe_20260908_jan5_12 \
  --out runs/nfl_native_universe_20260908_jan5_12/plots
```

The output directory must be new. Inputs are the completed benchmark's summary, completion receipt and full-resolution compressed curve; `replay_artifact_io.text_reader` validates the codec stream. No prices, fees, outcomes or selections are recalculated. All 396,085 curve timestamps are retained, with a zero starting point. Daily sample variance uses the eight certified Chicago dates, with ddof=1. Sharpe is explicitly unavailable for unlimited exposure and a small number of shared fixtures.

[PNG](../runs/nfl_native_universe_20260908_jan5_12/plots/native_universe.png) · [SVG](../runs/nfl_native_universe_20260908_jan5_12/plots/native_universe.svg) · [Verification](../runs/nfl_native_universe_20260908_jan5_12/plots/verification.json)

All four exact-decimal P&L, premium, face, and fee endpoints match the benchmark summary, as do final print counts and every daily P&L increment. Input/source/output hashes are recorded. Visual inspection confirmed legible legends, dates, captions and both volume series without clipping. The chart shows a large drawdown preceding recovery, with all four fee scenarios ending negative. Payout face is not customer winnings; these are unrestricted public-print seller counterfactuals, not executed RFQ returns.
