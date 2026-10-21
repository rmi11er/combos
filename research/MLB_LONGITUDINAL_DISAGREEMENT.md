# Continuous replay source-disagreement audit

Run `scripts/mlb_longitudinal_disagreement.py --version <retained longitudinal version> --out <new directory>`. Optional `--variant edge_0_3c_per_leg` distinguishes the per-leg hurdle from the default0.3c/combo-contract policy.

Consumes matching unlimited Kalshi and PM decision ledgers, verifies identical summary policies and complete paired cohorts, hashes unchanged inputs, retains source thresholds and observed/missing dates. Existing pair validation refuses trade/fee/outcome mismatches and inventory-restricted decisions. Outputs source-direction, selection, size and leg cuts, paired quantity-Brier, and per-fixture omission diagnostics for the entire common cohort and each source-only selection. This is a descriptive combo-pricing test, not a leg-level sharpness conclusion or evidence of achievable RFQ fills. Historical fee scenario and source coverage limitations remain.

Do not average ratios or Brier scores across dates: run on the actual retained continuous version. Version inputs are immutable research outputs, not the mutable latest pointer. The initial July1/15 report is in `runs/morning_research_20260908/disagreement_july1_15`. Three additional tests cover exact whole-fixture omissions, policy mismatch and incomplete source pairing; three inherited tests cover quantities, unknown outcomes and inventory exclusions.
