# Dynamic edge buckets versus observed markouts

Joined the dynamic-edge classification to all 381 observed labels from the
latest trace. The join is by the durable decision sequence and drops no-label
records; it does not invent fills or acceptance. The result is descriptive and
same-window only.

| Horizon | Base labels | Mean adverse move | Widened labels | Mean adverse move |
|---:|---:|---:|---:|---:|
| 10s | 129 | +0.0034¢ | 40 | +0.0013¢ |
| 30s | 105 | +0.0011¢ | 34 | +0.0090¢ |
| 60s | 53 | +0.0013¢ | 20 | −0.0034¢ |

The widened bucket is not uniformly more adverse: it is lower at 10 seconds,
higher at 30 seconds and negative at 60 seconds. The 30-second difference is
driven by only 34 labels and the entire sample is a quiet, overlapping window
whose fair changes are mostly liquidity-weight movement. There is no evidence
here to fit the dynamic charge or to claim toxicity. It does suggest that a
simple thin-depth markup should remain a shadow feature until active windows
provide fill-conditioned, independent evidence.

All hypothetical quote/fill counts remain zero. Artifact:
`runs/nfl_trace_worker_20260909/dynamic_edge_markouts.json`. One focused test
passes for durable joining and no invented fills.
