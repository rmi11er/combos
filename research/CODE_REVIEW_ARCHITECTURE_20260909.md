# Combos code review and architecture plan

Date: 2026-09-09  
Scope: `src/combos`, `scripts`, `tests`, configuration, and the current shadow/backtest workflow.

## Executive assessment

This is a strong research and shadow-trading prototype. The most valuable parts are the fail-closed source validation, explicit fee treatment, immutable pricing observations, append-only event capture, atomic risk reservations, idempotent consumer cursors, last-look checks, and the execution journal’s handling of unknown network outcomes. The code has also accumulated unusually good audit context: source timestamps, policy/config hashes, fair-value components, creator evidence, markouts, and reservation identities are preserved.

It is not yet a maintainable live-trading platform. The main constraints are architectural rather than a single pricing bug:

1. The package is a flat collection of tightly coupled domain modules, while orchestration is duplicated across a large script tree.
2. Configuration and event payloads are mostly untyped dictionaries/JSON blobs, without a schema registry or migration system.
3. Money/risk/fees use `Decimal` and integer fixed-point in some paths and binary `float` in others.
4. SQLite is simultaneously the event log, consumer state, risk ledger, creator store, markout store, and application state. That is excellent for a single-host shadow run but creates locking, migration, and scaling pressure.
5. There is no real exchange mutation adapter or complete sell-side inventory/settlement ledger. The current execution code intentionally stops before live trading.

The right next step is to preserve the existing behavior while introducing explicit domain contracts and ports. A rewrite would throw away the best evidence and create unnecessary model risk.

## What is working well

### Risk and failure handling

`RiskLedger` uses fixed-point 1e-4-dollar units, atomic reservations, explicit reservation states, conservative opposing-side exposure, and deployment-level committed-cap checks. The execution journal records an intent before I/O and leaves a dispatch with an unknown outcome when the transport fails. This is the correct default for an exchange integration where a timeout does not prove that an order was not accepted.

`EventStore` is append-only, idempotent by event key, digest-checks conflicting replays, uses WAL/full synchronous mode, and checkpoints consumers in the same transaction as derived state. `CreatorService` publishes versioned, causal blacklist evidence instead of silently mutating a list.

### Pricing and source provenance

`Observation`, the fee modules, and `weighted_fair` enforce mapping identity, source freshness, fee chronology, Pinnacle delay/age rules, and venue caps. The pricing result carries point, bounds, source components, disagreement state, and risk multiplier. `ShadowEngine` records the full initial pricing snapshot, quote reference, risk context, and later markouts. This is exactly the information needed to improve a “too tight” quoter.

### Scope and promotion safety

The current configuration fails closed on missing creator IDs, stale sources, unknown payoffs, unmapped legs, expired terms, disagreement, and invalid scope. The authoritative configuration is shadow-only with automatic promotion disabled. That separation should remain until execution and settlement evidence are complete.

## Findings, prioritized

### P0 — live deployment is not supported by the current settlement model

`src/combos/settlement_accounting.py:1-6,45-46,83-86` explicitly rejects sell fills and never authorizes capital release. That is appropriate for a safe research gate, but the intended strategy is a maker selling combo contracts. Before any live order can be enabled, the accounting model must support position lots/inventory transfers, buy and sell fills, partial fills, cancellations, netting, settlement, fees, and an auditable cash/risk release decision. The current `ExecutionJournal` is only an intent/reconciliation scaffold; it is not an order adapter.

**Required gate:** implement and test a sell-side inventory ledger and exchange-specific reconciliation before changing `orders_enabled`.

### P1 — derived markouts are created before risk acceptance

In `src/combos/shadow_engine.py:220-232`, `risk.reserve(...)` is called, markout rows are inserted, and only then is a rejected reservation converted into an exception at line 232. A rejected RFQ can therefore leave pending markout rows and update the next-markout scheduler. This can bias fill/markout denominators and make “selected versus rejected” reports harder to interpret.

Move markout insertion and `_next_markout` updates inside the `risk['allowed']` branch, or explicitly label rows as `candidate_rejected` and exclude them from fill-conditional metrics. Add a regression test that a risk-rejected RFQ creates no fill-eligible markout.

### P1 — event schemas and database migrations are implicit

`EventStore` creates tables with `CREATE TABLE IF NOT EXISTS` and stores payloads as compressed JSON (`event_store.py:24-35,48-60`). This is useful for rapid research, but there is no schema version, migration history, payload validator, or compatibility policy. A field rename can silently produce a replay that looks valid but means something different. The same issue appears in risk, creator, markout, and execution tables.

Introduce an event envelope containing `schema_version`, `event_id`, `causation_id`, `correlation_id`, `source_time`, `ingest_time`, `producer_version`, and `config_hash`. Add explicit migrations for SQLite tables and versioned codecs for payloads. Reject unknown major versions and retain old readers for replay.

### P1 — numeric precision crosses unsafe boundaries

Fees, risk limits, and settlement use `Decimal` or integer units, while observations, fair values, quote economics, markouts, and much of the backtester use `float`. For example, `shadow_engine.py:30-40,126-161` converts Decimal grid arithmetic back to floats, and the event layer serializes floats. This is acceptable for statistical modeling but dangerous when a fee-rounded quote or risk cap crosses a one-tick boundary.

Define a numeric boundary: integer fixed-point/`Decimal` for dollars, cents, fees, quantities, limits, and exchange prices; `float` only for probabilities, regressions, and analytics. Use named value types (`Money`, `Price`, `Contracts`, `Probability`) with explicit conversion methods and reject NaN/Infinity at the boundary.

### P1 — flat package and script sprawl obscure dependency direction

`src/combos` contains many large sibling modules (`shadow_engine`, `rfq_sniffer`, `pricing_service`, `live_collectors`, `backtest`, settlement, and provider code). Dozens of scripts modify `sys.path`, import other scripts, or contain machine-specific paths; for example `scripts/fetch_inputs.py:8-13` inserts `../kalshi_mm`. This makes a clean install, isolated replay, and deployment on another host unnecessarily fragile.

Make scripts thin entry points over importable workflows. Put provider integrations behind ports, move orchestration into package modules, remove path insertion, and make the repository installable with a `pyproject.toml` and console scripts. Keep compatibility wrappers for existing research commands during migration.

### P1 — persistence, domain logic, and orchestration are coupled

`ShadowEngine` directly owns SQLite tables, risk reservations, pricing, creator policy, markouts, and event publication. `EventStore` is also the database handle passed to most services. This makes deterministic unit testing possible only by constructing a database and makes it difficult to swap SQLite for a replay store, DuckDB/Parquet research backend, or a production database.

Define repository interfaces (`EventRepository`, `RiskRepository`, `CreatorRepository`, `MarkoutRepository`) and keep the pure decision function independent of storage. A command handler can then atomically persist the decision and state transition. For the single-host runtime, the SQLite implementation can remain the default.

### P1 — source adapters and market identity need a formal registry

The current mapping and pricing code is careful, but provider normalization, selector matching, payoff interpretation, and source freshness are spread across modules and scripts. Pinnacle/Polymarket/Kalshi identifiers, selectors, fixture identity, and payoff semantics should be represented by a versioned `MarketKey`/`LegMapping` registry. A mapping review should produce a signed/hashed artifact consumed by both collectors and the pricer.

This is particularly important for NFL/MLB pivots: the same economic leg can have different provider selectors, periods, lines, and settlement rules. Never let a provider-specific ticker leak into the core pricing API.

### P1 — configuration is not a typed, reproducible runtime artifact

There are many dated JSON configurations and direct dictionary lookups throughout the code. The current manifest hashing is good, but it happens after values have already been interpreted by many callers. Add a versioned `RuntimeConfig` model that validates all fields once, records source/config/code hashes, and emits a complete run manifest. Reject unknown fields and record the exact config used by every output artifact.

### P2 — broad exception handling needs observable semantics

Collectors and shadow sidecars intentionally catch broad exceptions to remain fail-closed, but broad catches occur in runtime and script code as well. Every catch should classify the failure (`transient_source`, `invalid_payload`, `mapping`, `storage`, `policy_sidecar`) and increment a metric/event. Otherwise an apparently healthy shadow run can hide a degraded feed or a disabled research sidecar.

### P2 — operational observability and backpressure are incomplete

The runtime logs heartbeats and events, but it lacks a standard metric set and explicit lag/backpressure policy: ingest lag, queue depth, event write latency, source freshness by venue, decision latency, risk rejection counts, last-look rejection counts, quote lifetime, markout completion, and SQLite WAL size. Add metrics and a watchdog that stops the consumer when event lag or disk usage violates a configured bound.

### P2 — testing is broad but misses production-shaped failure modes

The unit suite covers important fee, risk, creator, delayed-Pinnacle, journal, and reconciliation cases. The missing layers are schema migration tests, property tests for precision/rounding, concurrent writer tests, crash/restart tests around every event boundary, provider contract fixtures, full replay determinism, and an end-to-end shadow run with corrupt/stale/missing source data. Add these before live promotion; do not rely only on more strategy backtests.

### P2 — packaging and quality gates are absent

There is no visible `pyproject.toml`, type-check configuration, linter configuration, or CI workflow. Add `pytest`, `ruff`, and `mypy`/`pyright` gates, plus `compileall` and a clean-install smoke test. Exclude `__pycache__`, run artifacts, and local databases from source control and artifact manifests.

## Target architecture

The package should have one-way dependencies:

```text
domain (pure types and rules)
  -> application (decision/use cases)
    -> ports (interfaces)
      -> adapters (Kalshi, Polymarket, Oddspapi, SQLite, Parquet)
        -> workflows/cli (shadow, collect, backtest, review)
```

Suggested layout:

```text
src/combos/
  domain/
    money.py contracts.py markets.py payoffs.py
    pricing.py risk.py quotes.py creators.py settlement.py
  application/
    quote_decision.py fill_confirmation.py markout.py reconciliation.py backtest.py
  ports/
    market_data.py rfq_feed.py execution.py clock.py repositories.py
  adapters/
    kalshi/ polymarket/ oddspapi/ sqlite/ parquet/
  workflows/
    shadow.py collect.py blacklist.py backtest.py
  cli/
```

The core API should be deterministic and explicit:

```python
PricingResult = pricing_model.price(QuoteContext)
DecisionResult = quote_policy.evaluate(QuoteContext, PricingResult, RiskSnapshot)
```

`QuoteContext` should contain an immutable RFQ, normalized leg mappings, source observations with provenance, fee terms, clock times, and the config hash. `PricingResult` should contain point/bounds, source contributions, disagreement, correlation charge, and explainable blockers. `DecisionResult` should contain the selected price, quantity, edge decomposition, risk requirements, and a typed rejection reason. Persistence and network calls should happen around these pure functions, never inside them.

## Migration plan

1. **Freeze current behavior.** Preserve the current shadow manifest and replay outputs. Add the rejected-markout regression test. Do not change the active historical evaluator while it is running.
2. **Package the repository.** Add `pyproject.toml`, console entry points, a clean-install smoke test, lint/type gates, and remove hard-coded sibling paths.
3. **Introduce typed value objects.** Centralize fixed-point money/price/quantity and convert at analytics boundaries only.
4. **Define domain contracts.** Extract normalized market identity, source observation, pricing result, quote decision, and risk snapshot without changing model formulas.
5. **Split adapters from workflows.** Move provider clients and persistence behind ports; make collectors and backtests thin workflows.
6. **Version the data model.** Add event envelopes, payload schemas, migrations, and artifact manifests. Build replay tests across at least two schema versions.
7. **Separate inventory reconciliation.** Implement sell-side lots, partial fills, cancellation/replace, netting, settlement, and capital release. Add fault-injection tests for every uncertain exchange response.
8. **Only then consider a controlled execution canary.** Keep the current shadow-only configuration, blacklist, freshness/disagreement halts, last-look fair-move check, and automatic promotion disabled until forward fills, markouts, reconciliation, and promotion gates pass.

## Recommendation

Keep the current pricing and risk logic as the reference implementation. Future-proofing should be an incremental boundary exercise, not a wholesale rewrite: first stabilize types, schemas, and package boundaries; then add the sell-side execution/settlement model. The current code is suitable for continued shadow research and replay, but it is not yet safe to call a live market-making system because the inventory and capital-release path is intentionally incomplete.

## Migration work completed in this pass

- Moved markout creation in `ShadowEngine` after successful risk acceptance and added a regression assertion that rejected RFQs create no fill-eligible markouts.
- Added an installable `pyproject.toml`, test configuration, optional development dependencies, and an explicit CLI entry point.
- Added fixed-point domain value objects in `combos.domain` for money, binary prices, and contract quantities.
- Added initial repository protocols in `combos.ports` so future storage adapters do not need to be coupled to the SQLite implementation.
- Added focused tests for the new value objects and reran the critical runtime/execution/settlement suite.
- Hardened the sustained shadow supervisor’s macOS process-group cleanup and refreshed the locked candidate hash after the intentional runtime change.
- Added an additive `events.schema_version` migration with backward-compatible replay behavior and tests for old databases and conflicting event versions.
- Added an isolated signed inventory ledger in `combos.inventory_ledger` covering buy/sell fills, short positions, settlement cash flows, idempotency, and an explicit ownership gate before capital release.
- Added provider-neutral market-data and execution protocols under `combos.ports`.
- Added an offline [`shadow_preflight.py`](../scripts/shadow_preflight.py) command that fails closed on live mode, enabled orders, automatic promotion, missing source configuration, and low disk capacity.
- Added an explicit creator policy gate: shadow mode prices blocked creators counterfactually; live mode returns before pricing.
- Added [`shadow_session_report.py`](../scripts/shadow_session_report.py), which emits a summary, decision-edge data, and a six-panel visual review bundle covering outcomes, edge, cumulative hypothetical edge, markouts, disagreement, and rejection reasons.

The remaining phases—event schema migrations, provider adapters, and sell-side inventory reconciliation—should be done as separate reviewed changes because they alter replay and capital-accounting semantics.
