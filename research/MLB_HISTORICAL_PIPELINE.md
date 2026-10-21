# Reusable historical MLB day preparation

`scripts/mlb_daily_cohort.py` converts a complete day produced by
`scripts/mlb_public_day_acquire.py` into the same native cohort schema used by
the exchange collectors and model replays. It does not download the public
tape itself or call OddsPapi.

```sh
.venv/bin/python scripts/mlb_daily_cohort.py \
  --acquisition runs/older_days/daily_acquisition \
  --date 2026-07-01 \
  --out runs/older_days/2026-07-01/cohort \
  --fee-scenario runs/older_days/fee_scenario.json \
  --max-metadata-requests 10000

.venv/bin/python scripts/mlb_exchange_acquire.py \
  --cohort runs/older_days/2026-07-01/cohort \
  --out runs/older_days/2026-07-01/exchange \
  --workers 6 --write-reviewed-mapping

.venv/bin/python scripts/mlb_model_replay.py \
  --cohort runs/older_days/2026-07-01/cohort \
  --exchange runs/older_days/2026-07-01/exchange \
  --out runs/older_days/2026-07-01/replay
```

The command paths above are examples. The batch orchestrator supplies the
actual frozen experiment directories and request budgets.

Before collecting combo definitions, the adapter requires contiguous complete
partition coverage of the entire Chicago calendar day. Every page hash,
request interval, pagination cursor chain and terminal response must agree
with its manifest. Buffered boundary rows are trimmed using half-open time
intervals. Duplicate combo trade IDs must contain identical data. A partial
metadata recovery is cached but cannot emit a complete cohort certificate.
`--max-metadata-requests 0` permits only cached metadata recovery.

All pure MLB prints, including larger and same-game combinations, are retained
in `universe_trades.jsonl.gz`. Full-game pregame candidates feed the existing
replay, which restricts model evaluation to YES-taker, 2–4-leg, distinct-fixture
combinations more than 60 seconds before the earliest original scheduled game
start. Metadata matching does not use outcomes. Missing historical outcomes
remain unknown, including their P&L.

The exchange collector discovers Polymarket events using bounds derived from
native fixture dates. It still validates exact structured start times, teams,
doubleheader identity, payoff prose, lines, selected outcomes, tokens and fee
schema. `--write-reviewed-mapping` exports these automated structural checks;
it does not certify exceptional settlement equivalence or historical fee
effective dates.

## Dated fees

New daily cohorts require an explicit fee scenario. It is copied to
`cohort/fee_scenario.json` and automatically loaded by replay. A CLI override
recomputes combo maker fees as well as leg intervals, so a fee sensitivity does
not accidentally retain the original execution costs. The schema is:

```json
{
  "schema_version": 1,
  "start_at": 1782882000,
  "end_at": 1782968400,
  "reference": "Explicit research assumption; replace with dated source evidence where established",
  "historical_effective_date_verified": false,
  "kalshi_combo_maker_rate": 0.035,
  "kalshi_leg_taker_rate": 0.07,
  "polymarket_rate_policy": "native_market_schedule_unverified",
  "kalshi_rate_overrides": []
}
```

The numeric rates above illustrate an **unverified scenario**, not a historical
fee conclusion. The example timestamps cover July 1, 2026 in Chicago.
An optional `kalshi_rate_overrides` entry supplies `kind` (`leg_taker` or
`combo_maker`), `series`, `start_at`, `end_at`, `rate`, `reference` and `verified`.
Overrides use half-open effective intervals; overlapping entries for one series
and fee kind are rejected. Uncovered decision times are rejected. A fixed
Polymarket sensitivity uses `polymarket_rate_policy: "fixed_scenario"` and an
explicit `polymarket_taker_rate` instead of current native market metadata.
Unverified native Polymarket schedules cannot be marked fully historically
verified. Fee formula/rounding regime evidence still needs review for each
historical window; changing only the rate does not certify those conventions.

## Frozen exchange comparison variants

In addition to Kalshi and Polymarket individually, replay emits
`exchange_blend_equal` and `exchange_blend_pm75`. Their fixed Kalshi/Polymarket
weights are 50/50 and 25/75, applied to each leg before joint pricing. Both
sources must exist for each leg. These are explicit fixed-weight research
variants, not measurements of historical liquidity and not three-source
blends. Pinnacle-dependent models remain unavailable without a valid MLB
historical bundle.

Source windows, fee files, imported pricing code and input histories are hashed
in replay manifests. Point-in-time limitations remain the same as the original
research: publication allowances for minute histories, no historical depth,
current metadata for original scheduled identity, and public observed prints
as capacity scenarios rather than known own-quote fills.
