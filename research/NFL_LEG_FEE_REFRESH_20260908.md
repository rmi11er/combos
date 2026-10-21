# NFL individual-leg fee refresh

Fresh public Gamma NFL Week 1 events and Kalshi series/fee-change responses updated fee metadata for all 454 configured mappings. The existing fee helper reports Kalshi taker coefficient .07 and Polymarket coefficient .05; these coefficients did not change. They are probability-dependent formula coefficients, not flat percentage charges on premium.

Independent comparison against the saved prior configuration verified that only mapping fee records changed. All other configuration, including risk identities, payoff review status, Pinnacle selectors, risk limits and combo terms, remained identical. Every retained public-source hash was checked. Account-specific execution precision is still unverified; this refresh does not certify historical January/July fees.

The handoff-loaded preflight was rerun without starting collectors or placing orders. Shadow configuration remains ineligible because no Pinnacle payoff mappings have been reviewed. The API key and fee refreshes do not remove that separate requirement.

[Verification](../runs/morning_research_20260908/nfl_leg_fee_refresh/verification.json) · [Public source report](../runs/morning_research_20260908/nfl_leg_fee_refresh/public_sources/report.json) · [Preflight](../runs/morning_research_20260908/nfl_leg_fee_refresh/preflight.json)
