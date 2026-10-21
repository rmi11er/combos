# Live arrival-time three-source candidate pricing

The full120-second capture and135-second durable worker both exited zero. The
worker caught up to source sequence179,655 and independently reconciled every
one of44,865 RFQs to its source identity and receipt timestamp. No missing or
duplicate decisions were found. Restart reconstructed the source prefix and added
no duplicate rows.

The worker priced566 RFQs during collection:246 two-leg,203 three-leg,117 four-leg.
Pricing uses actual evaluation time and only earlier consumed source events. Priced
RFQ receipt-to-compute completion: median75.665ms, p99 131.962ms, maximum180.992ms.
Computation alone: median0.378ms, p99 24.126ms, maximum49.194ms. Every priced result
was timely under the two-second threshold. These timings include source queueing
but stop before output batch commit; they exclude quote sizing and risk decisions.

There were21 lag exclusions. Their receipts span23ms, about0.6s after the requested
120-second capture horizon, consistent with shutdown drainage. This is timing
evidence, not proof all future backlog can only occur at shutdown. They remain
excluded in the recorded worker output.

Mapped-path exclusions included96 exchange coverage failures,11 Kalshi age failures
and four exact Pinnacle selector gaps. Broader universe/scope exclusions remain
fully logged. No quote, acceptance, fill, profitability or blacklist benefit is
inferred. Research payoff, stake conversion, independence, account precision and
sampled-grid assumptions remain; production pricing gates stay blocked.

Next integrate causal creator state, quote sizing and risk reservations into this
worker as separately logged research decisions, then measure commit latency and
sustained restart behavior. Historical and heldout studies remain outstanding;
this operational result does not select production risk limits.

Reusable orchestration: scripts/capture_with_scenario_worker.py.
Independent census/timing audit: scripts/audit_live_scenario_worker.py.
Artifacts: runs/nfl_live_candidate_capture_20260909,
runs/nfl_live_candidate_worker_20260909, runs/nfl_live_candidate_audit_20260909.
