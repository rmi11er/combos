# Missing NFL markouts: depth quarantine and freshness

Reconstructed pricing state at the recorded source cutoff for all 371 unavailable
labels in the concurrent three-minute capture. Existing pricing/configuration
hashes were checked; source and model files were not changed.

- 192 labels involve a Polymarket book without a fresh native observation or
  matching snapshot certificate.
- 194 involve an inactive Polymarket observation. Every one is explicitly
  `snapshot_depth_quarantine`, not a closed market or expired fee configuration.
- These two groups overlap on 20 labels, accounting for 366 exchange failures.
- Five labels have missing Pinnacle state after the collector's recorded
  `collector_stopped` reset. They are shutdown-boundary observations, not evidence
  of a provider outage or a future snapshot overwriting a usable one.

The archived raw REST/WebSocket reconstruction reproduced all 91 rejected ladder
comparisons across 50 tokens. In 86 cases the bid and ask prices AND their sizes
matched exactly; only other levels differed. Five affected top-of-book inputs:
four size discrepancies and one ask-price discrepancy (REST 0.54, WS 0.53).
Thus blanket removal of quarantine would admit demonstrably inconsistent pricing
inputs. Conversely, full-ladder equality excludes some cases whose current fair
inputs agree. Rejection counts are not counts of independent markets or missed
fills, and this does not establish whether REST or WS was correct.

Next controlled research comparison: retain the current full-depth baseline and
add a separately identified top-of-book verification candidate. It must verify
both prices and sizes, retain generation/revision and request-time checks, expire
causally, and invalidate on any book update. It must not certify a corrupted full
ladder or permit later deltas to inherit freshness from an old top. Compare
recovered pricing coverage, markout availability and source weights on the same
RFQs before prospective use. Do not infer a profitability improvement merely
from a larger eligible set. Keep real top discrepancies excluded.

The remaining stale-book group needs request scheduling and certificate-lifetime
analysis: market inactivity alone is not evidence of stale prices, but a usable
forward book still needs current depth evidence. Increasing the age threshold
without that evidence is not the proposed fix.

Artifacts:
- runs/nfl_live_markout_missing_diagnosis_20260909_final/summary.json
- runs/nfl_live_markout_missing_diagnosis_20260909_final/details.json
- runs/nfl_live_markout_snapshot_audit_20260909/summary.json
- runs/nfl_live_markout_snapshot_audit_20260909/rows.json

Reusable diagnostic: scripts/diagnose_missing_markouts.py. The existing raw
reconstruction workflow is scripts/audit_snapshot_mismatches.py. Both operate on
completed captures. No new provider requests or orders were needed.
