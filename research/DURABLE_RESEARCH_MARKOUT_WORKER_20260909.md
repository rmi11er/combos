# Durable markout follower

MarkoutWorker follows source events plus committed candidate decisions. It pauses
before an RFQ whose decision is not yet available, schedules priced candidates at
their actual pricing evaluation time, and atomically writes labels, pending-horizon
changes, consumed-decision hashes and source checkpoint. It never changes creator
policy. Labels retain the market-data cutoff separately from computation time;
commit-return receipts are diagnostic, and consumers must use actual committed-row
visibility for publication causality.

Restart reconstructs market state from the verified source prefix, checks every
previously consumed decision hash, and loads pending horizons. A failed transaction
poisons the in-memory worker until reconstructed. Pending horizons persist when the
source has no later events; stopping a bounded worker does not label them missing
or settle them at an invented future price. One writer is enforced by a CLI lock.

Seven focused tests pass: delayed decision arrival, pending restoration, horizon
lookahead prevention, missing prices, duplicate entry, changed decision rejection,
and injected label-write rollback/recovery. Complete five-minute-capture run consumed
source sequence453244 and produced3360 labels (3028 observed/332 unavailable), with
474 pending horizons.3360+474=1278 priced candidates*3 horizons. Restart reconstructed
the same source checkpoint, label counts/statuses and pending counts without adding
labels. This run followed completed data; concurrent live deployment of this new
worker remains to be exercised with the capture launcher.

CLI: scripts/run_markout_worker.py. Module: src/combos/markout_worker.py.
Outputs: runs/nfl_durable_markouts_20260909. Labels are research evidence, not fills,
realized P&L or automatic toxicity determinations. Durable multi-capture creator state
and integration of markout evidence into grouped creator review remain outstanding.
