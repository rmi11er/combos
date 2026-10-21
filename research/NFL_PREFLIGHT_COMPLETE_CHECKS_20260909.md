# Preflight check alignment

The static NFL preflight previously stopped at the first mapping failure and did
not require Pinnacle payoff_reference or verified stake units. Those fields are
required by the actual normalizer, so a superficially cleared configuration could
have appeared ready while every Pinnacle observation remained invalid.

`readiness.py` now reports all exclusions per mapping and aggregate counts, while
preserving the existing first-reason counts for compatibility. Missing payoff
reference and missing USD/stake/reference evidence disqualify configuration
eligibility consistently with the normalizer. Two regression tests passed,
including a configuration that previously could have appeared ready despite
missing both requirements.

Running the delivery-age/sharp-peer candidate through the existing authorized key
handoff resolved the process-level API-key blocker without making any provider
request. The remaining configuration evidence is:

- 454 mappings lack approved Pinnacle payoff basis.
- 454 lack verified Pinnacle limit-unit evidence.
- 189 lack selector references in this runtime configuration.
- Zero eligible fixtures, so the shadow pricing preflight remains blocked.

These are overlapping counts, not mutually exclusive groups. The separately
reviewed selector candidate has 187 missing selectors rather than 189; it has not
been promoted into this runtime. Completed-period payoff enumeration and explicit
basis sensitivity are useful inputs, but neither constitutes an approved
unconditional pricing basis.

Result: `runs/nfl_preflight_complete_checks_20260909/report.json`.
No historical pinned implementation, model weights, or live permission changed.
