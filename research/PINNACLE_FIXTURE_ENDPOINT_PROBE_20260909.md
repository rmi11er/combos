# Exact alternate-line endpoint check

The documented v4 tournament and fixture odds endpoints expose bookmaker and
verbosity parameters, but neither documents a switch that requests extra alternate
lines. The current collector already requests verbosity 3. Sources:
https://oddspapi.io/en/docs/get-odds-by-tournaments
https://oddspapi.io/en/docs/get-odds

Two budget-accounted read-only GET /v4/odds probes used the configured pinnacle+30
bookmaker, verbosity 3 and decimal odds. The existing catalog/native-identity matcher
still found no exact LAC spread 6.5 or JAC spread 4.5. Raw responses are cached under
runs/pinnacle_fixture_endpoint_probe_20260909 and
runs/pinnacle_fixture_endpoint_jax_probe_20260909. The latter uses provider code JAX,
which the reviewed mapper canonicalizes to JAC.

These probes occurred after the earlier tournament capture. They establish absence
in both sampled fixture responses, not simultaneous endpoint equivalence, universal
provider absence, or an entitlement diagnosis. Adding recurring fixture requests
has no demonstrated coverage benefit from these tests. Ask provider support about
alternate-line availability with these concrete fixture/line examples before
building an expensive per-fixture polling fallback. No nearby-line substitution,
new subscription purchase or external message was made.
