# Continuous research runtime

This implements the first infrastructure milestone in `NFL_LAUNCH_PLAN.md`:
independent collectors, a creator/blacklist service, continuous shadow decisions,
atomic risk reservations, later markouts, and raw data archival/replay. It has
no live quote/order submission adapter. Pinnacle is an input boundary awaiting
the user's historical/live provider selection.

## Processes and state

`scripts/runtime.py` runs three independently restartable roles:

- **Collectors:** Kalshi communications, public trades, multivariate lifecycle
  and selected order books; Polymarket market-stream books for configured tokens.
  Original messages remain in the event log even when pricing metadata is absent.
- **Creator monitor:** persistent RFQ deduplication, rolling duplicate-leg-set
  detection, aggregate creator features, cooldowns, overrides and policy history.
- **Shadow engine:** one disposition per captured RFQ event; reviewed mapping,
  strict three-venue fair, optional actual combo-book comparison, quote proposal,
  capital/contract checks, reservations and later markouts.

A SQLite WAL database holds compressed immutable events, consumer offsets,
indexes and risk state. The synchronous durability setting is FULL. A consumer
commits its outputs and input checkpoint atomically. Process locks prevent two
copies of the same consumer from operating on one database. The quoter waits
for the creator consumer's evidence watermark, then reads the policy state
preceding the current RFQ's source sequence. It never performs a remote lookup
on the quote path. Later blacklist changes do not alter earlier decisions.

Use this deployment on one host with a local filesystem. It is not a distributed
message broker or a network-filesystem database. Configuration is pinned per
consumer: changing risk/model/mapping settings requires a separately named
experiment database. Ordinary restarts with the same settings retain offsets,
blacklist history and reservations. A future live adapter must reconcile actual
positions before starting; creating a fresh experiment is not live risk recovery.

## Start, inspect and stop

The shipped `config/runtime.json` intentionally has empty reviewed mappings and
combo fee/grid metadata, and unset risk caps. Capture and creator monitoring
work with it; strict quotes remain excluded until the required inputs exist.
No arbitrary live risk limit or Pinnacle weight is substituted.

For NFL Week 1, `config/runtime_nfl_week1.json` now contains 299 exact exchange
outcome mappings and verified fee/grid samples. See the
[mapping review and refresh commands](NFL_MAPPING_REVIEW.md). It collects both
exchanges while explicitly gating pricing on Pinnacle payoff review. Fee
metadata expires after 24 hours or the next scheduled change. Refresh before
the intended session rather than reusing this snapshot indefinitely.

```sh
.venv/bin/python scripts/runtime.py --db runs/nfl_session_001/events.sqlite init
.venv/bin/python scripts/runtime.py --db runs/nfl_session_001/events.sqlite run --seconds 3600
.venv/bin/python scripts/runtime.py --db runs/nfl_session_001/events.sqlite status
```

`run` supervises separate OS processes, propagates a failed child, and stops its
children on interruption. It also starts Polymarket when token mappings exist.
The requested collector duration is followed by up to ten seconds of consumer
draining. Per-service stdout/stderr go to files adjacent to the database. All
live smoke-test processes were bounded; these commands do not install an
unattended launch or scheduled trading job.

Durations now use both monotonic and calendar deadlines because macOS sleep can
pause the monotonic clock. Collector shutdown records both elapsed times.
Initialization saves source text and hashes; service startup requires matching
code, runtime configuration and weights. For an old experiment, use its saved
source snapshot. Read-only status, archive and review commands remain available
after source changes.

For independent operation in separate terminals:

```sh
.venv/bin/python scripts/runtime.py --db runs/nfl_session_001/events.sqlite worker creators --seconds 3600
.venv/bin/python scripts/runtime.py --db runs/nfl_session_001/events.sqlite worker shadow --seconds 3600
.venv/bin/python scripts/runtime.py --db runs/nfl_session_001/events.sqlite collect kalshi --seconds 3600
.venv/bin/python scripts/runtime.py --db runs/nfl_session_001/events.sqlite collect polymarket --seconds 3600
```

Kalshi collection uses `KALSHI_API_KEY_ID` and `KALSHI_PRIVATE_KEY_PATH` only for
WebSocket read subscriptions. Polymarket public market data needs no credentials.
There are no order/quote mutation commands in either collector.

`status` reports offsets/lag, decision counts and rejection reasons, reservation
states, database size and WAL size. Offsets refer to the shared event stream,
including derived events; they are not counts of unique RFQs. All decisions and
source data are retained; printing every RFQ to the console is avoided.

## Capture coverage and timestamps

Configured Kalshi legs remain subscribed. The collector also discovers NFL
2–4-leg full-game RFQs, retaining up to 100 recently requested combo books and 200 unmapped
NFL leg books by default. It uses a 60-second activity window and replaces older
subscriptions with more recent candidates. This is explicitly bounded book
coverage, not the entire combo book universe. Broad RFQ/trade/lifecycle capture
continues independently. Subscription commands, cap/candidate counts, empty
books, evictions and reconnects are recorded.

Each Kalshi subscription's sequence is checked. Book deltas require a snapshot;
negative depth or crossed state forces reconstruction after reconnect. Live
empty snapshots can omit both price ladders; this was verified empirically.
Polymarket changes replace a level's absolute size, whereas Kalshi deltas add to
the previous size. Polymarket's market stream has no equivalent sequence check
in this adapter; connection failures cause full resubscription and fresh books.

Late updates for retired subscriptions remain in the raw log and are explicitly
excluded from book reconstruction. A re-added market requires a fresh snapshot.
This avoids unnecessary full-feed reconnects during normal subscription churn.

The live test measured exchange timestamps approximately 40 ms ahead of the
host's receipt clock. The normalizer preserves `source_observed_at` and the
measured positive offset, allows at most 250 ms ahead, and conservatively uses
`min(source_time, receipt_time) - 250 ms` for pricing freshness. An excessive
offset makes the observation inactive without interrupting raw capture. Raw
timestamps are never rewritten. This explicit clock allowance is a provisional
normalization policy, not a latency measurement or assurance of synchronized
clocks. Receipt time means when the application dequeued the message.

Disconnect/stop events invalidate the venue's normalized observations. Future,
inactive or stale inputs are rejected by the strict fair. Missing fee metadata
prevents normalization while raw books remain archived. Snapshot/delta schemas
are based on the current [Kalshi book feed](https://docs.kalshi.com/websockets/orderbook-updates)
and [Polymarket market stream](https://docs.polymarket.com/market-data/realtime-data).

## Feed adapter and mapping contract

The separate `scripts/oddspapi_feed.py` v4 REST recorder now implements batch
polling and exact reviewed selectors. Account inspection redacts returned keys.
Use the [launch plan](NFL_LAUNCH_PLAN.md) for commands and current blockers;
tournament IDs, subscription boundaries and paired outcome/limit/payoff evidence
remain required. The generic event contract below is also supported.

The provider adapter should emit JSONL event envelopes with:
`kind`, `source`, `received_at`, `event_key`, and `payload`. Event keys must be
stable for retries; reusing a key for different content fails. A Pinnacle adapter
can pipe records to:

```sh
.venv/bin/python scripts/runtime.py --db runs/nfl_session_001/events.sqlite publish -
```

Use `kind: "external_raw"` to retain provider payloads, `kind: "observation"`
for normalized complete two-sided snapshots, and `kind: "venue_reset"` with
`{"venue":"pinnacle","reason":"disconnected"}` when that feed loses validity.
Periodic `heartbeat` events support expiry/markout processing. The `publish`
command also accepts a file path. `Observation.from_record` validates normalized
prices, chronology, fee references and comparable payout capacity. Normalized
records should reference their raw event keys.

Do not promote historical download times to historical availability times.
Pinnacle quote pairing, limit currency/units, source update semantics and mapping
must be verified when the provider arrives. This runtime does not invent a
Pinnacle WebSocket URL or assume the historical vendor also supplies a live feed.

Each reviewed mapping in the runtime configuration needs:

```json
{
  "market_key": "canonical-payoff-key",
  "fixture_key": "canonical-game-key",
  "sport": "NFL",
  "start_at": 1788999600,
  "mapping_reference": "reviewed-rule-and-outcome-evidence",
  "kalshi_ticker": "EXACT_KALSHI_TICKER",
  "polymarket_yes_token": "CANONICAL_YES_TOKEN_ID",
  "fees": {
    "kalshi": {"rate": 0.07, "reference": "VERIFIED_EFFECTIVE_FEE_VERSION"},
    "polymarket": {"rate": 0.05, "reference": "VERIFIED_MARKET_FEE_VERSION"}
  }
}
```

This is a schema illustration, not a verified NFL mapping or fee recommendation.
Canonical YES must match Kalshi YES and the selected Polymarket token exactly.
Normalized external observations must use the same mapping reference. The
initial phase classifier uses the configured start time; actual kickoff delays,
halts and game-state transitions need a validated live state source before
in-play execution. Eligibility requires 2–4 distinct mapped fixtures and full-game moneyline, spread or total markets.

`combo_terms` maps ticker prefixes to reviewed `maker_fee_rate`, `fee_reference`
and `price_ranges` (`start`, exclusive `end`, `step`). The longest matching
prefix wins. Neither yesterday's CFB fee nor an arbitrary tick grid is silently
applied to NFL. Configuration ranges describe this adapter's grid contract;
provider definitions must be translated and verified.

## Quoting and risk semantics

The initial engine offers only the maker-NO side, equivalent to selling the
customer combo YES. It selects the lowest valid YES ask meeting the configured
net edge above a fee-expanded, correlation-stressed upper fair. The default rho
0.05 is an explicitly provisional pairwise ceiling, not an estimated dependence.
For three/four legs, a joint-state linear program leaves higher-order dependence
unrestricted within the pairwise moment bounds; the resulting reserve is logged
separately. See [the current launch plan](NFL_LAUNCH_PLAN.md).
There is no ticket cap or probability filter.

Fixed-count RFQs retain their requested size. Target-cost RFQs use a labeled
shadow upper bound `ceil(target_cost / YES_ask)` before customer fees. This avoids
under-reserving under that sizing assumption, but is not a verified exchange
contract count or fill quantity. An execution adapter must reconcile actual
derived counts and deadlines. Requests are never silently clipped to remaining
cash; if the full modeled size cannot fit, the decision is excluded.

Risk reservations use integer ten-thousandths of a dollar. The portfolio counts
each commitment once; each involved canonical underlying contract and fixture
is conservatively charged that combo's full maximum loss. Equivalent combo
leg sets share a risk bucket across different tickers. Positive edge does not
override any cap. The per-contract, per-combo and per-fixture dollar limits must
be configured for a reserved shadow quote.

Hypothetical offers expire after the configured lifetime or cancel on RFQ
deletion/blacklist changes. No fills are inferred. Explicit `simulation_fill`
and `simulation_settlement` inputs exercise the separate simulation ledger;
filled simulations retain capital through quote expiry and release it only at
settlement. These events are never described as actual account fills.

## Creator policy and review

The initial spam policy requires at least 30 distinct RFQs in 60 seconds, at
least 80% with the same leg set, and three separated bursts before a one-hour
cooldown. The monitor records raw IDs, cumulative counts, evidence, policy
versions and prior/new states. Heartbeats log cooldown expiry even without a
new request from that creator. Long-leg counts remain context. The first stage
does not automatically label correlation pickoffs.

Observed 5/30/120-second markouts are stored with available input references.
Unavailable/stale horizons are labeled missing after a grace interval. Positive
`adverse_move_cents` means the combo fair rose against the maker-NO side. The
current benchmark uses the same three-venue fair, so labels remain diagnostics;
they cannot automatically blacklist a creator. The monitor groups this evidence
by fixture pair and horizon to avoid counting duplicate requests as independent
proof. An independent benchmark and calibrated toxicity thresholds remain work
for research, not prerequisites to logging the evidence.

Explicit `creator_override` input supports clear/watch/cooldown/blocked state.
It requires creator ID, reason, evidence references and a future expiry for a
cooldown. Every override is itself archived, and applies prospectively.

```sh
.venv/bin/python scripts/runtime.py --db runs/nfl_session_001/events.sqlite export-review --out runs/nfl_session_001/review_001
```

The review directory contains decision contexts, blacklist transitions,
markouts, risk transitions, feed resets, errors, a status summary and hashes.
`decisions` in SQLite is a compact index pointing into the compressed event log;
it is not a second uncompressed copy of each request. A retained synthetic
example under `runs/runtime_synthetic_demo_20260906/` demonstrates quoting, a
contract-limit rejection, markouts, expiry and a creator block. It contains no
real trading results.

For large sessions, `scripts/review_runtime.py --db runs/nfl_session_001/events.sqlite
--out runs/nfl_session_001/review` produces compact health/coverage metrics and
creator evidence with reconstructed rolling windows. It reads the event log
without duplicating every decision as uncompressed JSON. Run it after the
collectors stop and consumers drain for final completeness checks; an in-progress
snapshot can legitimately contain RFQs whose decisions occur after its cutoff.

## Archives, replay and operating limits

```sh
.venv/bin/python scripts/runtime.py --db runs/nfl_session_001/events.sqlite archive --out /path/to/archive/session_001
.venv/bin/python scripts/runtime.py --db runs/nfl_replay_001/events.sqlite restore-inputs /path/to/archive/session_001
.venv/bin/python scripts/runtime.py --db runs/nfl_replay_001/events.sqlite replay --seconds 3600
```

Archives use independently compressed 10,000-event chunks with hashes, row
counts, an upper sequence watermark and configuration/source-code provenance.
Restoration checks every chunk and event digest, atomically imports original
inputs into an empty database, and regenerates derived decisions/policy state
through the services. Replay uses event time and disables real-time backlog
rejection; execution wall-clock latency therefore is not reproduced. Preserve
the recorded live decisions when assessing live latency exclusions.

Archives do not currently prune the hot SQLite database or upload themselves to
cloud storage. An always-on host, periodic archive scheduling, off-host retention
and bounded hot-state compaction remain deployment tasks before a multi-day run.
At the measured whole-universe traffic rate, storage is substantial: one
30-second sample produced about 19 MB of compressed event archives. Extrapolation
to a day is about 55 GB if that rate persisted; it is not a measured daily total.
Do not provision a multi-day laptop run on the assumption that these are small
logs. The collectors use no database retention policy that could silently erase
research data.

Tests cover transaction rollback, event conflicts/deduplication, causal creator
watermarks, cooldown/expiry and restart, concurrent reservations, capital release,
full-size rejection, feed invalidation, book reconstruction, clock offsets,
markout timing, archive corruption, and deterministic quote/risk replay. Live
validation covers Kalshi collection and independent consumer throughput. The
Polymarket adapter now also has live verification for 299 mapped NFL contracts.
Three-venue pricing still requires the chosen Pinnacle feed and payoff review.

An earlier 60-second integration run recorded 43,148 RFQs and exactly 43,148
decisions, 8,382 public trades, 329 book snapshots and 908 book deltas. Both
consumers drained to zero event lag. It had one successful connection and no
unplanned reconnect; the two venue-reset records were startup and shutdown.
Application decision lag was approximately 129 ms median and 215 ms at the
99th percentile. Forty-three requests exceeded the two-second lag cutoff;
these remain explicit exclusions. This benchmark included missing-mapping
decisions, not full three-venue pricing at that traffic rate. Evidence is in
`runs/runtime_acceptance_20260906/validation.json`. The complete suite passed
35 tests, and the existing September 5 accounting verifier still passed.
