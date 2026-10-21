# Pricing disagreement reaches research admission

RFQScenarioConsumer now retains each selected leg's pricing_guard. ResearchQuoteConsumer
requires complete allowed guards by default, takes the minimum risk multiplier across
legs, and passes it to CapacityReplay. The multiplier reduces each applicable
underlying/combo/event cap against existing plus proposed exposure. It does not
reduce recorded exposure, cancel existing positions, or alter available cash.

Missing/invalid guard evidence and a halted guard block admission. The explicit
apply_pricing_risk_multiplier=false policy remains available solely to reproduce
legacy research ablations; decisions report that it is disabled. Default is true.
The live persistent risk API already accepts a multiplier, but the complete live
quote transport/lifecycle is still not wired or authorized by this change.

27 focused tests pass, including cumulative exposure under reduced caps, restoration
to normal limits, malformed multiplier rejection before ledger mutation, strictest-leg
selection, missing/halted evidence, explicit legacy ablation and defensive admission
after worker restart. No existing holding is released when the regime changes.

Full replay of all47,937 RFQs across four source-weight policies priced694 each.
Every priced leg was in the normal regime: zero defensive priced RFQs. All2,776
saved decisions exactly match their prior versions after removing only the new
pricing_guard and applied-multiplier evidence. There is no demonstrated performance
benefit from this capture, only a corrected path tested synthetically. Peak capital
and reservation counts are unchanged.

Prechange source copies: runs/disagreement_risk_fix_20260909/source_before.
Verification: runs/disagreement_risk_fix_20260909/verification.json.
Updated full replay: runs/nfl_source_weight_comparison_guarded_20260909.
All23 frozen August source hashes were verified unchanged. Old worker identities and
exact-output baselines remain version-specific; do not resume old outputs using the
new consumer. They require their archived source version or a fresh output directory.

Next sustained/multiple-slate shadow capture should measure actual defensive regime
incidence, quote competitiveness and source-agreement outcomes. The delayed feed
is not assumed to be generally toxic, and this change does not select optimal risk
limits or source weights from held-out outcomes.
