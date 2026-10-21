# Causal top-book pricing and capacity comparison

The top-only research overlay recovers 80 priced RFQs (687 to 767, +11.6%) and
106 of the existing unavailable markouts (371 to 265). Every previously priced
RFQ remains priced, with identical common-entry fair values. All 65,995 baseline
pricing decisions AND quote/risk decisions exactly reproduce the durable capture.
All 1,719 baseline markout fair records also reproduce exactly.

Certificates become available at the original verification-result publication
sequence and time, not at the earlier HTTP receipt. Top prices, sizes, generation
and revision must match; any revision change, reset or token rebuild invalidates
the overlay. Inactive observations are eligible only when their recorded reason
is depth quarantine. Actual top mismatches stay excluded. The replay retains
recorded collection/rebuild actions; it does not simulate how a different
verification policy would alter later requests or subscriptions.

Under the captured $10k capital, $1k underlying/combo/event limits and point fair
plus 0.3c/combo quote policy, with all admitted quotes assumed filled and held:

| Metric | Full-depth baseline | Top-only overlay |
|---|---:|---:|
| Priced RFQs | 687 | 767 |
| Research reservations | 78 | 80 |
| Risk rejections | 609 | 687 |
| Peak committed cash | $4,231.2354 | $4,275.4493 |
| Creator cooldown exclusions | 85 | 85 |

Coverage improves materially, but current risk limits admit only two additional
reservations and about $44 more committed cash. Policy records differ on 325 RFQs
because earlier admissions change subsequent portfolio state; this is not 325
different fill decisions. These are hypothetical reservations, not acceptance,
profit or evidence that risk caps should be increased.

Tests: 15 focused overlay/verifier tests passed, including publication timing,
expiry, revision/rebuild invalidation and size mismatch. Original verifier tests
passed in the preceding component check. The replay's exact baseline comparison
is stronger evidence for this dataset than fixture tests alone, but shared fair
and risk code is not independent probability validation.

Remaining work: prospective collection with separately labeled top evidence,
new-entry markouts, grouped creator/fixture analysis, liquidity-dependent charge
and partial-sizing comparisons, and multi-slate outcomes. Hyperparameters remain
provisional; the full historical held-out study remains in progress.

Artifacts: runs/nfl_top_book_pricing_capacity_20260909/{summary,recovered,policy_changes}.json.
Workflow: scripts/compare_top_book_pricing.py.
