# Grouped creator markout evidence

Added `scripts/review_creator_markouts.py`, a reusable multi-capture review
workflow. It verifies each runtime mapping against the markout identity, records
database hashes, rejects duplicate source databases and conflicting duplicate
RFQ/horizon labels, and keeps unavailable and pending observations explicit.
It does not publish creator state or sanctions.

Within each creator/horizon, the first chronological RFQ for each fixture set is
the representative. This prevents repeated requests from multiplying that set's
weight. Raw means remain alongside grouped means for review. A connected-component
diagnostic also links fixture sets sharing any game, transitively. Neither group
counts nor components are estimates of statistically independent samples.

The completed five-minute and three-minute captures together contain:
- 4,376 observed markouts, 703 unavailable labels and 816 pending horizons.
- 166 creators with observed marks, forming 456 creator/horizon reviews.
- 1,815 first-per-fixture-set representatives across those reviews.
- At most three disconnected fixture components per creator/horizon.

This is evidence that repeated RFQ volume overstates sample diversity, not evidence
that any creator is reliably toxic. Same-model fair changes include freshness
weight changes, missing marks can select the sample, and no actual acceptance or
realized strategy profit is attached. The existing duplicate-burst cooldown is a
separate behavioral policy; these results do not justify new economic sanctions.

Two focused tests verify transitive overlap and a deliberately adversarial repeat
case: 100 subsequent positive marks can flip the raw mean, but do not replace or
multiply the first fixture-set representative. The combined report reconciles to
both durable label/pending censuses. The earlier five-minute marks were computed
by following a completed capture; only the three-minute capture ran the markout
worker concurrently. These retrospective reports do not imply live publication
of five-minute markout-based creator state.

Next infrastructure step is a persistent evidence importer keyed by immutable
source and RFQ/horizon identity, with publication-time provenance, feeding a
review process. The current creator-service markout schema differs from durable
worker labels and must be explicitly adapted before connecting them. More slates
and outcome evidence remain necessary for an economic blacklist.

Plan: runs/nfl_creator_markout_combined_plan_20260909.json.
Artifacts: runs/nfl_creator_markout_combined_review_20260909/{summary,creators,dependence_diagnostics}.json.
