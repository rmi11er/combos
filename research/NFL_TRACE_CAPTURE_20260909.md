# Live venue-component trace verification

Completed a fresh 90-second three-source capture with
`record_venue_components=true`, concurrent pricing, horizon evaluation and
persistent creator-evidence ingestion. Both pipeline and importer returned zero;
collector archive/export steps also passed. Three Pinnacle snapshots were
retained; account usage before capture was 82 requests. No orders were sent.

The independent pricing audit reconciles every one of 37,646 RFQs to the final
162,014-event checkpoint. 278 were priced: 141 two-leg, 66 three-leg and 71
four-leg. Research allocation admitted 81 hypothetical reservations and rejected
197 for risk. These are not live quotes or fills. All priced decisions had a
durable commit receipt: median 79.97 ms, p99 138.75 ms, maximum 164.72 ms.

The horizon audit reconciles 278 times three horizons to 381 observed labels,
132 unavailable and 321 pending beyond the source window. No receipts are
missing and all source cutoffs match. Horizon-to-commit p99 is 1.323 seconds,
maximum 1.847 seconds; the shutdown-versus-active timing split has not yet been
diagnosed for this run, so no active-session tail-latency claim is made.

All 513 completed labels were ingested exactly into the persistent evidence
store (now 6,873 labels across five source identities). Computed-to-confirmed
availability was median 646 ms, p99 1,180 ms, maximum 1,212 ms for this new source.
No economic creator sanctions were applied.

Replay checks the actual logged venue-component payloads as well as baseline
prices, rather than merely adding traces retrospectively. All 37,646 baseline
records and 381 observed marks reproduce exactly. Price attribution is again
zero throughout; freshness changed in every mark, depth in 148, spread in 238,
with 142 marks changing only freshness among recorded score inputs. This is
quiet-window infrastructure evidence, not predictive or profitability evidence.

The consensus price screen appears in 200 of 278 RFQs (212 passing leg
occurrences of 764). As before it is a descriptive screen, not activation of the
gated consensus pricing module. Production mapping blocks remain in force.

Artifacts:
- `runs/nfl_trace_capture_20260909`
- `runs/nfl_trace_worker_20260909`
- `runs/nfl_trace_pricing_audit_20260909/verification.json`
- `runs/nfl_trace_markout_audit_20260909/verification.json`
- `runs/nfl_trace_worker_20260909/evidence_verification.json`
- `runs/nfl_trace_attribution_20260909`

During this work the August30 cohort's first attempt terminated with public
request retry exhaustion. Existing recovery supervisor 57439 retained its
failure receipt and launched batch 60502 for the second permitted attempt;
validation supervisor 57443 continues waiting. No duplicate collector was
launched and no attempt count was reset.

## Reusable shutdown timing diagnosis

`audit_markout_worker.py` now includes collector stop receipts, timing summaries
on either side of the first receipt, and each >500 ms label's first source
watermark beyond its horizon. It uses cumulative source watermarks, preserving
the worker's ordering when event receipt timestamps are not monotonic.

The trace capture's 480 pre-stop labels have median computation delay 64.91 ms,
p99 140.55 ms and maximum 167.76 ms. There are 33 post-stop labels. All 15 labels
over 500 ms fall after the first stop receipt, are unavailable, and have a
`capture_timing` event as the first watermark beyond the horizon. Stop receipts
can follow socket shutdown, so these categories are descriptive and do not
independently certify active source health.

The full census/cutoff audit reran successfully with the new diagnostic;
four existing markout worker/launcher tests also pass. Result:
`runs/nfl_trace_markout_timing_audit_20260909/verification.json`.
