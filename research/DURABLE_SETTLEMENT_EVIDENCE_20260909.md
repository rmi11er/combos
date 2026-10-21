# Durable settlement reconciliation

Added `SettlementEvidence` and optional `--journal` support to
`scripts/reconcile_account_settlement.py`. The CLI validates archived private
settlement and complete ticker/subaccount-filtered fill pagination before
persisting the economic assessment and its exact inputs/source references.
Evidence is content-addressed and append-only: repeated inputs deduplicate,
revisions retain earlier assessments, and enclosing transaction rollback removes
the associated insertion. No balance or hold is changed.

Fifteen settlement accounting/storage tests pass. The archived real account
sample was also recorded at
`runs/settlement_evidence_store_20260909/reconciliation.json` and its sibling
SQLite database. Two unique fills reconcile to zero final settlement revenue
with an inferred $1.60 earlier complementary-position credit. Economic P&L is
-$991.6066 before account adjustments; using only final settlement revenue
would understate it by $1.60. This is an account evidence sample, not strategy
performance. Earlier credit remains inferred rather than an observed cash flow.

The full filled-position release path remains incomplete: strategy ownership,
complete account activity/no transfers, earlier netting credits, and settlement
rounding/balance reconciliation still need evidence. These records support that
path but cannot authorize release by themselves.
