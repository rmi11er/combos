# Authenticated execution-readiness observations

Nine authenticated GET requests succeeded using the session's existing Kalshi credentials. No order, quote, transfer or account-setting mutation was made. Response envelopes are retained with hashes under `runs/kalshi_execution_readiness_20260909`, with owner-only permissions and no authentication headers or API key values.

Two reads report primary available cash of **−$1,048.3917**, legacy balance −104839 cents, portfolio value zero, and only primary subaccount 0 in the subaccount-balances response. This does not match the intended $10k strategy bankroll. The user has been asked whether this is the intended account to reconcile/fund or whether another account will be used. This observation must be resolved before funding a live strategy ledger; it is not a reason to stop historical research or shadow infrastructure work.

`balance_dollars` preserves four decimals; using the legacy integer cents would discard $.0017 here. The returned non-cent balance supports investigating direct-member precision, but no explicit precision entitlement field was returned. Do not substitute the model's $10k starting cash for the observed account's available funds.

The account reports basic limits: read refill 200 tokens/s, capacity 600; write refill 100 tokens/s, capacity 100. These are token budgets, not universally equivalent requests/s. [Account limits](https://docs.kalshi.com/api-reference/account/get-account-api-limits)

The authenticated self-quote query returned zero quotes without a continuation cursor. Resting orders likewise returned zero without a cursor. Positions and fills each returned two records with a continuation cursor, so their first pages are not a complete portfolio census. No private accepted-quote example is available from this query to validate side-specific target-cost sizing. The communications identity endpoint succeeded.

Actual fill records expose count_fp, dollar prices, fee_cost, order/fill IDs, side/action, book_side/outcome_side, exchange index and subaccount number. These field shapes inform the future normalizer but do not themselves prove fee accumulator state, opening positions or account reconciliation.

`src/combos/account_cash.py` assesses a successful, timestamped balance read using fixed-point dollars where available and legacy cents only as fallback. It limits proposed initial strategy cash by both available account cash and the strategy budget, floors negative balances to zero allocation, and rejects stale reads. Two focused tests pass. Its output explicitly does not authorize ledger initialization until positions, orders, shared activity and precision evidence are reconciled.

The repeated cash assessment uses the original response receipt time and is saved as historical readiness evidence. It is not a current cash authorization. Balance endpoint semantics: [Get balance](https://docs.kalshi.com/api-reference/portfolio/get-balance).

## Later account refresh and repeatable assessment

Fresh bounded GET collection again reports available cash −$1,048.3917. Positions,
resting orders and self-quotes are each empty with completed pagination. These
reads are sequential, not an atomic account snapshot. A $10k strategy budget
therefore yields zero allocatable starting cash; no strategy ledger was funded.

`scripts/collect_account_reads.py --strategy-budget 10000` now performs the cash
assessment immediately after archiving the balance response, retaining its exact
receipt time and fixed-point dollar precision. Invalid/missing balance evidence
or an invalid budget is recorded as an assessment error without discarding the
private raw reads. Thirteen focused account-read/cash/signing tests passed, and
the integrated four-GET workflow succeeded against the account.

Evidence is stored with owner-only permissions under
runs/kalshi_execution_assessment_20260909. The previously raised question about the
intended funded trading account remains unresolved; research and shadow work can
continue independently. This assessment is not order, quote or transfer authority.
