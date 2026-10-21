# Bounded mismatch recovery

The opt-in shadow snapshot probe now requests a full stream reset on confirmed
REST/WS full-depth mismatch. It rejects that certificate, records affected tokens,
and the collector invalidates venue state before waiting for socket closure. A
fresh connection reconstructs from new subscription snapshots. Per-run REST and
recovery budgets survive reconnects; exhausting the recovery budget terminates the
collector and publishes invalidation. Intervening updates alone do not trigger a
reset. Default maximum recovery count is two; configuration allows zero through five.

41 tests passed across probe, runtime, certificate and causal state logic. A real
40-second Polymarket capture allowed eight REST batches and two recoveries. It
encountered seven full-depth mismatches and one intervening-update rejection,
performed both allowed reconnects, and completed normally with 792 verified checks
from 800 requested token checks. Fresh subscription bootstrap occurred on all three
connections. The terminal recovery-budget branch was unit-tested, not reached live.

Artifacts: `runs/polymarket_resync_capture_20260909`, with runtime, raw event DB,
completion, verification and archived collector source. After that capture, reset
publication was moved ahead of socket close; regression tests passed, but the new
publication ordering has not yet had its own live run.

This first implementation reconnects the entire Polymarket stream. That is a
conservative recovery mechanism and may interrupt otherwise valid markets. The
observed recovery frequency makes targeted per-token resynchronization worth
evaluating before an always-on deployment. No active pricing parameters changed;
normal quoting still has unresolved three-source payoff/liquidity gates.

MLB collection and its validation supervisor remain active. August 16 completed
during this work, leaving August 18, 20, 22, 24, 28 and 30 before held-out evaluation.
