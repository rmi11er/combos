# Integrated research quote policy and durable reservations

ResearchQuoteConsumer now composes arrival-time three-source pricing with published
creator state, captured fee/grid terms, full-RFQ sizing and canonical underlying,
combo and event capacity reservations. It accepts explicit research configuration;
run_scenario_worker.py enables it only when --policy is supplied. There remains no
quote transport or live authorization. A watch state does not automatically block;
blocked/cooldown states do. Creator decisions use only policy events consumed in
source order, and cooldown expiry uses the actual evaluation time.

Each research decision contains its quote, fee references, sizing basis, risk keys,
all binding limits and resulting committed cash. Restart reconstructs source state,
then re-evaluates recorded pricing decisions at their recorded evaluation times to
rebuild reservations. Any mismatch fails. A test verifies that a reservation held
before restart still causes the next overlapping RFQ to be rejected after restart.
Commit failures continue to poison in-memory state and require reconstruction.

Seventeen focused tests pass. Full-census replay processed47,937 RFQs and matched
all694 priced RFQs exactly against the independently audited staged outputs:
quote arithmetic, quantities, fee/cash amounts, creator status, canonical leg risks
and capacity admissions/rejections. This parity run uses one diagnostic policy:
point reference,0.3c/combo,$10k ceiling,$1k underlying/combo/event caps,1:1 native
stake conversion and all-admitted-fill/no-release assumption. These are explicitly
research settings, not selected production hyperparameters. The config is
config/research_quote_policy_20260909.json.

Forward integrated quote computation and persistence latency remain to be tested.
This capacity mode assumes every admitted quote fills; it does not estimate fills.
The alternate no-fill3s expiry mode also remains a research assumption, not authority
to release dispatched live orders. Actual execution ledger/reconciliation is separate.
Pricing payoff/unit assumptions and account funding/precision issues remain unresolved.

Artifacts: runs/integrated_quote_parity_20260909/verification.json;
prechange worker/runner: runs/integrated_quote_worker_20260909/prechange.
Workflow: scripts/check_integrated_quote_parity.py.
