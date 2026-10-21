# Worker commit-failure audit

Fault injection exposed a missing stop condition around the second, diagnostic
commit. The decision/checkpoint transaction could succeed, then commit-receipt
insertion fail without marking the in-memory worker unusable. The runner already
exited on that exception, but direct reuse of the class was insufficiently guarded.
ScenarioWorker now marks itself poisoned on diagnostic-write failure as well.

SQLite-trigger tests verify both transaction boundaries:

* Decision insertion failure leaves no output row and checkpoint zero. A fresh
  worker can process the RFQ once after the injected fault is removed.
* Receipt insertion failure preserves the committed decision and checkpoint, leaves
  timing evidence absent, and prevents reuse of the failed instance. Restart emits
  no duplicate decision and retains the valid output.

Nine worker/integrated-policy tests pass. This tests SQL aborts at the write
boundaries, not power loss or every filesystem failure. Missing timing receipts
remain explicitly reportable by the live audit; they are not fabricated on restart.
No source stream or existing live-output database was modified by the tests.

Prechange source: runs/worker_commit_faults_20260909/worker_before.py.
Implementation: src/combos/scenario_worker.py; tests/test_scenario_worker.py.
