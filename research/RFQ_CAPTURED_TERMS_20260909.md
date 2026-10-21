# Captured NFL series fees, grids and causal creator state

All 167 three-source-priced RFQs match the captured zero-maker-fee series, using
longest-prefix matching. The prior RFQ charge sweep's uniform .035 coefficient was
an explicit sensitivity scenario, not the applicable captured rate for this cohort.
Do not use its fee-inclusive asks as the corrected captured-term result.

At 0.3c/combo, the corrected median asks are 29.8c (point), 30.6c (quarter reserve)
and 32.9c (full reserve). Median conservative fragmentation cash holds are $24.85,
$23.44 and $20.70. All 501 rows satisfy the captured piecewise grid, causal fee-term
validity and requested edge. The central price tick is .001, not the previous
uniform .0001 assumption. These grids were sampled at series level; exact combo
metadata validation remains required before live quoting.

All 167 creators are clear under policy events actually published before their RFQ
arrivals. Later policy publications are not applied retroactively, even if their
underlying evidence predates the RFQ. This short fresh capture does not include a
mature imported blacklist, and cannot establish the blacklist's economic benefit.

Each decision now includes canonical signed leg-risk identities and distinct event
keys. Complementary moneylines share an underlying key, without granting hedge
credit to their different combo payoffs. Portfolio reservations are still pending.

Workflow: scripts/rfq_quote_terms_replay.py. Outputs:
runs/nfl_rfq_quote_terms_20260909/{summary,decisions,verification}.json.
Five focused quote tests pass; all 501 output rows were independently checked for
grid membership, fee-prefix selection, creator publication causality, leg counts
and fee-net edge. Balance precision remains a .0001 research assumption; target
quantities remain conservative bounds. No orders or fills are inferred.
