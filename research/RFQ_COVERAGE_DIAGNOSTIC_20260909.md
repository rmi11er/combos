# RFQ-arrival exchange coverage bottleneck

A causal replay examines all 545 mapped candidate RFQs (1,529 leg occurrences,
56 distinct market keys) in the recent 43,003-RFQ capture. It preserves event
ordering and verified-book certificate expiry; it does not backfill observations.

| Exchange availability at RFQ arrival | RFQs |
|---|---:|
| Both exchanges usable on every leg | 169 |
| Only Polymarket missing on one or more legs | 222 |
| Only Kalshi missing on one or more legs | 64 |
| Both have missing legs | 90 |

Of the 169, 167 were three-source priced; two precede Pinnacle availability.
Counts reconcile independently of the original first-failure classifications.
Kalshi has 240 old-timestamp leg occurrences. Polymarket has 464 old-timestamp
candidate failures and one observation not yet available. Positive depth had been
observed; age exclusions do not establish prices were economically stale.

The PM failures are concentrated: DET moneyline appears 78 times, SEA 56 and LAR
43. These repeated leg occurrences are not independent market observations.

The current verifier rotates across all 454 mapped keys, at most 100 books per
request with a minimum five-second interval. With a 15-second freshness window,
rotation alone cannot continuously certify every quiet book, even before latency
and rejected verifications. The candidate RFQs in this capture use only 56 keys.
Prioritizing recent observed RFQ demand is therefore the next implementation task:
maintain an expiring demand set, refresh demanded books before certificate expiry,
reserve some batch capacity for exploration, and retain exact full-depth checks
and resynchronization. Prioritization must use only requests already received;
this hindsight set must not be replayed as though known at capture start.

This capture predates automatic mismatch recovery, so quantify the effect again
with the updated collector. Do not change native timestamps or relax depth checks
to manufacture coverage. Improved coverage is not proof of accepted quotes.

Workflow: scripts/rfq_coverage_diagnostic.py. Outputs:
runs/nfl_rfq_coverage_diagnostic_20260909/{summary,decisions,verification}.json.
