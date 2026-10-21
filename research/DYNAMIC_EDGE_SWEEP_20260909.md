# Dynamic edge charge on the latest NFL trace

Ran `scripts/sweep_dynamic_edge.py` over 278 immutable scenario-priced RFQs
from the latest 90-second trace. This is a hurdle sensitivity only; it does not
simulate competitive quote acceptance, fills, inventory or P&L.

With the candidate parameters (0.3¢ base, 2¢ disagreement threshold, $1,000
thin-depth threshold):

| Maximum edge | Mean | Median | 95th percentile | Maximum | Records above 0.3¢ |
|---:|---:|---:|---:|---:|---:|
| 0.3¢ | 0.300¢ | 0.300¢ | 0.300¢ | 0.300¢ | 0 |
| 0.5¢ | 0.316¢ | 0.300¢ | 0.389¢ | 0.399¢ | 82 |
| 1.0¢ | 0.316¢ | 0.300¢ | 0.389¢ | 0.399¢ | 82 |

All 82 adjustments came from the thin-depth component. No recorded combo in
this capture exceeded the disagreement threshold, so the disagreement premium
was not exercised. The cap above 0.5¢ had no additional effect. This is a useful
sanity check: the proposed dynamic model is mostly a thin-depth guard in the
quiet trace, not a hidden source-disagreement tilt.

The result should not be interpreted as proof that $1,000 is the correct depth
threshold. It should be rerun on active windows and grouped by market family,
leg count and eventual acceptance/fill. Parameters remain provisional and no
production policy was changed.

Artifact: `runs/nfl_trace_worker_20260909/dynamic_edge_sweep.json`.
One focused sweep test passes.
