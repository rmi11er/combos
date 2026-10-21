# OddsPapi Pinnacle limit semantics audit

The captured NFL payload contains numeric `limit` values for all 4,220
Pinnacle outcomes reviewed in the existing five-snapshot audit. It contains no
currency, unit, or stake-versus-loss indicator. The audit is archived at
`runs/nfl_pinnacle_limit_audit_20260910.json`.

The current provider materials are not internally sufficient to certify the
field for risk weighting:

- The v4 historical-odds documentation describes `limit` as the maximum stake
  allowed for an outcome and shows it as a numeric field.
- An OddsPapi provider article separately says Pinnacle limits can represent
  the bookmaker's maximum loss, with the customer stake varying by decimal
  price.

Those statements imply different transformations for a liquidity score and
for a hard risk limit. We therefore retain the locked policy's fail-closed
behavior. We must obtain a written provider clarification, or validate the
semantics against a controlled Pinnacle account response, before using the
field as USD stake/depth. The existing `shadow_assume_usd_limits` option is
research-only and is not part of the canonical runtime.

The same audit confirms that the numeric field is present, so this is a
semantic certification problem rather than a missing-data problem. Historical
endpoint availability is a separate issue: the current account's probe of a
reviewed January NFL fixture returned HTTP 404 even though the public v4 docs
describe historical coverage. That result remains archived as
`runs/nfl_oddspapi_history_probe_20260910/summary.json` and should be resolved
with the provider before relying on NFL historical Pinnacle replay.
