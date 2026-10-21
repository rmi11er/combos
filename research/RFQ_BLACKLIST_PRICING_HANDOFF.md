# RFQ blacklist handoff to the pricing agent

## Objective and completed scope

Add a cheap creator-ID rejection gate before expensive pricing work is allocated. The offline collector, behavior detector, durable evidence, exports, and nightly schedule are implemented. The quoting engine has not been changed. This is category-independent behavioral screening, not a model of profitability, customer identity, calibrated correlation, or malicious intent.

The passive collector subscribes to Kalshi communications and public trades, records RFQs including selected legs and `msg.creator_id`, and journals raw data with checksums and connection/coverage diagnostics. It submits no quotes or orders and requires no private fills. Blocked creators continue to be collected offline so recurrence and expiry can be evaluated.

## Existing components

Paths below are relative to `../combos`:

| Path | Role |
|---|---|
| `src/combos/rfq_sniffer_capture.py` | Passive WebSocket collector |
| `src/combos/rfq_sniffer.py` | Behavior detection, persistent evidence, expiry, exports |
| `scripts/rfq_sniffer.py` | Capture/run/scan/export CLI |
| `config/rfq_sniffer.json` | Current v2 detection policy |
| `data/derived/rfq_sniffer/evidence_v2.sqlite` | Durable evidence; do not query this in the quoting hot path |
| `output/rfq_sniffer/blacklist.json` | Self-contained integration artifact |
| `output/rfq_sniffer/creators.csv` | Ranked human review |
| `output/rfq_sniffer/evidence.jsonl` | Auditable burst evidence |
| `research/RFQ_SNIFFER.md` | Full operating guide and detector details |
| `research/rfq_flow_design/verify_v2.py` | Independent read-only evidence consistency audit |
| `scripts/rfq_sniffer_nightly.py` | Scheduled dispatcher |
| `scripts/scheduling/` | Shell runner and source LaunchAgent plist |

## Detection policy already implemented

All rate/repetition thresholds below apply within a 60-second creator window:

| Rule | Threshold |
|---|---|
| High rate, watch only | 120 RFQs; never contributes to blocking |
| High rate, block eligible | 600 RFQs |
| Identical parlays | 30 repetitions, without a creator-wide dominance requirement |
| Minor-edit variants | 30 similar requests, with variation, at least 6 legs and 80% overlap against a fixed anchor |
| Large concentrated variants | 10 similar requests with at least 12 legs and at least 60% of legs in groups of 3+ sharing a fixture/event |

Near-match edit allowance is `min(5, max(2, ceil(0.05 * smaller_leg_count)))`, measured as the larger one-sided leg-set difference. Leg identity includes side and scalar settlement values. Concentration uses event/fixture structure as a proxy, not estimated economic correlation. At most 64 recent template anchors per creator are retained, so very diverse similar flow can be undercounted.

Three block-eligible windows separated by at least 60 seconds within 24 hours produce a provisional block, expiring 24 hours after the latest qualifying evidence. Recurrent confidence requires qualifying evidence from two distinct captures, with at least three eligible windows per qualifying period and the configured 30-minute separation; recurrent blocks expire after seven days and renew on qualifying evidence. Replaying a capture does not create recurrence.

Public-trade activity at 60 and 300 seconds is supporting context only. Missing prints never trigger a block and do not establish absence of fills. Coverage gaps and incomplete horizons are censored. Watchlist membership alone must not block a quote.

## Export contract

Read `output/rfq_sniffer/blacklist.json`. Top-level fields:

- `schema_version`: currently `2`.
- `generated_at`: Unix epoch seconds, floating point.
- `policy_version`: detector policy/mapping fingerprint, suitable for provenance logging.
- `creator_ids`: IDs active at export generation time; not a permanent set.
- `entries`: both blocked and expired historical entries.

Relevant entry fields: `creator_id`, `expires_at`, `first_at`, `last_at`, `confidence` (`provisional` or `recurrent`), `reason_codes`, `evidence_ids`, `qualifying_periods`, `active`, `status`, and both trade-context summaries. All timestamps are Unix seconds. `active` and `status` are snapshots evaluated at export time.

Match the RFQ-created message's **`msg.creator_id`** exactly against the exported `creator_id`. Treat this as an opaque string: do not hash it again, lowercase it, or substitute RFQ ID, quote creator ID, or a private account identifier. Missing/empty creator IDs are unknown, not blacklist matches; count them separately.

For a valid loaded v2 export, build an in-memory dictionary from entries that are marked active/blocked and not expired. At each decision, check the entry's **`expires_at > current Unix time`** again. This is necessary even if no file has changed. Both provisional and recurrent entries are currently intended blocks; recurrent-only enforcement would be a separate policy decision.

The producer writes a temporary JSON file then atomically replaces `blacklist.json`. Each other output is replaced separately; there is no cross-file transaction. The export is written before the subsequent independent nightly validation completes. It is not a validation-gated publication mechanism; if that is required, use a completed dated report or introduce explicit promotion rather than assuming the active path has that guarantee.

## Requested quoting-engine integration (not yet implemented)

1. Load and validate the JSON outside the RFQ hot path; periodically check for replacement, e.g. every 30–60 seconds. Swap an immutable in-memory dictionary only after a successful complete parse and schema/type validation.
2. Immediately after decoding the minimum RFQ envelope and creator ID, check the dictionary and expiry. On a match, skip the RFQ **before queueing pricing jobs, fetching market/model data, constructing correlation inputs, or allocating pricing workers**. Submit no quote for that RFQ. Preserve whatever cheap intake logging is needed.
3. Log/counter the RFQ ID, creator ID, reason codes, confidence, expiry, policy version, and export generation time, using bounded or rate-limited logging under spam. Track missing creator IDs, reload failures, file age, and skipped counts.
4. Recommended error behavior: keep the last successfully loaded dictionary on reload failure, while continuing to enforce per-entry expiry. With no valid dictionary at startup, report a degraded blacklist gate and continue the engine's existing risk checks. Missing/stale blacklist data must not silently become a blanket block or an indefinite block. This fallback is a proposal, not existing engine behavior.
5. Add an enforcement switch and an explicit operator allowlist if useful. Shadow mode can measure the impact before enforcement, but it is not currently implemented or a required extra approval step. Preserve existing engine-wide risk controls.

Useful integration tests: exact-ID match skips pricing enqueue; expired entry allows normal processing without a reload; unknown creator does not match; watch-only ID does not block; valid replacement adds/removes IDs; malformed replacement retains the previous valid map; seconds versus milliseconds are handled correctly. No per-RFQ disk or SQLite access is needed.

## Schedule and completed evidence

Installed user LaunchAgent: `local.combos.rfq-sniffer-nightly`. It checks every minute for the 18:00–18:04 America/Chicago window, starts once per Central date, captures 3,600 seconds, then scans, exports, validates, and saves a dated report. DST is explicit. Mac must be awake/logged in at start; missed windows are skipped. `caffeinate` prevents idle sleep during work. Failed attempts are retained rather than retried repeatedly. A 10 GiB free-space preflight prevents starting new captures on a nearly full disk; no retention deletion is implemented.

Nightly state/logs/reports are in `runs/rfq_sniffer_nightly/YYYY-MM-DD/`. Analysis can take hours after capture, and the blacklist changes at export time, not precisely at 19:00. September 8's full job finished September 9 at 00:10 Central. The 18:00 window is an initial sampling choice, not a proven daily volume maximum.

Latest completed September 8 capture: 5,263,297 RFQs and 535,161 public trades, no recorded reconnects/sequence gaps, no missing creator IDs. Combined evidence: 9,261,135 RFQs from 154,471 creators. Export contained **298 active IDs: 286 provisional and 12 recurrent**, evaluated at that export's generation time. Compared with the prior 217-ID export: 270 added, 28 retained, 189 removed/expired. Counts will change with expiry; do not hardcode them.

The original v1 replay cleanup removed 17 rate-only entries under revised rules; original evidence/results were preserved. The revised policy also added structurally qualifying creators. This does not establish that removed creators are benign.

Detector tests, schedule/DST/duplicate-run tests, and the independent evidence audit passed. Latest audit verified all 8,522 flagged windows (6,062 block eligible), recurrence support, expiry, export membership, and both public-trade horizons. Snapshot: `runs/rfq_sniffer_nightly/2026-09-08/report/`. The old `output/rfq_sniffer/policy_comparison.json` is a historical September 7 comparison, not a rolling nightly delta.
