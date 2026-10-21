# Five-minute integrated NFL shadow run

The300-second capture and390-second decision worker completed successfully. Runtime,
Pinnacle collection, creator/shadow drains, raw archive and review export all returned0.
The capture supervisor elapsed311.90 seconds including collector shutdown; RFQ receipt
span was299.58 seconds. No quote/order transport or actual account allocation occurred.

Independent census/timing audit:103,490 RFQs through source sequence453,244, fully
caught up;1,278 priced candidates (589 two-leg,353 three-leg,336 four-leg).95 research
reservations and1,183 risk rejections. Peak held cash$4,263.946 under the existing
$10k capital/$1k underlying-combo-event caps, point fair+0.3c/combo, assumed-all-fill
and no-release policy. All1,183 risk rejections hit event limits;650 also hit underlying,
49 combo and6 cash (overlapping reasons). Every priced guard multiplier was1.

Priced receipt-to-durable-commit latency: median77.143ms,p99141.045ms,max584.637ms.
Zero priced commits exceeded2s; every decision had a commit receipt. These results
are from a quiet overnight sample, not a busy-game reliability guarantee. The worker
was restarted with unchanged identity; all103,490 decisions and source checkpoint
were retained, zero new batches were added, and risk policies reconstructed exactly.

Creator audit:3,663 creators;47 watch publications and one cooldown across41 creators.
The cooldown's three separated burst windows and one-hour expiry were verified from
raw request evidence. Publication-causal exposure:101,855 clear,1,511 watch,124 cooldown.
All1,278 priced candidates were clear. The124 cooldown RFQs were excluded by creator
policy but were not among priced candidates. There are still no live economic creator
markout groups; no blacklist-related profitability benefit has been established.

Capture orchestration now accepts bounded90–600s windows, with an8GiB free-space
floor and nonzero exit on child/postprocessing failure. Outer orchestration watches
worker liveness and uses interrupt-based capture cleanup. Refresh request budgets
were raised from24 to64 in this run's input configuration to cover five minutes.
Provider usage was freshly reconciled at59 requests before launch. Original mapping
pricing blocks remain present; research pricing explicitly retains payoff, stake-unit,
price-grid and balance-precision assumptions. Disk-floor interruption itself was not
fault-injected during this healthy live run.

Artifacts:
- runs/nfl_five_minute_capture_20260909 (raw/archive/config/process evidence)
- runs/nfl_five_minute_worker_20260909 (decision database, original summary, restart log)
- runs/nfl_five_minute_audit_20260909/verification.json
- runs/nfl_five_minute_creator_audit_20260909
- runs/nfl_five_minute_worker_20260909/restart_risk_verification.json
Prechange capture/audit scripts are in runs/sustained_shadow_setup_20260909.

Remaining: multi-slate and longer-lived state, durable live markouts, private execution
and settlement/balance accounting, acceptable live pricing assumptions and funded
account, and frozen historical validation/parameter selection. August24 metadata
recovery is advancing; three historical dates remain at this check. No held-out
outcome was inspected to tune these settings.
