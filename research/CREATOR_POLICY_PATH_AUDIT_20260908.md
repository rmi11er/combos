# Creator policy used by shadow pricing

The live runtime and nightly sniffer implement different policies. The nightly export's 217 entries are not evidence that those same creators would be rejected by the shadow engine.

`scripts/runtime.py` now resolves the optional `creator_policy` object from the runtime configuration in both the worker and archive replay path. Omission preserves existing defaults. It does not load `config/rfq_sniffer.json`. The consumer persists requests, counts, policy history and its event cursor in the runtime database. `ShadowEngine.step` waits for the creator cursor before handling an RFQ. `creator_state` selects only transitions with source sequence strictly before that RFQ. A triggering request does not retroactively acquire its own newly generated strike; subsequent requests see it. Cooldown/blocked states reject requests and policy events can invalidate outstanding shadow reservations.

| Behavior | Runtime CreatorService | Nightly sniffer v2 configuration |
|---|---|---|
| Repetition | At least 30 requests in 60 seconds, same exact leg set at least 80% | Exact and near-template repetition, rate and structural evidence |
| Repeated bursts | Three windows, at least 60 seconds apart | Three qualifying bursts, with separate recurrence/confidence logic |
| Default cooldown/blacklist | One hour cooldown | One-day provisional / seven-day recurrent blacklist |
| Large leg count | Counted as evidence at 20 legs; no automatic ban | Structural diagnostics starting at 12 legs, plus repetition criteria |
| Markouts | Grouped and retained, no automatic adverse-price ban | Later public-market trades are context, not creator-specific fills |
| Publication | Transactional event/history consumed by shadow | Export after journal processing and reporting |

These are implementation descriptions, not validated optimal thresholds. The runtime policy version is persisted by consumer registration and a configuration mismatch is rejected. Policy selection is now an explicit strategy configuration parameter covered by the immutable runtime manifest; do not silently import the broader nightly list.

For example, the current defaults can be frozen explicitly as:

```json
"creator_policy": {
  "window_seconds": 60,
  "minimum_requests": 30,
  "duplicate_fraction": 0.8,
  "bursts_before_cooldown": 3,
  "cooldown_seconds": 3600,
  "long_legs": 20
}
```

Unknown fields, nonpositive/nonfinite numbers, boolean values, fractional counts and fractions above one are rejected. No deployed configuration or threshold was changed. This runtime source change requires a new experiment database under the existing source-pinning rule; old archives retain their saved source. The runtime and added policy tests pass together (32 tests), covering default parity, invalid inputs, causal cooldown, reopen equivalence, policy mismatch and actual worker use of the configured thresholds. Source files edited here are outside the active historical batch/completion/spread watcher manifests.

The September8 bounded real-data consumer replay establishes restart equivalence on its sample, but not equal decisions between the two policies. Focused existing runtime tests for creator causality, persistence, expiry and event rollback pass (3 passed, 17 deselected). The next empirical comparison needs identical causal input, timestamped policy states, blocked RFQ opportunity counts and prospective markouts/fills. No creator-specific economic toxicity is established by these tests.

## Refreshed NFL preflight

The September8 21:55 Chicago static preflight still reports 454 mappings excluded for unreviewed Pinnacle payoff basis, expired/unverified combo fee metadata, and no OddsPapi key visible to that process. It remains shadow-not-ready and live-not-ready. This observation does not establish whether a key exists in another terminal or scheduler environment. No credential contents were read, and no live feed/order was started.

[Current preflight](../runs/morning_research_20260908/nfl_preflight_current.json) · [Sniffer and replay evidence](SNIFFER_FORWARD_READINESS_20260908.md)
