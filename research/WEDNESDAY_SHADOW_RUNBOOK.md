# Wednesday shadow session: executable preparation and remaining work

Reviewed September 7, 2026 late evening against the actual CLI and supervisor source. This runbook does not certify pricing or execution readiness. No provider calls or captures were launched during this review.

## Existing collection smoke test

`scripts/shadow_research_capture.py` deliberately requires every mapping to carry a pricing block and permits only 90–120 seconds. Use it for a bounded collection smoke test, not a healthy-pricing soak. It reconciles subscription usage, freezes configuration/code, starts runtime and Pinnacle collectors together, drains consumers, archives input events and exports review records.

From the repository root, with an existing securely stored key file and a new output path:

```sh
export COMBOS_ODDS_KEY_FILE='/absolute/path/to/existing/private/key-file'
export COMBOS_CAPTURE_OUT='runs/nfl_wednesday_collection_smoke_NEW'
.venv/bin/python scripts/shadow_research_capture.py prepare \
  --out "$COMBOS_CAPTURE_OUT" --key-file "$COMBOS_ODDS_KEY_FILE"
COMBOS_CAPTURE_FREEZE=$(.venv/bin/python scripts/shadow_research_capture.py source-digest)
.venv/bin/python scripts/shadow_research_capture.py run \
  --out "$COMBOS_CAPTURE_OUT" --key-file "$COMBOS_ODDS_KEY_FILE" \
  --seconds 100 --code-freeze "$COMBOS_CAPTURE_FREEZE"
```

The key value is never printed or passed as a command argument. Replace the placeholder path before executing; do not copy an old temporary credential path without checking it still exists. Preparation checks the account and consumes provider requests; it is not an offline command. Run within ten minutes of preparation, with unchanged code/configuration. Do not reset the shared monthly request budget or reuse an event database.

Read `readiness.json`, process logs and the archived decision records. Verify process exits and post-processing results, positive actual Kalshi/Polymarket two-sided depth, Pinnacle active observations and invalid reasons, consumer drainage, and complete per-RFQ dispositions. Zero orders is expected. All-skip results are collection evidence only. Distinguish upstream observation age, transport receipt age and time since the last price change.

## Sustained shadow supervisor implemented; healthy-pricing validation pending

The smoke wrapper cannot run a reviewed pricing subset because its validator requires all mappings blocked. Do not remove that guard or assume a longer `--seconds` value is supported. Before a sustained pricing experiment:

1. Review exact payoff equivalence and current fees for a small subset spanning at least two distinct fixtures. Resolve Pinnacle limit units and snapshot freshness semantics. Keep unavailable exact lines unavailable.
2. Create a new versioned shadow runtime containing only reviewed mappings, actual forward depth requirements and the existing capital/risk limits. Record mapping evidence and the time each policy/fee fact became available. No historical depth imputation is allowed.
3. Embed the logging-only candidate study with `scripts/configure_shadow_policy_study.py`; supply verified cash precision and fee-availability time. Its point variants are explicitly nondeployable diagnostics, do not reserve risk, and have no invented acceptance labels.
4. Use the new [sustained shadow supervisor](SUSTAINED_SHADOW_SUPERVISOR.md). It supports 120–21,600 seconds, executes a frozen local source/configuration clone, reconciles the shared budget, directly supervises collectors/workers, stops process groups, drains consumers and archives review evidence. Root independently passed all 18 focused tests, including a real offline runtime lifecycle. Missing/duplicate RFQ dispositions, invalid quote depth/latency, early exits and unfinished drainage prevent a healthy result. Actual live validation remains pending.
5. Start with a bounded run and inspect healthy quote-generation latency, reserve decomposition, proposed prices/sizes, canonical risk exposure and complete candidate dispositions before extending duration. Test cutoff/invalidation and recovery with healthy inputs; rejection-path latency is insufficient.

Target-cost RFQs retain a documented candidate-dependent sizing limitation. Counts of candidate prices must not be summed as filled volume. Actual RFQ submit/accept/confirm/cancel, fill reconciliation and ambiguous-submission recovery remain separate unimplemented live-execution work.

## Session decisions

Use the [readiness plan](MORNING_LAUNCH_READINESS.md) for kickoff/cutoff times and the [morning brief](MORNING_BRIEF_20260908.md) for research conclusions. Report collection health, verified pricing health and execution readiness independently. Keep the healthy-pricing result unavailable until the above experiment actually produces and verifies it. Review creator behavior prospectively; a high leg count alone does not justify a permanent blacklist.

The new supervisor adds an executable sustained lifecycle without modifying the smoke wrapper or approving any mappings. Follow its linked prepare/run commands with reviewed inputs; preparation can call the provider.

CLI signatures were checked with `--help`; the duration and mapping-block restrictions were inspected directly in `shadow_research_capture.py`. These checks do not execute or validate a live capture.
