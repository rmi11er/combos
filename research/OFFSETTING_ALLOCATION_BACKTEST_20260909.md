# MLB/NFL small-ticket and offsetting allocation replay

Date: 2026-09-09  
Status: exploratory historical replay; not a live limit recommendation

## Question

How many historical edge-qualified public prints could be admitted with a $10,000 capital pool when tickets are capped at smaller liabilities, and how much additional capacity appears when distinct full-game moneyline exposure is netted by fixture and team side?

## Inputs and method

- 6,266 Kalshi opportunity rows from the saved NFL replay (Jan 5–18) and 11 saved MLB dates (Jul 1–29).
- Rows were kept only for `model=kalshi`, `quote_allowed=true`, and recorded edge after maker fee of at least 0.30 percentage points.
- Chronological replay. A ticket releases its gross collateral only at its recorded settlement time.
- Capital: $10,000. Canonical caps: $100 per contract bucket, $100 per combo bucket, $250 per fixture bucket.
- Public prints are treated as hypothetical fills. There is no queue, fill elasticity, adverse selection, or latency model.
- Smaller tickets scale quantity, collateral, fee, and edge linearly. Exchange fee rounding at resized quantities is not reconstructed.
- Cash remains gross collateral. Offset credit is applied only to internal contract/fixture risk budgets for exact, distinct-fixture full-game moneyline tickets. MLB spreads, totals, same-game structures, and unknown structures remain gross-risk-only.

## Results by sport

Peak committed cash is the largest gross collateral outstanding. “Accepted edge” is the recorded edge before outcomes; “retrospective P&L” uses the saved settlement labels and is not allowed to fund decisions.

| Sport | Policy | Accepted | Peak committed | Peak offset credit | Accepted offset-eligible | Accepted edge | Retrospective P&L | Avg ticket liability |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| NFL | full gross | 21 | $139 | $0 | 21 (100%) | $1.52 | -$29.40 | $12.45 |
| NFL | $50 gross | 22 | $189 | $0 | 22 (100%) | $3.03 | -$35.66 | $14.20 |
| NFL | $25 gross | 22 | $176 | $0 | 22 (100%) | $2.83 | $3.47 | $13.77 |
| NFL | $10 gross | 42 | $161 | $0 | 42 (100%) | $2.54 | $28.28 | $8.39 |
| MLB | full gross | 1,189 | $1,342 | $0 | 169 (14%) | $375.83 | $941.33 | $12.04 |
| MLB | $50 gross | 1,069 | $1,420 | $0 | 143 (13%) | $435.99 | $1,057.21 | $15.73 |
| MLB | $25 gross | 1,317 | $1,386 | $0 | 193 (15%) | $401.33 | $1,383.51 | $12.36 |
| MLB | $10 gross | 1,929 | $1,175 | $0 | 323 (17%) | $321.47 | $1,210.37 | $6.76 |
| MLB | $50 moneyline offset | 1,506 | $2,540 | $273 | 260 (17%) | $610.53 | $2,383.22 | $17.78 |
| MLB | $25 moneyline offset | 1,900 | $2,497 | $247 | 340 (18%) | $537.03 | $2,255.23 | $13.24 |
| MLB | $10 moneyline offset | 2,491 | $1,934 | $175 | 508 (20%) | $375.76 | $1,563.88 | $7.10 |

Aggregate results are in [`analysis/offsetting_allocation_v1/results.json`](../analysis/offsetting_allocation_v1/results.json). The executable is [`analysis/offsetting_allocation_backtest.py`](../analysis/offsetting_allocation_backtest.py).

The MLB settlement-based equity curves are in [`mlb_equity_curves.png`](../analysis/offsetting_allocation_v1/mlb_equity_curves.png), with point-level data in [`mlb_equity_curves.csv`](../analysis/offsetting_allocation_v1/mlb_equity_curves.csv).

## Learnings

1. **The current caps, rather than $10,000 of cash, are the binding constraint.** Even the largest observed gross peak is only about $1.4k. Smaller-ticket policies admit more distinct tickets, but the extra count is not equivalent to more independent risk because many tickets share fixture and combo buckets.
2. **Offsets are valuable in this sample only for MLB.** The MLB $50 offset policy admits 1,506 tickets versus 1,069 under the same gross policy, with a $273 peak internal risk credit. The $25 and $10 policies show the same direction. NFL admits are unchanged and receive zero credit: the saved NFL slice has no useful simultaneous opposing moneyline inventory under this replay.
3. **A $10 cap maximizes ticket count, not observed edge dollars.** In MLB, $50 offset has the largest recorded edge and retrospective P&L in this particular public-print sample, while $10 admits the most tickets and lowers average ticket liability. This is an outcome of the historical opportunity stream, not evidence that $50 is optimal live.
4. **Most MLB opportunities are not safely offsettable with moneyline pairs.** Only roughly 13–20% of accepted MLB tickets qualify for exact moneyline offset credit. The remainder include spreads, totals, same-game combinations, or structures whose selected team cannot be recovered without ambiguity.
5. **No one-game conditional isolation was assumed.** A ticket can touch several fixtures; the replay limits canonical fixture buckets but does not claim statistical independence. Offset credit reduces opposite-side exposure within a fixture; it does not erase residual correlation, common information, parlay tail risk, or execution/toxicity risk.

## Claims tested

| Claim | Result | Evidence / qualification |
|---|---|---|
| Smaller ticket caps deploy more capital across more bets | **Accepted mechanically** | $10 gross admits 1,929 MLB tickets vs 1,069 at $50; peak gross collateral is still only $1,175–$1,420 under these caps. |
| Opposing moneyline positions can increase capacity | **Accepted for MLB, refuted for this NFL slice** | MLB offset policies admit 1,506/1,900/2,491 tickets at $50/$25/$10; NFL offset and gross counts are identical. |
| Offsets reduce the cash needed to settle tickets | **Untested / not implemented** | Cash remains gross collateral by design; only risk-budget usage is netted. A clearing/margin credit requires an approved economic convention. |
| A single ticket cap identifies the optimal live size | **Refuted** | Results change with opportunity sequence, caps, fills, fees, and settlement clustering; no fill elasticity or forward sample is modeled. |
| The saved sample supports NFL sizing conclusions | **Refuted** | Only 21–42 accepted NFL tickets per policy in this input; use as a pipeline check, not an NFL sizing estimate. |

## Deployment implications

The implementation supports a conservative next step: retain gross cash collateral, add a bounded moneyline offset credit only after exact fixture/team matching, and keep spread/total/same-game structures on gross limits. Before changing live limits, rerun with actual fill/queue assumptions, creator blacklist state, maker-fee rounding, and a forward period. A useful next experiment is a grid over ticket cap, fixture cap, and a fractional offset credit (0%, 25%, 50%, 75%, 100%) with fill throttles; that will separate capacity from simply assuming every public print fills.
