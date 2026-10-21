# Morning brief — September 8, 2026

Updated September 8, evening checkpoint. **Interim: 15 of 31 MLB dates fully processed, plus July 13 collected but unpriced. All 31 raw dates are collected.** July27 processing is active. August outcomes remain unread; the complete January 5–18 NFL study is audited.

Latest: July25 broad seller net−$2.737m; common priced sell-all−$895,680. Unlimited K/PM selections earn+$5,048/+$26,400, while fixed equal/PM75blends lose$6,097/$13,500; funded variants all lose. Lower entry hurdles improve this day's blend results, while larger risk caps at0.3c generally worsen results. See [selected audit](MLB_JULY25_SELECTED_LEDGER_AUDIT.md), [margin/risk review](MLB_JULY25_ENTRY_RISK_REVIEW.md), and [spread decomposition](MLB_JULY25_SPREAD_REVIEW.md). Independent point reconstruction now passes1,483,540model decisions across13completed July dates; [audit scope and limits](JULY_FAIR_ARITHMETIC_AUDIT.md).

**Wednesday remains a diagnostic NFL shadow target.** We have useful selection evidence, but no validated live strategy yet. MLB may complement football, although the larger sample has weakened the initial impression of steady seller profitability.

The table separates the broad seller benchmark from the narrower common priced strategy cohort. Dollars are net under the retained, historically unverified .035 maker-fee scenario. Unlimited results assume selling observed YES-taker prints at their public price and full size; they are not returns achievable with $10k or demonstrated RFQ fills.

| Sample | Broad sell-all net | Common priced sell-all net | Unlimited selected net across four models |
|---|---:|---:|---:|
| MLB July 3, Friday | −$2.885m | −$1.199m | −$130k to −$23k |
| MLB July 5, Sunday | +$1.932m | +$396k | +$70k to +$212k |
| MLB July 7, Tuesday | +$226k | −$313k | −$16.9k to +$2.5k |
| MLB July 9, Thursday | −$1.576m | −$801k | +$11k to +$65k |
| MLB July 11, Saturday | +$1.029m | +$294k | −$2.9k to +$14.1k |
| MLB July 17, Friday | +$314k | −$351k | −$16.1k to +$2.5k |
| NFL January 5–18 | +$3.111m | −$300k | +$44k to +$63k |

The earlier MLB July 1/15/29 Wednesday subset earned **+$3.586m broadly**. Its continuous funded replay at 0.3¢/combo earned only **+$27 to +$492**, using $566–$1,229 peak cash. The additional daily funded results must not be added to that account: a continuous replay across the expanded dataset is still pending. Full plots, counts and audits are in the [detailed report](MORNING_REPORT_20260908.md).

**Selection helps on some dates, but much of the apparent advantage depends on game outcomes.** July 3 and July 9 broad losses persist after every single-fixture omission. July 7's positive broad total becomes −$1.69m without COL–LAD, and its pregame slice loses $581k. NFL's broad gain comes largely from same-game/prop structures; its semantic distinct-fixture slice loses $638k. Those gains do not validate independent-leg pricing for our intended scope. [July 7 audit](MLB_JULY7_UNIVERSE_AUDIT.md), [July 9 audit](MLB_JULY9_UNIVERSE_AUDIT.md), [NFL universe audit](NFL_NATIVE_UNIVERSE_JAN5_18.md).

**There is no established universal source ranking.** Kalshi beats PM on matched probability scores across every fixture omission on July 3 and July 7. PM's July 5 and July 9 advantages reverse when SD–LAD and NYY–TB respectively are removed. PM-only selections lose $18,260 on July 7 but earn $57,065 on July 9. NFL's small Kalshi score advantage also changes sign under fixture omission. Keep the sport models separate and test the heuristics across the full development sample. [July 7 selection](MLB_JULY7_SELECTED_LEDGER_AUDIT.md), [July 9 selection](MLB_JULY9_SELECTED_LEDGER_AUDIT.md), [NFL calibration](NFL_JAN5_18_CALIBRATION_REVIEW.md).

**Realized profit is substantially larger than modeled compensation in several winning selections.** NFL selections book about $5,251–$5,996 of modeled edge against $43,529–$62,749 eventual profit; removing PHI–SF makes every model negative. Favorable settlement residuals explain most of that excess. We should not extrapolate it as repeatable pricing edge. The current baseline hurdle is **0.3¢ per combo contract, not per leg**, after maker fees.

**Lowering the hurdle or raising limits is not a reliable cure for idle capital.** All zero-edge selections lose on July 7 and July 9. All 0.3¢/leg selections lose on July 7; July 9's positive per-leg results can each reverse under fixture omission. Wider underlying spreads mostly associate with settlement residuals, while the sign and size vary by date and specification. Larger risk limits improve some portfolios and worsen others. These findings require pooled analysis, not a daily surcharge rule. [July 7 sweep review](MLB_JULY7_SPREAD_CAPACITY_REVIEW.md), [July 9 sweep review](MLB_JULY9_SPREAD_CAPACITY_REVIEW.md).

NFL's nine common underlying risk buckets impose a loose **$450 simultaneous-cash ceiling** at the existing $100 limits and at least two buckets per combo. Funded selections average just $71–$103 committed and peak at $118–$209. More competitive prices cannot consume $10k within that ceiling. All capital-hours calculations reconcile; a separate liquidation tail of at most 2.30 hours closes every portfolio's denominator. [Capital audit](NFL_JAN5_18_CAPITAL_HOURS.md), [liquidation sensitivity](NFL_JAN5_18_FULL_LIQUIDATION_CAPITAL_HOURS.md).

Accounting audits found no fee double charge or payoff-sign error. Eventual settlement P&L is shown at trade time, while cash releases only at actual settlement. Payout notional is maximum face value, not customer winnings. Reviewed NFL SF–SEA and MLB CHC–BAL identifier sensitivities remain separate from pricing and schedule assumptions. **Pinnacle is absent from these historical comparisons**; neither the planned three-source fair nor actual quote acceptance is validated here. Forward testing still requires real source depth.

The next-days plan is:

1. **Tuesday:** continue collection; finish all 16 July development dates before freezing model, hurdle, sizing and risk choices. Then test the candidate on 15 August dates with shared-fixture purging. Prepare a small reviewed NFL mapping set and resolve source freshness and current fee applicability for pricing shadow.
2. **Wednesday:** capture RFQs and proposed decisions with complete market context, source timestamps/depth, prices, sizes and canonical exposure. A run that only skips is a collection test, not successful pricing shadow. No live launch is established by the current evidence.
3. **Thursday:** inspect coverage, latency, quote competitiveness, subsequent price moves and creator behavior. Use those observations to diagnose mechanics before changing parameters.
4. **Friday–Sunday:** assess MLB alongside future-football RFQ demand and capital-hours. No-game days can still carry NFL RFQs; historical windows are not contemporaneous evidence of weekday allocation. Live trading also requires the missing execution, reconciliation and recovery path to be implemented and tested.

Public tape collection is complete. The dated model batch and analysis watchers remain active. Approximately 24 GiB was free at the latest check, but full remaining storage requirements are not yet proven to fit; additional space was requested. No date scope or raw data has been removed.

[Detailed findings and plots](MORNING_REPORT_20260908.md) · [Readiness gaps](MORNING_LAUNCH_READINESS.md) · [Wednesday runbook](WEDNESDAY_SHADOW_RUNBOOK.md) · [Development/validation handoff](MLB_COMPLETION_HANDOFF.md).

July 11 also shows concentration: removing AZ–LAD changes broad scenario net from +$1.029m to −$459k. The identity recovery preserved all 223 completed artifacts and passed 33 focused tests plus July 9 economic replay parity. [July 11 audit](MLB_JULY11_UNIVERSE_AUDIT.md).

July 17’s audited broad result becomes −$802k without SD–KC; its pregame slice loses $103k. Selection audits pass for July 11/17. Source ranking again reverses: PM has the better paired Brier score July 11, Kalshi July 17. [Latest entry/risk review](MLB_JULY17_ENTRY_RISK_REVIEW.md).

July 19 native audit is now complete: broad net +$948k, reversing to -$743k without DET–LAA; selected-model processing remains pending. [Audit and plot](MLB_JULY19_UNIVERSE_AUDIT.md). Additional July 11/17 source and spread diagnostics are verified: [follow-up](MLB_JULY11_17_DISAGREEMENT_SPREAD_REVIEW.md).

July 19 is fully processed and audited: PM-selected unlimited net +$22,257 versus Kalshi -$9,921; PM remains profitable and better on matched Brier after every single-fixture omission. Funded PM net +$154, peak cash $1,068. This stronger daily PM evidence remains development-only. [Selection audit](MLB_JULY19_SELECTED_LEDGER_AUDIT.md) · [Entry/spread/risk review](MLB_JULY19_SPREAD_CAPACITY_REVIEW.md).

July21 is fully processed: common sell-all -$30,272; all four unlimited selections positive ($21,253–$74,211) and remain positive after each game omission. Funded K/equal/PM positive, PM75 negative. [Audit](MLB_JULY21_SELECTED_LEDGER_AUDIT.md) · [Entry/risk](MLB_JULY21_ENTRY_RISK_REVIEW.md). NFL isolated risk sweep also completed all84portfolios: [results](NFL_JAN5_18_RISK_ABLATION.md).

July23 is fully processed and audited: broad +$2.603m (all game omissions positive), common +$221k, selected unrestricted K/equal/PM75 +$5.7k/$8.7k/$7.3k and PM -$986. Equal survives all game omissions. [Selection](MLB_JULY23_SELECTED_LEDGER_AUDIT.md) · [Spread/entry/risk](MLB_JULY23_SPREAD_CAPACITY_REVIEW.md).
