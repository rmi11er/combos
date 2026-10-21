# NFL Jan 5–11 independent ledger audit

The completed replay passes the independent accounting audit: 16 ledgers, 64 model portfolios, the same 16,219 prints for each of four models, and 204 source/input hashes. No fee double charge or PnL-sign mismatch was found. This verifies the recorded historical replay mechanics, not live fills or the January effective maker-fee rate.

Evidence: [verification JSON](../runs/morning_research_20260908/nfl_jan5_11_audit/verification.json), [bounded audit script](../runs/morning_research_20260908/nfl_jan5_11_audit/audit.py), source replay `runs/nfl_moneyline_replay_20260907/jan5_11`.

## Checks

Independently recomputed decimal fees for all four fee scenarios (0, .0175, .035, .07), including six-decimal ceiling and signed-cash alignment. For every selected print, net PnL is `quantity × (YES price − YES settlement) − maker fee`; net model edge is `quantity × (YES price − fair) − maker fee`. Accepted IDs match fill IDs. Fill PnL sums, premium, payout notional and cash cost all reconcile to summaries. A separate settlement-time heap reproduces peak cash, ending committed cash and settled PnL. Eventual PnL is attributed to trade time while cash is released only at recorded settlement.

## Primary .035 scenario: unlimited selections

Amounts below are dollars. Fixture omission drops all accepted prints touching that fixture; the range is a sensitivity diagnostic, not a confidence interval.

| Model | Jan 5–11 PnL | Fixture omission range | Without largest winning print | Jan 5–10 PnL | Prior without largest print |
|---|---:|---:|---:|---:|---:|
| Kalshi | 61,245.81 | [-3,180.74, 64,103.22] | 41,741.63 | 28,766.23 | 9,262.05 |
| Equal exchange blend | 41,225.18 | [-14,403.29, 53,016.30] | 21,721.00 | 11,356.23 | -8,147.95 |
| 75% Polymarket blend | 38,663.27 | [-19,325.20, 54,471.84] | 19,159.09 | 7,699.25 | -11,804.93 |
| Polymarket | 22,536.35 | [-26,401.58, 40,869.15] | 3,032.17 | 1,029.28 | -18,474.90 |

All four selections now remain positive without the largest winning print (34,803 contracts; $19,504.18 net), whereas only Kalshi did in the prior prefix. However, removing PHI–SF makes every model negative. More prints have improved single-print resilience without resolving fixture concentration. The prior fixture-omission ranges were Kalshi [−2,759.73, 29,459.14], equal blend [−13,951.43, 23,147.35], PM75 [−18,864.22, 23,507.82], and Polymarket [−25,526.08, 19,362.08].

## Funded selections and universe comparison

| Model | Funded PnL | Peak committed cash |
|---|---:|---:|
| Kalshi | -2.12 | 139.07 |
| Equal exchange blend | 6.74 | 118.02 |
| 75% Polymarket blend | -50.91 | 174.50 |
| Polymarket | -111.69 | 208.57 |

Selling every print in this common priced cohort loses $298,835.25 unlimited, versus $62.92 funded. The corresponding peaks are $2,465,915.48 and $227.17. This is the shared priced moneyline cohort, not the entire NFL combos universe. Funded selections use only $118–209 at peak against the $10,000 capital base; these results do not establish performance at target deployment capacity.

## Remaining limits

The historical fee scenarios are mechanically consistent but their effective January applicability remains uncertified. These are exchange-only models: Pinnacle is unavailable in this replay. The independent-product pricing and fixed exchange blends remain diagnostics, with ordinary completed-game settlement assumptions. The audit does not validate annualized Sharpe as evidence of independent returns. Fixture omissions do not rerun or reallocate a funded portfolio. No pipeline code, original ledger, plot or provider data was changed during this audit.
