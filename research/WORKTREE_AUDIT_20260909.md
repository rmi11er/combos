# Strategy worktree audit — September 9, 2026

This audit records the state found while resuming the five-workstream research
plan. It is an evidence index, not a promotion decision.

## Verified infrastructure

- `scripts/validate_candidate_freeze.py --freeze config/candidate_freeze_shadow_20260911.json`
  passes. The freeze is valid, has nine pinned source files, and explicitly
  keeps orders and automatic promotion disabled.
- The focused execution, fill-edge, Pinnacle last-look, risk, and creator tests
  pass: 28 tests. The disk-index tests pass: 9 tests.
- `runs/mlb_longitudinal_disk_20260907/index_parity.json` records 290,244
  indexed model rows and exact parity against the three-date oracle.

## Processes verified alive

- PID 69700 is running `mlb_completion_followthrough.py`; its current child is
  processing the July 27 universe stage. The completion certificate is not yet
  terminal.
- PID 69702 is running `mlb_longitudinal_sweep.py` in simulation at roughly
  100% CPU. Its output has not yet reached a terminal result.

## Five-workstream assessment

1. **Pipeline recovery:** active. The certified batch exposes 30 eligible dates,
   but the follow-through still needs to finish and publish its terminal
   certificate.
2. **NFL three-source shadow:** integrated and fail-closed. The capture has
   source polling, freshness checks, creator evidence, last-look validation and
   fill-edge reporting, but no meaningful acceptance/fill sample yet.
3. **Source ablations:** available in
   `runs/nfl_source_weight_comparison_guarded_20260909`. The comparison shows
   694 common priced RFQs; historical Pinnacle OOS profitability remains
   unverified.
4. **Margins and risk:** MLB August held-out and NFL trace sweeps exist; the
   pooled MLB chronology is still running. Public-print results remain a
   capacity/selection diagnostic, not an execution result.
5. **Candidate freeze and promotion evidence:** the baseline is reproducible,
   but promotion still requires confirmed fill edges, markouts, settlement and
   account reconciliation, reviewed Pinnacle mappings, creator review, and an
   untouched OOS comparison.

The current evidence supports continuing with the frozen shadow baseline while
the two long-running MLB jobs finish. It does not yet support changing the
edge hurdle or risk limits based on the three-source model, because the key
fill-conditional and historical Pinnacle tests are still missing.

## Storage incident

The first two attempts at the pooled longitudinal sweep stopped before a
completion marker while the workspace approached full capacity. Their output
directories were incomplete derived artifacts: neither contained `complete.json`
and the active run had only begun its first policy. The verified three-date
streaming certificates and all raw/dated batch inputs are retained. The
incomplete directories were removed after recording this disposition so the
full streaming evaluator can be rerun without deleting research inputs.
