# Paired freshness coverage replay

`VerifiedBookState` consumes native Polymarket observations, verification events
and venue resets in strictly increasing event sequence. It binds certificates to
the current generation/revision and exact baseline observation, waits until their
publication time, expires them after 15 seconds, and invalidates them on any new
book observation or reset. Candidate records are copies with explicit native time
and verification provenance; the underlying observation remains unchanged.

Replaying the 25-second, three-request capture at its 23 Polymarket heartbeat
checkpoints yielded:

| Coverage | Native-age baseline | Snapshot-verified candidate |
|---|---:|---:|
| Mean eligible market keys | 66.09 | 238.09 |
| Last checkpoint | 68 | 164 |

Maximum additional eligible keys was 299. No checkpoint lost baseline coverage.
Both book and certificate state cleared at the final venue reset. The request
budget ended after three probes; certificates subsequently expired rather than
remaining valid indefinitely. Means weight each heartbeat checkpoint equally.

20 tests passed across consumer state, snapshot verification and asynchronous
collector integration. Workflow: `scripts/replay_verified_book_coverage.py`.
Results and source hashes: `runs/polymarket_verified_coverage_20260909`.

This is single-venue coverage on a short selected experiment, not three-source
fair accuracy or executed opportunity. Certificate integrity relies on the trusted
collector's verified raw evidence; this state consumer is not an independent REST
authenticator. Full pricing and RFQ behavior remain to be evaluated.

Next integrate the candidate record view into a matched three-source shadow
diagnostic, preserve baseline outputs, and add a sustained snapshot request budget.
Kalshi quiet-book freshness and Pinnacle payoff/liquidity assumptions remain
separate constraints; this Polymarket improvement does not clear them.
