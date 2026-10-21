# Full July continuous risk experiment

The funded risk sweep uses the same certified immutable index as the 48-policy July margin study: 467,583 common prints per model across 15 priced development dates, with July 13 retained as an explicit unpriced gap. Every portfolio starts with $10,000, carries positions/cash continuously and releases funding only at actual settlement. Daily P&L is not reset into fresh capital.

Four source models each receive four risk policies:

| Policy | Underlying cap | Combo cap | Event cap |
|---|---:|---:|---:|
| Existing baseline | $100 | $100 | $250 |
| Balanced $1,000 | $1,000 | $1,000 | $1,000 |
| Event $1,000 | $10,000 | $10,000 | $1,000 |
| Event $2,000 | $10,000 | $10,000 | $2,000 |

All retain point entry at 0.3c/combo, full observed public-print quantities and inherited dated maker fees. There is no premium restriction, partial sizing or inferred quote acceptance. This separates risk-allocation effects from changes in source probabilities or margin. The current stressed shadow rule is a separate pricing-model question.

The runner reuses the existing streaming evaluator and pins the shared input index and source closure. It writes progress after each portfolio and publishes completion only after all 16. A prepared independent audit will replay the integer exposure checks and compare baseline decisions, fills and curves row-for-row with the 48-policy study's funded 0.3c/combo baseline. Execution completion alone does not claim that independent audit passed.

The first launch stopped before creating output because its coverage guard expected a list of strings while the index stores structured missing-date records. The guard now reads their `date` fields and still requires only the July 13 gap. No source data or existing replay was altered. The second launch is active; results and candidate parameters are pending.

[Runner](../scripts/mlb_continuous_risk_sweep.py) · [Independent audit](../runs/morning_research_20260908/july_continuous_risk_audit/verify.py) · [Experiment receipt](../runs/mlb_july_continuous_risk_20260908/started.json)

The first completed Kalshi baseline exactly matches the separate 48-policy replay across all 467,583 decisions, 621 fills and 458,387 curve rows. Its continuous net is $506.45 with $1,140.04 peak committed cash. This is one verified baseline, not a completed risk comparison. Evidence: `july_continuous_risk_audit/kalshi_baseline_parity.json`.
