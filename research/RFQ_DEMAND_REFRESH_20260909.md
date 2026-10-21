# Demand-prioritized Polymarket verification

An opt-in shadow collector feature now publishes scoped RFQ leg demand from the
Kalshi process and consumes it through the shared event log in the Polymarket
process. Demand expires after 60 seconds, polling is bounded to 2,000 demand rows,
and selection uses only already-published requests. Due demanded quiet books get
priority after eight seconds since their last attempt; up to 20 batch slots remain
available for oldest-attempted exploration. Unused priority slots also explore.

Existing full-depth REST/WS verification, revision/generation checks, request
budgets and mismatch recovery remain. No observation timestamps are renewed by
request selection. The feature defaults off and is enabled by
polymarket_snapshot_verification.demand_priority=true in shadow configuration.

A 35-second read-only dual-collector capture completed both collectors: 355 scoped
RFQ demand publications, seven 100-book verification selections, 697 verified
books and one bounded resynchronization. Selected demanded-book counts were
4,12,29,22,35,24,34. All 160 demanded selections independently had earlier demand
publications; repeated selections are not distinct books. Thirty-three tests pass,
and the 23-file frozen August implementation seal remains unchanged.

This verifies the cross-process mechanism, not an improvement in three-source RFQ
priceability: the short probe had no Pinnacle collector or pricing worker. A
longer combined capture must measure all-leg coverage and priceability using the
same source-age policy. Scope demand is not weighted by creator request frequency,
and no future RFQs are used to prepopulate priority. An actor can still request
many different legs; the exploration allocation and request caps limit, but do
not eliminate, competition for refresh capacity.

Artifacts: runs/rfq_demand_scheduler_20260909. Prechange collector/probe sources are
archived there. Implementation: src/combos/refresh_demand.py, quiet_book_probe.py,
live_collectors.py. No orders submitted or production pricing gates changed.
