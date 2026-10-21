# Durable fill ingestion

`src/combos/execution_fills.py` adds account fill evidence to the existing SQLite
execution journal. Fill identity includes exchange index. Repeated observations
do not add quantity or fees again; a conflicting identity/economic payload rolls
back the entire incoming page. Raw observations and source references are retained.

The normalizer uses actual `count_fp`, complementary YES/NO prices, action/side,
maker/taker flag and reported `fee_cost`. Both buy/sell and YES/NO directions have
explicit tests. It does not substitute the research fee coefficient for a reported
fee. Principal and fee arithmetic remains Decimal without cent rounding.

Trade cash flow before balance adjustments is signed principal minus fee. This is
not an account balance delta: collateral netting, balance rounding, rebates and
settlements still require reconciliation. Order totals are explicitly incomplete;
fill ingestion does not establish strategy ownership or release capital. A verified
quote-to-order binding remains necessary before applying evidence to a risk hold.

45 tests passed across fills, journal, holds, quote reconciliation and liability.
The 13 fill tests cover restart deduplication, overlapping pages, atomic rejection,
four trading directions and malformed economics. Replayed the two previously
saved authenticated fills from `runs/kalshi_execution_readiness_20260909/fills.json`:
two inserted initially, zero inserted after reopening and replaying. No additional
provider request occurred. Private verification and database are retained under
`runs/kalshi_fill_evidence_20260909`.

The original two-row response was paginated and does not establish historical fill
completeness. API provenance is supplied by the authenticated collector; an
arbitrary envelope supplied by a caller is not authenticated merely because it has
the expected fields. Source schema: [Kalshi Get Fills](https://docs.kalshi.com/api-reference/portfolio/get-fills).

Next: persist verified quote/order ownership, fetch bounded overlapping fill
windows, compare aggregate fills with terminal order quantities, then reconcile
account cash and outstanding holds without releasing uncertain exposure.
