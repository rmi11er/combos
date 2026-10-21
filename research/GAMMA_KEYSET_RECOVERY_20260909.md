# Historical collection recovered from Gamma offset ceiling

August24 cohort recovery completed, then exchange acquisition failed because Gamma
GET/events rejected offset2100 with422: offset too large, use/events/keyset. This
was not an allowlisted transient failure. The recovery and frozen-validation
supervisors stopped, and their process handles were confirmed absent before recovery.

The official keyset endpoint supports the same filters and next_cursor/after_cursor
pagination. A bounded23-page read recovered2201 events under the exact original
series/date filters; all2100 prior successful-page event IDs remain present. Every raw
HTTP response is retained. The adapter materialized local100-item cache slices;
all2201 items/order exactly match the complete raw keyset scan. These are explicitly
labeled derived cache results, not asserted HTTP200 responses from the legacy URL.
Original cache files including the422 envelope are preserved in original_cache.
The failed-envelope manifest points to its preserved copy and validates its SHA256.

No frozen acquisition/pricing code, candidate definition or outcome-dependent rule
was changed. The adapter installed only these query-specific cache representations
while holding the batch lock, and verified hashes after installation. Its purpose is
to feed the existing cache interface using documented source provenance. All23 frozen
validation source hashes remain unchanged. Raw pages, manifests and the exact adapter
source used are in runs/gamma_keyset_recovery_20260909/materialization.

Resumed same batch command/request budgets as PID53682; new recovery supervisor53684
and frozen validation supervisor53688. All three were verified live, and August24
exchange acquisition is running. Original stopped supervisor evidence remains intact;
new monitoring plans/status files are under runs/gamma_keyset_recovery_20260909/resumed.
No held-out outcomes were inspected or used to tune the repair. Future deep catalog
queries may require the same explicit cache materialization; the legacy network loop
itself remains frozen.

Sources:
https://docs.polymarket.com/api-reference/events/list-events-keyset-pagination
https://docs.polymarket.com/changelog
