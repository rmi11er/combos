# Top-of-book verification research replay

Implemented a separate top-only verifier in
`scripts/top_book_verification_research.py`. It compares both best prices and
sizes, retains the existing generation, revision, request-duration, HTTP-age and
availability checks, and issues an explicitly top-only research certificate.
The certificate expires on any revision change, even if the new top is unchanged.
It cannot be used as an existing full-depth certificate. Source pricing modules
and the historical validation implementation were not changed.

The captured 180-second NFL stream contains 3,600 snapshot comparisons. Replay
reconstructed raw books, token-rebuild filtering, recorded generations/revisions,
request selection and REST responses. Every baseline verdict and every successful
baseline evidence object exactly matches the published capture result.

| Result | Full-depth baseline | Top-only research |
|---|---:|---:|
| Verified | 3,464 | 3,550 |
| Book changed during request | 45 | 45 |
| REST/WS inputs differ | 91 | 5 |

All 86 additional verifications are the previously identified lower-depth-only
mismatches. Every original success remains successful. These are snapshot
comparisons, not new RFQ fills or recovered markouts. The original request and
quarantine/rebuild actions are held fixed; a prospective alternative policy could
change subsequent collection behavior.

Validation: 22 focused tests passed, covering top-price and size mismatches,
chronology, reconnects, revision changes, expiration, malformed deeper ladders,
input immutability and the distinct authority of top-only evidence. Shared helper
code means this is not an independent implementation of snapshot arithmetic.

Next: attach these separately identified certificates at their causal publication
sequences in a research replay and measure priced RFQs, unavailable markouts and
changes in liquidity weights. Do not insert them at the earlier HTTP timestamp
or let an old certificate survive a later book revision. Preserve the original
full-depth baseline and distinguish observed from counterfactual collection.

Artifacts: `runs/nfl_top_verification_replay_20260909/{summary,rows,verification}.json`.
Workflow: `scripts/replay_top_verification_research.py`.
