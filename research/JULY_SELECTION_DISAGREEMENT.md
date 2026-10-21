# Full July: where Kalshi and Polymarket selections disagree

This paired comparison covers all 467,583 matched prints across the 15 priced July development dates. Each source selects at the same observed price, size and maker-fee scenario using the 0.3c/combo point-fair hurdle. There are no capital constraints here. Every print belongs to exactly one group.

| Selection group | Prints | Realized net | Kalshi modeled compensation | PM modeled compensation |
|---|---:|---:|---:|---:|
| Both | 2,256 | $143,994.95 | $9,653.89 | $13,960.97 |
| PM only | 23,895 | $514,098.44 | −$24,091.57 | $41,683.00 |
| Kalshi only | 548 | −$12,942.91 | $1,748.56 | −$21.60 |
| Neither | 440,884 | −$312,701.96 | −$511,096.79 | −$353,793.62 |

Groups reconcile to $332,448.53 full matched-cohort net. Both plus each exclusive group reproduces that source's complete July point-selected count and P&L. These are observed-price selection counterfactuals, not customer acceptance of quotes we submitted.

PM-only net is positive after every single-date omission, with a minimum of $338,850.87, and every single-fixture omission, with a minimum of $373,576.11. It is also positive through July 25 alone at $272,701.22. Both-source selections remain positive under both omission checks. Kalshi-only selections lose $16,062.18 through July 25 and $12,942.91 over the full period.

The stronger PM-only result supports the prior that cross-venue disagreement can be informative in MLB, alongside the matched scoring and date-stability evidence. It does not establish why the books disagree, that lower fees cause greater sharpness, or that Pinnacle would confirm those signals. Most PM-only realized profit exceeds its approximately $41,683 of modeled compensation; favorable settlement residuals remain a large part of the result. Do not extrapolate $514,098 as recurring expected edge.

The neither-source group loses $2,702,377.38 through July 25, then recovers substantially in the final three observed dates while remaining negative overall. That contrast helps explain why a positive broad-universe curve is insufficient reason to quote all RFQs at the observed traded price.

## Verification and use

The existing paired-row validator checks identical timestamps, quantities, prices, fees, settlements, source metadata and risk buckets for each K/PM pair. The workflow rejects duplicate IDs across dates, confirms the original price-only admission rules, and reconciles all selection counts/net results to the independently audited complete-July reserve report. All 15 input hashes and both workflow hashes were rechecked. Omissions delete trades without reallocating exposure and are not independent confidence intervals.

Keep PM-heavy MLB pricing among the candidate models for the continuous funded and held-out tests. Separate quote reserve, margin, sizing and source weighting: the point-selected evidence does not validate the current stressed quote rule. NFL evidence remains separate. Historical fee applicability, source semantics and exceptional payoff parity remain limitations; live depth, Pinnacle and RFQ execution are not established by this study.

[Grouped results and omissions](../runs/morning_research_20260908/july_selection_disagreement/results.json) · [Verification](../runs/morning_research_20260908/july_selection_disagreement/verification.json) · [Reproduction](../runs/morning_research_20260908/july_selection_disagreement/run.py)
