# Report after frozen validation audit

Added `scripts/report_frozen_validation.py`, separate from the sealed replay
and supervisor. It requires matching completion/independent-audit summary
hashes, an exact 28-portfolio audit census and unchanged audited artifacts before
reporting. It writes all policies to CSV and funded/unlimited comparison plots
for the primary, two challengers and sell-all control, with trade-attributed
P&L, model edge, YES premium and committed cash. Payout notional is in the CSV.
Legends carry observed-date P&L variance and explicitly mark Sharpe unavailable.

The chart reader streams compressed curves, retains extrema for display, checks
chronology and reconciles final P&L/cash/premium/notional to the audited summary.
This is not an independent reconstruction of every intermediate curve point.
The report does not fit or promote any parameter.

Run only after the existing independent audit completes:

    PYTHONPATH=src .venv/bin/python scripts/report_frozen_validation.py --study runs/mlb_august_frozen_validation_20260909 --out runs/mlb_august_frozen_validation_report_20260909

Two gate tests pass (incomplete audit census and changed audited artifact).
Syntax compilation passed. Actual held-out rendering and visual inspection are
still pending the study's completion; no August P&L was inspected for this work.
The existing supervisor does not yet invoke this additional report command.

Full report rendering subsequently passed on a 28-portfolio synthetic fixture at
`runs/frozen_report_synthetic_20260909`. The final funded PNG was visually
inspected, synthetic data is explicitly labeled, and date ticks were changed to
whole days to avoid duplicate labels. Both PNG/SVG regimes and the CSV/manifest
were generated. This is renderer validation, not held-out strategy evidence.

Storage recovery archived the completed July `input.sqlite` byte-for-byte under
`runs/mlb_july_development_snapshot_20260908/input_archive_20260909` (1.673 GB
logical original, 0.307 GB archive), with restoration instructions in
`INPUT_RESTORE.md`. Six additional completed capture decision logs saved 0.503 GB
allocated space through transparent, hash-verified compression. The original
July input must be restored before further index-based July analysis. The frozen
August runner uses its separate exclusion manifest and does not need that file.

After sufficient disk headroom was restored, the existing validation supervisor
started the frozen replay as PID 61022 at 2026-09-09T11:23:45Z. Independent audit
and actual-data report remain subsequent steps; no policy parameters changed.

The comparison now includes five panels: P&L, model edge, YES premium, payout
notional and committed cash. Both volume measures appear directly on the chart;
the footer distinguishes payout face value from customer winnings. The expanded
synthetic layout was rendered and visually inspected under
`runs/frozen_report_synthetic_20260909/render_with_notional`. A third test checks
that a payout-notional endpoint mismatch blocks reporting. All three report
tests pass. Actual held-out rendering remains pending the independent audit.
