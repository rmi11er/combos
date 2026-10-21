# Sustained shadow supervisor — offline implementation review

New workflow: `scripts/sustained_shadow_supervisor.py`; tests: `tests/test_sustained_shadow_supervisor.py`. Existing runtime, feeds, source guards, smoke wrapper and mapping configurations are unchanged. No feeds, account inspection, orders or mapping approvals were run during this implementation.

The workflow accepts reviewed shadow mappings; it does not require every mapping to remain blocked. It preserves the existing ShadowEngine constructor and pricing/risk guards, exact $10,000/$100 underlying/$100 combo/$250 fixture limits, pregame scope and delayed Pinnacle policy. Live mode is rejected before runtime initialization. The CLI contains no quote/order submission operation.

## Operator lifecycle (requires separately reviewed mappings)

Use a new output directory and an existing private key file. Preparation normally performs an account inspection; a supplied fresh cached account summary avoids that request. The shared request-budget ledger is reconciled upward and never reset. Preparation is therefore not intrinsically offline.

```
.venv/bin/python scripts/sustained_shadow_supervisor.py prepare \
  --runtime /absolute/path/to/reviewed-shadow.json \
  --out runs/sustained_shadow_NEW --key-file /absolute/path/to/private-key-file \
  --purpose pricing
```

Copy the returned `source_freeze` into the next command. Run within ten minutes of the account retrieval timestamp; preparation requires an account summary at most five minutes old.

```
.venv/bin/python scripts/sustained_shadow_supervisor.py run \
  --out runs/sustained_shadow_NEW --key-file /absolute/path/to/private-key-file \
  --seconds 1800 --code-freeze FREEZE_FROM_PREPARATION
```

`--purpose capture` permits static pricing blockers for a collection-only experiment. `pricing` preparation rejects those blockers; neither preparation mode proves future pricing health. Allowed capture duration is 120–21,600 seconds, with bounded shutdown and postprocessing time added.

The supervisor runs independent runtime creator/shadow workers, Kalshi and applicable Polymarket collectors, and the Pinnacle capture command from a saved source clone. Each is directly supervised in its own process group. Nonzero exit, successful exit more than 0.5 seconds before the requested soak duration, timeout, interruption or changed frozen inputs makes capture incomplete. Workers have ten seconds extra to consume final observations. Stop escalates group SIGINT/TERM/KILL and reaps every direct child; descendants are signaled even if their leader has exited. The supervisor cannot reap grandchildren adopted by the OS, and does not support descendants deliberately escaping their process group.

After stopping, the intact clone alternately drains creator/shadow consumers, archives events and exports review records. Fixed bounded drain passes are checked against the actual event tail; a remaining backlog is reported incomplete, never silently treated as drained. If the saved source/config clone is altered, postprocessing is refused and a failure marker is retained. A restart requires a new output/database and preparation; automatic resume is intentionally absent.

## Freeze and evidence

The freeze includes every local `src/combos/*.py` module, runtime/feed scripts and supervisor/helper script dependencies, plus original and copied runtime/weighting/polling/account inputs. Children execute the frozen clone; both originals and clone are periodically checked. Credentials are never copied into it. Mutable shared budget/cache state is intentionally excluded. Python, third-party installed packages and credential files remain environment dependencies, not byte-frozen package snapshots.

`readiness.json` distinguishes capture completeness from guarded pricing observed. It reconciles actual RFQ event sequence IDs with decision `source_seq` using disk-backed temporary SQLite tables: missing, duplicate, orphan and malformed statuses/modes are explicit failures even if raw counts match. Both consumer cursors must reach the final event tail.

Healthy-pricing evidence additionally requires at least one `shadow_quote` with `mode=shadow`, `fills_assumed=false`, allowed risk/pricing guards, 2–4 pregame legs, all three source venues, positive actual Kalshi and Polymarket depth in each quoted leg's context and finite nonnegative completed processing lag within the configured bound. Invalid quote context or consumer errors prevents that result. Global observation counts alone cannot certify quote health. All-skip, empty and no-depth captures cannot pass healthy pricing. These are observed runtime guard records, not independent proof of exchange payoff equivalence or fee correctness.

Read archived decisions, quote-context invalid reasons, per-RFQ reconciliation, process exit timing, consumer cursors and postprocessing outcomes. `finished.json` hashes the readiness result. The hardcoded zero-order fields describe this shadow-only workflow; they are not account reconciliation or proof that another process did not trade.

## Verification and remaining gates

18 tests pass, including actual EventStore statuses/schema, equal-count duplicate/missing dispositions, nonfinite/missing lag, missing quote context, child failure/timeout/early exit, config changes, descendant termination, shared-budget cached-account preparation, live rejection and a real frozen-runtime **offline** init → synthetic RFQ → drain → archive → export lifecycle. No healthy live pricing has yet been observed with this workflow.

Before a real sustained run: approve exact current mappings and fee semantics separately, resolve Pinnacle units/freshness interpretation, supply credentials and a fresh account reconciliation, then inspect a bounded healthy-input experiment. Validate quote latency, cutoff/invalidation/recovery, canonical risk decomposition, reserve release and creator policy against actual incoming RFQs. Shadow reservations and candidate prices are not accepted fills. Live submit/accept/confirm/cancel, reconciliation and ambiguous-submission recovery remain separate gates. See `WEDNESDAY_SHADOW_RUNBOOK.md` for the underlying prerequisites; its previously missing sustained-supervisor step is implemented here, but live validation remains pending.
