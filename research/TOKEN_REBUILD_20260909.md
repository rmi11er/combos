# Targeted subscription rebuild and verified recovery

Polymarket documents changing asset subscriptions without reconnecting:
https://docs.polymarket.com/api-reference/wss/market
The shadow collector now supports token_rebuild=true alongside token_quarantine.
It sends unsubscribe/subscribe for quarantined tokens, clears only their local
ladders, ignores their deltas until a book snapshot arrives, then requires a new
exact REST/WS full-depth comparison. Other tokens remain subscribed and active.

A rebuild is issued at most once per token per collector process, at most 20 tokens
per batch. It waits for any in-flight verification to complete. Quarantine is
published/flushed before commands are sent. Raw frames remain logged, including
ignored deltas. Missing snapshots or exhausted rechecks leave the token inactive.
There is no subscription acknowledgment guarantee inferred from sending commands;
recovery evidence is the later snapshot plus matched full-depth verification.

The 45-second live probe completed both collectors with 888 verifications, three
rebuild batches covering six distinct tokens, seven quarantine events and two
successful recoveries. Both recovery chains were independently checked:
quarantine -> rebuild request -> later book snapshot -> recovery -> matching
verification certificate. Five quarantine events did not correspond to a recovery
within the short probe; event counts may include repeated quarantine of a token.
This is proof of the mechanism on two live cases, not sustained readiness.

Thirty-eight tests pass, including isolated clearing, delta filtering, one-rebuild
budget, request concurrency and continued quarantine until verified recovery.
Production settings remain unchanged; both features are opt-in shadow settings.
Next run the full three-source capture with these settings and re-evaluate coverage,
latency and per-market downtime without interpreting priceable RFQs as fills.

Artifacts: runs/token_rebuild_20260909 (runtime, events, completion, verification,
prechange source). No Pinnacle requests or exchange orders were made in this probe.
