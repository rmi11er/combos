# Live integrated pricing, creator policy, sizing and risk

The120-second capture and135-second worker completed with zero exit codes. The
independent live census/timing audit reconciled all42,879 RFQs through the final
source sequence167,643. Of687 priced RFQs (287 two-leg,249 three-leg,151 four-leg),
75 received research reservations and612 were risk-rejected. All decision batches
have commit receipts, and no priced decision committed after the two-second limit.

Receipt-to-durable-decision latency: median78.160ms, p99 262.398ms, maximum429.261ms.
Integrated computation: median1.178ms, p99 13.419ms, maximum25.590ms. A commit receipt
is written after the decision/checkpoint transaction returns; it records that prior
commit's time. A crash before writing the diagnostic receipt can leave a valid
committed decision without timing evidence, which the audit reports as missing.

This run uses the diagnostic point+0.3c/combo policy,$10k capital and$1k underlying,
combo and event caps. It assumes every admitted quote fills and holds cash for the
entire capture. Peak committed cash was$5,403.42. All612 risk-rejected RFQs hit an
event limit;400 also hit underlying,32 combo and five cash limits. Counts overlap.
These are research reservations, not actual orders or a fill forecast. Fair/payoff,
Pinnacle unit, sampled-grid and account precision assumptions remain unresolved.

Restart reconstructed source and creator state, re-evaluated archived research
policies to rebuild held risk, matched every saved policy decision, and added zero
new rows. The output retained42,879 records. Twelve stale/future receipt exclusions
remain explicitly logged; this run does not establish hour-scale reliability.

The live census/latency audit does not independently rederive fair values or risk
arithmetic; staged arithmetic parity and synthetic restart tests are separate
supporting evidence. No actual balance was replaced with the research$10k figure,
and no quote transport was used.

Storage maintenance reused the existing verified native-compression routine on24
closed completed-capture files, saving426.25MB. Logical bytes and SHA256 values
were checked before/after replacement; file paths and contents remain transparently
readable. No raw data was deleted. Receipts: runs/closed_capture_storage_20260909.
Free space after maintenance was8.895GB, still requiring further capacity planning
for sustained capture. August20 is complete; four historical dates remain pending.

Artifacts: runs/nfl_integrated_live_capture_20260909,
runs/nfl_integrated_live_worker_20260909, runs/nfl_integrated_live_audit_20260909.
Next: sustained shadow orchestration with storage/health limits; execution lifecycle
and account reconciliation; complete frozen historical validation and hyperparameter
selection before live promotion.
