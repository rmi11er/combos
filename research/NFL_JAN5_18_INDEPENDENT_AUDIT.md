# Full January 5–18 NFL paired replay audit

All 16 fee/funding/selection ledgers pass the independent accounting checks: **64 model portfolios, the same 23,809 prints across four models, and 246 source/input hashes**. Native cohort quantities, prices, settlement values and timestamps are independently matched to the replay. No fee double charge, payoff-sign discrepancy or selected/rejected accounting gap was found.

Evidence: [verification JSON](../runs/morning_research_20260908/nfl_jan5_18_audit/verification.json), [audit script](../runs/morning_research_20260908/nfl_jan5_18_audit/audit.py). Source replay: `runs/nfl_moneyline_replay_20260907/jan5_18` (14 completed Chicago dates).

## Checks performed

All four fee scenarios (0/.0175/.035/.07) independently reproduce the quadratic fee, six-decimal ceiling and signed-cash alignment using Decimal arithmetic. Every fee is deducted once in `quantity × (YES price − native settlement) − fee`; model edge is `quantity × (YES price − fair) − fee`. Native input hashes and current source hashes match retained evidence.

For every ledger/model, accepted decision IDs and counts match fills; eventual fill P&L and fees reconcile, and selected plus rejected P&L equals the entire common-cohort P&L. Every selection threshold is exactly quantity×$0.003 **per combo contract**, not per leg, and every accepted print clears it. Premium, payout notional and cash cost reconcile. A separately reconstructed actual-settlement heap matches peak cash, ending committed cash and settled P&L at window end. Retrospective P&L attribution does not release capital early.

## Primary .035 fee scenario

Unlimited selections, dollars:

| Model | Selected P&L | Rejected P&L | Fixture-omission range | Without largest winning print |
|---|---:|---:|---:|---:|
| Kalshi | 62,749.36 | −363,039.69 | [−1,677.19,65,606.77] | 43,245.18 |
| Equal exchange blend | 46,846.83 | −347,137.15 | [−8,781.65,58,637.94] | 27,342.65 |
| PM75 blend | 48,835.59 | −349,125.92 | [−9,152.88,64,644.17] | 29,331.41 |
| Polymarket | 43,529.08 | −343,819.40 | [−5,408.86,61,861.88] | 24,024.90 |

The full shared priced cohort loses **$300,290.32** selling all 23,809 YES prints. Unlimited selections improve on Jan5–11 ($61,245.81/$41,225.18/$38,663.27/$22,536.35 respectively), especially PM-heavy selections. Nevertheless, dropping every accepted combo involving **PHI–SF** makes all four models negative. All remain positive without the largest $19,504.18 winning print, so single-print robustness exceeds fixture robustness. Omission ranges remove trades without reallocation; they are influence diagnostics, not confidence intervals.

| Model | Funded selected prints | Funded P&L | Peak committed cash |
|---|---:|---:|---:|
| Kalshi | 21 | −29.40 | 139.07 |
| Equal blend | 23 | +37.38 | 118.02 |
| PM75 | 20 | −26.73 | 174.50 |
| Polymarket | 43 | −73.66 | 208.57 |

Funded sell-all has 32 fills, −$38.32 P&L and $227.17 peak cash. Unlimited sell-all peak cash is $2,465,915.48; selected unlimited peaks range $202,764–253,790. Current funded limits therefore still prevent meaningful use of the $10k starting base. Favorable unlimited selection cannot be translated directly into a $10k-capital return.

## Interpretation limits

This is the matched pregame, distinct-fixture moneyline cohort, not the entire native NFL combos universe. Pinnacle remains absent. January maker-fee effective dates remain unverified scenarios even though implemented mechanics reconcile. Public traded prices/sizes are counterfactual execution proxies, not observed fills of our RFQs. Shared fixtures sharply reduce independence; no annualized Sharpe inference was validated. The accounting audit does not independently reconstruct source fair values or certify exceptional cross-venue payoff parity. Native outcomes were matched exactly rather than inferred. No provider calls, frozen source edits or August outcomes were involved.
