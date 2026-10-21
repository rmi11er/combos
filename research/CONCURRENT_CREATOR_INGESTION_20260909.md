# Concurrent capture through persistent creator evidence

A new 120-second NFL shadow capture ran with pricing, durable markouts and the
persistent evidence importer concurrently. `scripts/capture_with_creator_evidence.py`
waits for a committed markout checkpoint before starting ingestion and supervises
both children through bounded completion. Capture cleanup, archive/export,
pricing, markouts and importer all exited successfully. No orders were submitted.
Provider account usage was freshly reconciled at 75 requests before starting.

Audits reconcile all 45,009 RFQs through source sequence 184,264. There were 366
priced entries (201 two-leg, 96 three-leg, 69 four-leg), 74 assumed-fill research
reservations and 292 risk rejections. Priced receipt-to-commit latency was 79.61ms
median, 176.43ms p99 and 227.08ms maximum. No priced decision exceeded two seconds.

There were 21 processing-lag/future-receipt guard exclusions over a 59.8ms RFQ
receipt span. Six had 2–4 legs; that alone does not establish full pricing
eligibility. The maximum all-RFQ completion lag was 2.078 seconds. This tail needs
root-cause and busy-session investigation; the run does not prove latency was
unaffected by the importer. No controlled concurrent-versus-disabled comparison
was performed.

The markout census is 835 labels plus 263 pending horizons, exactly 366 times
three. Labels comprise 678 observed and 157 unavailable. Source cutoffs and
decision identities passed. Horizon-to-commit-return latency was 65.75ms median,
731.28ms p99 and 1.860 seconds maximum.

All 835 new labels reached the evidence store with matching payloads and timing.
Computation-to-confirmed-availability latency was 573.47ms median, 1.181 seconds
p99 and 1.238 seconds maximum. This measures evidence ingestion, not quote latency.
A concurrent as-of review succeeded while importing. The final audit also
reconciles both earlier captures, for 5,914 stored labels and availability receipts.
Restart added zero labels and preserved the hashes of every evidence and
availability row. Original completion status is retained before restart.

Artifacts:
- runs/nfl_creator_ingestion_capture_20260909
- runs/nfl_creator_ingestion_worker_20260909 (completion, evidence audit, restart,
  concurrent review and lag-guard records)
- runs/nfl_creator_ingestion_pricing_audit_20260909/verification.json
- runs/nfl_creator_ingestion_markout_audit_20260909/verification.json
- runs/nfl_persistent_creator_evidence_20260909/evidence.sqlite

The existing full-depth pricing baseline and all mapping blocks remained in use.
Top-only research certificates were not promoted to this run. Creator evidence
was retained without economic sanctions. Forecast calibration, acceptance,
funding/execution lifecycle and held-out parameter selection remain incomplete.
