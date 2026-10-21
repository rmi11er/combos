# Recovered OddsPapi process environment

The user-provided temporary handoff file remains available. Loading its single token directly into a child environment removes `oddspapi_key_unavailable_to_process` from the NFL static preflight. No key was printed, copied into repository configuration or placed on a command line, and no provider request was made. The parent session environment remains unchanged.

Use `scripts/run_with_oddspapi_key.py --key-file <user-provided-handoff> -- <approved child command>` to launch a collector or preflight with that handoff. The helper reads a single token and runs an argument vector without shell evaluation. Do not interpret shell export statements or source unrelated environment files. Child applications must still follow normal secret-safe logging practices.

Evidence: `runs/morning_research_20260908/nfl_preflight_handoff.json`. Remaining static shadow blockers are reviewed pregame payoff mappings and verified/current combo fee metadata. Key availability is not proof that the token is still valid or that subscription entitlements match the intended calls; those require a bounded API probe. No live trading was enabled.

## Bounded API probe completed

The existing smoke workflow reused the previously discovered NFL identifiers and issued exactly three requests: account, NFL tournament odds, account. All returned HTTP 200. The entitled bookmaker is `pinnacle+30`, and the odds response contains 16 fixture records. The active football subscription has a 100,000-request limit, no player props, no in-play odds and no WebSocket access. Its reported period is September 7–October 7, 2026. Reported usage increased from 28 to 29, consistent with one charged odds request in this probe.

This confirms the recovered token works for the intended pregame REST feed. It does not prove continuously fresh delivery, exact payoff mappings, usable limits/depth or the correctness of live pricing. The saved response envelopes were checked for accidental inclusion of the actual credential value; none was found. No trading or order submission occurred.

Evidence: `runs/morning_research_20260908/oddspapi_recovered_smoke/summary.json` and `verification.json`.

## Short freshness probe

Two odds polls 30.52 seconds apart completed, with five total endpoint requests including account/catalog calls and three reported quota units consumed (29 to 32). Both polls returned 16 fixtures and 2,008 active outcomes without parser issues. Eight outcome records were added, but none of the 2,106 existing outcome records changed economically. The verdict is therefore `inconclusive_membership_changes_only`, not healthy/stale upstream validation.

Receipt times and HTTP dates were current. Reported change-to-publication lag had a median of 30.55 seconds, consistent with the delayed-feed metadata, but this is not a measured current end-to-end latency guarantee. Old individual price-change timestamps can reflect unchanged prices; they cannot alone diagnose a stale feed. More observations during actual price movement are needed before treating freshness as validated.

Evidence: `runs/morning_research_20260908/oddspapi_recovered_freshness/summary.json`. The collector's shared request budget and exclusive ownership lock were used; no live trading occurred.
