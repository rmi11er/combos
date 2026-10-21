# Independent RFQ quote and capacity accounting audit

The complete latest capture's 2,082 quotes and20,820 risk decisions (30 portfolios)
pass the new reusable audit scripts/audit_rfq_capacity.py. It does not import the
quote solver, fee helper or capacity ledger. Decimal arithmetic rederives finite-
size maker fees and balance alignment, full fixed quantities or target-cost bounds,
quote-reference and net-edge arithmetic, captured grid membership and fragmentation
cash holds. An independent integer exposure replay verifies every admission, all
binding-limit reasons, active reservations, expiry, capital ceiling, peak cash and
summary count. Exact quote and portfolio policy censuses are required.

Four intentional corruptions were rejected: altered fee, altered quantity, flipped
admission and removed decision. These were applied only to temporary copies. The
final v2 audit additionally checks exact summary/portfolio policy identities rather
than relying on counts alone. Original artifacts were not modified.

This validates accounting conditional on inputs. It does not independently rederive
three-source fair values, canonical payoff identities, creator policy substance or
fee metadata authenticity. Sequence bounds reject future creator publications, but
are not a complete independent creator-state replay. The sampled grid and balance
precision assumptions remain research assumptions. No prediction of fill rate,
profitability or safe optimal risk limits follows from an accounting pass.

Final verification: runs/nfl_both_demand_independent_audit_v2_20260909/verification.json.
Mutation evidence: runs/nfl_both_demand_independent_audit_20260909/mutation_checks.json.
Both verification receipts identify their inputs and auditor by SHA256.
