# Explicit Pinnacle delivery-age candidate

`config/runtime_nfl_delivery_candidate.json` is a separate shadow configuration. It preserves the current mappings, risk settings, fee records and payoff-review gates, and opts into `response_delivery_proxy_v1`. The default NFL configuration and historical exchange-only studies are unchanged.

The effective observation time is the earlier of request start and HTTP Date, minus HTTP cache Age and the nominal 30-second delay. The recorded response receipt remains the causal availability time. Native price-change timestamps are retained separately; unchanged prices do not age merely because no new price was published. Cached envelopes retain their original receipt and cannot be relabeled as newly received data.

The candidate rejects requests longer than five seconds, HTTP cache Age above five seconds, HTTP Date lag above ten seconds, dates more than two seconds ahead, missing timing evidence, and malformed chronology. These are explicit research parameters, not verified provider latency bounds. Existing fixture-phase, exact-line, payoff, currency, market activity and venue-disagreement guards still apply.

The policy explicitly assumes that a timely successful response reflects a live upstream snapshot. HTTP delivery cannot establish that assumption by itself. Every observation records `upstream_freshness_validated=false` and `upstream_live_snapshot_assumed=true`. A backend freeze can still return timely HTTP responses; prospective monitoring and comparison with live exchange movements remain required.

The normalizer and collector accept the policy through an optional configuration field. Existing callers retain the prior conservative price-change-age behavior. Thirty-six focused normalizer/freshness tests passed. Applying the timing function to both saved successful OddsPapi odds responses produced effective ages of approximately 30.77 and 30.39 seconds at receipt. This used no new provider requests and did not clear payoff/limit gates.

`config/weighting_sharp_peer_candidate.json` separately gives Pinnacle the same 1.5 score prior as Polymarket and removes its special 20% cap, retaining the common 60% venue cap. Liquidity, spread, age and disagreement adjustments still determine actual weights. This is a hypothesis for matched shadow comparison, not an estimated optimal weight or a promoted live configuration. The existing delayed-feed guards are unchanged.

[Saved-response verification](../runs/morning_research_20260908/pinnacle_delivery_candidate/verification.json) · [Timing implementation](../src/combos/snapshot_age.py) · [Tests](../tests/test_snapshot_age.py)
