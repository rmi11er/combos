# Matched NFL source-weight sensitivity

Replayed all47,937 RFQs from the120-second both-demand capture with four separately
maintained causal consumers. All models priced the same694 RFQs. All require all
three venues and retain the same spread/depth/freshness weighting, fee widening,
price grids, disagreement guards, Pinnacle payoff/unit assumptions and creator
publications. Equal score multipliers do not mean equal final weights.

The research quote policy is point fair+0.3c/combo, native stake USD scale1, $10k
capital, $1k each underlying/combo/event, full RFQ size. All admitted quotes are
assumed filled and held throughout. These are capacity scenarios, not actual fills
or forecasts. The quote consumer does not apply the pricing guard's defensive risk
multiplier; this comparison holds those research caps fixed across models.

| Source score prior | Reservations | Peak held | Admission differences from captured |
|---|---:|---:|---:|
| Captured K1/PM1.5/Pin1.5 |106|$4,672.89|0|
| K1/PM1/Pin1 |107|$4,671.33|1|
| K1/PM3/Pin3 |98|$4,666.38|8|
| K1/PM1.5/Pin0.5, Pin cap20% |105|$4,765.85|5|

Doubling sharp-source multipliers moves the combo fair by -0.108c to +0.072c
between the5th and95th percentiles; extremes -0.229c/+0.183c. Its quote difference
has median0 and5th/95th percentiles -0.1c/+0.1c. Reducing Pinnacle weight produces
larger positive differences:95th percentile fair+0.254c, quote+0.3c; max fair+0.508c.
All source weights remain liquidity-dependent and capped; multipliers are not
probability weights. Small quote changes can alter target-cost quantity bounds and
subsequent portfolio admissions, so admission changes are path-dependent.

This sample does not suggest that changing source priors alone will unlock major
cash deployment. It says nothing about relative forecasting skill: no outcomes or
actual quote acceptances are attached. Liquidity-sensitive charges, source-agreement
regimes and sustained/multiple-slate testing remain necessary before selecting
parameters. No August held-out outcomes were inspected and no production policy
was changed.

Verification:694 baseline fair scenarios exactly match the existing archived replay;
all694 baseline admission/binding/cash rows exactly match the independently audited
capacity sweep. All2,776 model rows reconcile summary counts, peak cash, venue
weight sums and quote complementarity. Source/code/config hashes are retained.
Challenger fair arithmetic uses the common pricing implementation and was not
independently rederived. The plot was rendered and visually checked.

Config: config/nfl_source_weight_comparison_20260909.json
Workflow: scripts/compare_rfq_source_weights.py and scripts/plot_rfq_source_weights.py
Outputs: runs/nfl_source_weight_comparison_20260909/{summary.json,priced_decisions.jsonl,verification.json,source_weight_sensitivity.png}

Historical recovery supervisor restarted collection as PID50445; ps confirmed the
replacement live. The existing supervisors remain responsible for collection and
frozen validation; no duplicate job was launched.
