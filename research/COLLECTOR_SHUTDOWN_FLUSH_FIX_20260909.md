# Shutdown RFQ publication delay

The 21 lag-guard exclusions in the creator-ingestion capture occurred in the
final Kalshi batch. Its RFQs were received over 59.8ms around the requested
120-second endpoint. Kalshi's capture timing records 122.003 seconds elapsed,
consistent with its configured two-second WebSocket close timeout. Those RFQs
were published with the collector-stopped events in source sequences 184198–184243.
The first late decision evaluated 10.9ms after the shutdown timing timestamp;
the batch's output commit took about 0.244ms. Earlier decisions remained timely.

Code inspection identifies the delay mechanism: buffered frames were flushed in
the outer collector finally block, after exiting the WebSocket context manager.
Closing the socket can await a handshake before that block executes. This is a
shutdown-specific publication delay, not evidence that those RFQs required two
seconds of pricing computation. These records alone do not explain every other
latency variation in the capture or establish zero importer overhead.

Added `flushing_connection` in src/combos/live_collectors.py. Its finally block
publishes buffered events before the underlying connection awaits closure, for
normal exits and cancellation. Existing final flush and reset events remain.
Three focused tests passed: ordering on normal exit, ordering and propagation on
cancellation, and closing the socket even if flushing fails. A fresh live
shutdown test remains necessary to measure the operational effect.

The original source file is preserved in
runs/collector_shutdown_flush_fix_20260909/live_collectors_before.py and the
recorded timing diagnosis is in diagnosis.json. All 23 frozen historical study
source hashes remain unchanged. Completed worker identities that include every
source module belong to the prior version; do not silently restart those workers
with the changed collector file.

## Fresh live verification

A subsequent 90-second capture with pricing, markouts and persistent evidence
ingestion completed successfully. Kalshi again spent about two seconds closing:
92.004 seconds total. This time the last RFQ completed in 13.63ms, approximately
1.991 seconds BEFORE the collector's shutdown timestamp. The buffered RFQ was
therefore processed during the close handshake rather than after it.

All 33,562 RFQs reconcile; zero hit the processing-lag guard. There were 229 priced
entries, 54 research reservations and 175 risk rejections. Priced receipt-to-commit
latency was 78.18ms median, 138.07ms p99 and 195.38ms maximum. This supports the
specific shutdown fix, not a guarantee across busier sessions.

The markout census is 446 labels (283 observed, 163 unavailable) plus 241 pending,
exactly 229 times three. All labels and source cutoffs reconcile. Markout
horizon-to-commit maximum remains 1.758 seconds; this is a separate source/horizon
scheduling tail and should not be described as fixed by the RFQ flush change.
All 446 new labels were imported into the persistent store, whose 6,360 labels
across four sources reconcile with their availability receipts.

Evidence: runs/nfl_shutdown_fix_worker_20260909/shutdown_verification.json,
runs/nfl_shutdown_fix_pricing_audit_20260909/verification.json,
runs/nfl_shutdown_fix_markout_audit_20260909/verification.json and the worker's
evidence_verification.json. No orders were submitted.

Further markout-tail diagnosis: all 21 labels taking more than 500ms had horizons
after the first collector-stopped event, and all 21 were unavailable. Their next
source-watermark advancement was the Kalshi shutdown timing event. The worker
waits for causal source advancement rather than inventing post-capture prices.
No active-collection markout exceeded 500ms in this sample. Details are retained
in runs/nfl_shutdown_fix_worker_20260909/markout_delay_diagnosis.json.
