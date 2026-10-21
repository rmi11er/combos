# Live execution startup gate

Added `combos.execution_startup_gate.assess_startup`, a read-only gate that
distinguishes the desired strategy budget from authenticated available cash.
It refuses startup when the balance is stale/nonpositive, account reads are not
atomic, pagination is incomplete, positions/orders/self-quotes exist, shared
account activity remains unresolved, or production mappings are incomplete.
The result explicitly reports maximum initial strategy cash, mutation=false and
orders_submitted=0. It never initializes `ExecutionRiskHolds` and never calls a
mutation endpoint.

Applied to the latest archived account assessment, it returns:

    ready_for_ledger_initialization: false
    strategy_budget_dollars: 10000
    maximum_initial_strategy_cash_dollars: 0.0000

Reasons are stale balance evidence, nonpositive cash, non-atomic account reads,
unresolved shared activity and zero of 454 production mappings verified. This is
consistent with the previously archived balance of -$1,048.3917. The decision is
stored at `runs/kalshi_execution_assessment_20260909/startup_gate.json`.

The gate is intentionally stricter than the historical/research risk ledger,
which may use a hypothetical capital base. A live caller must pass a fresh gate
before constructing a funded execution ledger. Twelve focused startup/account/
risk tests pass. No account or exchange state changed.
