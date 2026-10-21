# Durable candidate-pricing worker

The research consumer now accepts an explicit evaluation time for RFQ pricing.
Source events retain their original receipt/availability timestamps. The durable
worker evaluates source freshness at actual decision time, excludes RFQs older
than two seconds (or future receipts), and separately marks computations finishing
after that deadline as untimely. No live authorization, quote sizing or risk
allocation is inferred from successful scenario pricing.

scripts/run_scenario_worker.py attaches to an existing event database, maintains a
separate output SQLite database and takes an exclusive process lock. Candidate
results and the source checkpoint commit in one transaction. Restart reconstructs
source state through the checkpoint and verifies a chained digest of the entire
processed prefix. A configuration/code identity change or modified input prefix
fails. After processing/commit failure, the in-memory worker cannot continue; it
must reconstruct from the durable checkpoint. Rebuilding currently replays the
full prefix, so mature-database restart duration still needs measurement.

Seven tests cover mode/config isolation, ordering, restart/deduplication, stale
RFQs, changed history, failure reconstruction and late completion. Complete replay
parity still holds for all47,937 RFQs after adding evaluation-time support.

A saved-input worker run consumed189,852 events and recorded all47,937 RFQs as
stale exclusions, as appropriate for historical data processed with a live clock.
It then restarted, rebuilt source state, emitted no duplicate decisions and kept
47,937 output rows. This is a restart/staleness test, not a forward performance run.
Next attach the worker during a fresh three-source capture to measure actual
queueing, pricing and persistence behavior. Persistence itself is not yet included
in the per-result completion timing, which is taken before batch commit.

Artifacts: runs/scenario_worker_saved_input_20260909;
parity receipt: runs/nfl_scenario_consumer_parity_v2_20260909/verification.json.
Implementation: src/combos/scenario_worker.py, rfq_scenario_consumer.py,
scripts/run_scenario_worker.py. Original production pricing gates remain intact.
