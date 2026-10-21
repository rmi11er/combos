# Settlement netting and account reconciliation

A two-row authenticated settlement read and a complete one-page fill read for the
first market were archived privately in runs/account_settlement_probe_20260909.
The first settlement reports YES1100/NO1.60, NO result and zero revenue. Its two
buy fills exactly reconcile quantities, cost bases and total fees of $1.7346.
Kalshi documents that only net positions settle. An inferred $1.60 earlier pair
credit reconciles gross terminal payoff to zero remaining settlement revenue.
This inference is not an observed balance entry and does not authorize cash release.
The rows are existing account activity, not strategy executions.

Economic P&L before balance adjustments is -$991.6066; using settlement revenue
alone minus both purchase costs and fees would incorrectly produce -$993.2066.
No historical seller-only model P&L was changed by this account-specific finding.

New settlement_accounting.py checks buy-only fill identities, deduplication, exact
counts/costs/fees, binary/scalar payout consistency, expected net payout and reported
revenue. It exposes scalar rounding differences without silently crediting them.
Sells and unmatched quantities/costs reject pending a general inventory ledger.
A reusable archived review script requires explicit subaccount/ticker scope and
complete unbounded fill pagination; missing pages and time-filtered histories reject.
API retention cutoffs and position transfers remain separate completeness concerns.

71 focused tests passed across settlement math/review, terminal orders, risk holds,
balances, fills and authenticated reads. Actual private sample review also passed
its cost/fee/net-revenue identities. There is still no settlement-driven capital
release or live order submission. Next reconcile netting and posted balance changes,
and connect strategy ownership and terminal-order evidence to hold transitions.

Sources checked September9:
https://docs.kalshi.com/api-reference/portfolio/get-settlements
https://docs.kalshi.com/openapi.yaml
https://docs.kalshi.com/getting_started/market_settlement

The collection and validation supervisors and collector process were confirmed live
with ps; the four pending August dates remain22,24,28,30 at the latest status read.
