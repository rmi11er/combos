# NFL January 5–18 completion handoff

The final comparison requires all 14 January 5–18 cohort dates and 336 hourly tape partitions. A live process or partial replay is not completion. Preserve the resumed collector budget; do not restart merely because observation times out.

Before starting the final replay, verify collector terminal success, every required day's complete status/exit code/output hashes, and each cohort's 24 contiguous hourly source manifests. The current moneyline script validates hashes, census and contiguity, but deliberately accepts a completed prefix: the operator must separately require the exact 14 dates. Preserve existing January 5–11/12 results and use fresh output directories.

Run the broad native universe first, then paired moneyline selection. Both commands are offline and use the existing fee scenarios; no Pinnacle history is synthesized:

```sh
.venv/bin/python scripts/nfl_native_universe_report.py --root runs/nfl_playoffs_history_20260907 --through 2026-01-18 --out runs/nfl_native_universe_20260908_jan5_18
.venv/bin/python scripts/nfl_moneyline_replay.py --root runs/nfl_playoffs_history_20260907 --out runs/nfl_moneyline_replay_20260907/jan5_18
```

Both commands completed successfully on September 8. Exact 14-date/336-partition certification is retained in `runs/morning_research_20260908/nfl_full_cohort_completion_check.json`; the paired and native independent audit reports retain outcome, fee and artifact verification. The commands remain a reproducibility record, not a reason to rerun completed work. Full-window paired plots have also been rendered and visually checked. Capital-hours, full-liquidation sensitivity and paired calibration reviews are now complete and integrated in the morning brief/report. Cross-sport comparison still awaits full MLB development and held-out validation.

Afterward, independently reconcile native seller direction, quantity, price, fractional settlement and once-only fees. Review the SF–SEA date alias as a separately labeled semantic sensitivity; do not silently modify pricing history or eligibility. Reconcile selected/rejected and broad/common coverage, all four fee scenarios and funded/unlimited results. Inspect fixture omissions, largest-print influence and missing-source timing; January 12 previously added no common prints because required PM markets were created later.

Generate the existing full-resolution native and paired-model plots, inspect their rendering, and retain hashes. Use actual settlement for capital availability and eventual P&L attributed to trade time. Report fee assumptions, premium versus face notional, open positions and unknown outcomes explicitly. Add capital-hours using the reusable workflow after cash/fill reconciliation. Daily statistics remain dependent on a small number of playoff games.

Compare the final NFL evidence with MLB development and later held-out results without treating noncontemporaneous windows as proof of weekday allocation. Keep Wednesday collection readiness, healthy candidate-pricing readiness and live execution readiness separate. Final historical profitability cannot certify quote acceptance, reviewed payoff mappings, current depth or the missing execution adapter.
