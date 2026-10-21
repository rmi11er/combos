# Explicit connection evidence

The live collector now distinguishes local heartbeat emission from upstream
activity. Heartbeats retain last inbound frame age, last data-frame age, matched
Polymarket application-pong age, outstanding ping age and response round-trip time.
Matched application pongs also produce durable `feed_liveness` events.

These fields do not renew book observations or prove per-market synchronization.
Kalshi inbound data is tracked; protocol-level ping/pong acknowledgments managed
inside the WebSocket library are not claimed as explicit application evidence.
Polymarket only has one outstanding application ping, avoiding ambiguous matching
when a response is delayed. An unanswered ping is not hidden by a new send.

24 runtime/liveness tests passed. A 25-second Polymarket-only capture observed two
pong responses, approximately 114ms and 111ms after their requests, with 23 local
heartbeats and no disconnect before the planned stop. Raw evidence and verification
are retained under `runs/polymarket_liveness_20260909`. The tested capture source is
archived there; the subsequent one-outstanding-ping guard does not alter these two
timely response measurements. No OddsPapi requests or exchange mutations occurred.

Next verify quiet book contents through bounded snapshot reconciliation. Connection
responses are useful evidence but cannot replace that check. The 15-second pricing
age limit and native book timestamps remain unchanged.
