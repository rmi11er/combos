# Stateful RFQ scenario consumer: complete replay parity

The three-source research pricing logic is now encapsulated in
src/combos/rfq_scenario_consumer.py as RFQScenarioConsumer. It consumes ordered
market events, maintains exchange verification and Pinnacle snapshot state, caches
conditional payoff reviews and returns a decision for each RFQ. It has no order
transport and requires shadow mode. The original replay remains unchanged as the
comparison implementation.

scripts/benchmark_rfq_scenario_consumer.py verified exact object equality for all
47,937 RFQ decisions in the latest capture: all exclusions and all694 priced RFQs,
including every scenario, leg probability, source reference and weight. Total replay
was3.00s. Priced-scenario compute median0.271ms, p99 14.593ms, maximum34.440ms;
Pinnacle snapshot rebinding median17.666ms, maximum20.651ms over four snapshots.
The larger tail includes first-use conditional payoff enumeration, not just cached
weighted averaging. These are measurements on this machine/run, not latency SLOs.

These timings exclude input queuing, JSON/event decode, persistence, quote sizing,
creator decisions and risk allocation. They do not replace complete forward-path
measurement. The consumer still uses explicit research assumptions for exceptional
settlement, tie probability, Pinnacle native stake units and cross-game independence;
production normalization blocks remain intact. No live fair model was approved.

Next attach the consumer to a durable live worker, with explicit decision-time
freshness, restart state reconstruction, consumer checkpoints and maximum processing
lag. Log pricing computations separately from executable quote eligibility. Then
measure actual end-to-end candidate latency under sustained collection.

Verification: runs/nfl_scenario_consumer_parity_20260909/verification.json.
