# Inventory-aware shadow deployment

The default `scripts/run_shadow.py` configuration now enables the inventory
policy in `config/runtime_nfl_authorized_shadow_20260910.json`. This is a
shadow deployment of the runtime model, not live-order authorization.

## Policy

- Normal minimum net edge remains **0.30 cents per contract**. No marginal or
  dependence reserve has been added to the quote reference.
- Hedge minimum is **0.10 cents** (`0.001` dollars). The 0.05-cent comparison
  remains available below. The prior public-tape replay obtained the same
  allocations at 0.10 cents as at 0.05 cents, with better modeled edge.
- Discounts require an exact full-game moneyline combo on distinct fixtures,
  at least one fixture at 90% of its regime-adjusted cap in **filled paper
  inventory**, a reduction in that fixture's payoff-loss bound and absolute
  conditional sensitivity, and nonpositive incremental whole-book model
  variance. Resting/unfilled hedges cannot earn credit.
- Both pricing and fill-time checks reprice held inventory. Any unavailable
  held position disables the discount, not ordinary quoting. In particular,
  started games can prevent discounts until their holdings are settled;
  this deployment does not invent in-play fair values.
- Variance assumes independent fixtures, uses upper covariance bounds for
  unknown same-fixture intersections, and assumes 1% full-game fractional
  ties. This is a model sensitivity guard, not a calibrated variance guarantee.
- Signed and unsigned positions share one cap calculation. Only filled
  opposing reviewed moneylines supply premium credit to conditional
  contract/fixture risk. Cash, combo exposure and deployment capital stay gross.
- Caps remain $10,000 committed capital, $250 per ticket, $500 per contract
  and combo, and $1,000 per fixture. Inventory mode rejects a requested ticket
  that exceeds the cap; it does not pretend the RFQ requested a clipped size.
- The rho 0.05/top-1% correlation rejection, creator policy, source freshness,
  pregame and liquidity requirements remain in force.
- Kalshi–Pinnacle and Polymarket–Pinnacle fallback weights now respond to
  liquidity/age scores instead of being forced to 80/20. Pinnacle retains its
  20% ceiling; the three-source blend and consensus lean remain enabled.

## Paper inventory, not exchange fills

The collector retains public trade messages for recently observed in-scope
RFQ combo tickers. A YES-directed public print can allocate FIFO across active
shadow quotes only if its price crosses our YES ask, its native timestamp is
after publication and before expiry, and receipt-time last look passes.
Allocations use our quoted price, never favorable public-price improvement.
Print volume is allocated only once, with persistent trade-ID deduplication.
Block trades, stale/future/prepublication prints and ambiguous timestamps are
excluded. Seconds-only timestamps use the start of the second conservatively.

Partial fills create held child reservations and retain the unfilled parent.
Expiry/cancellation releases only the parent. A partial fill is rejected if
fee rounding would exceed the reserved total; no additional fee reserve is
charged to fair value. Restart and transaction rollback retain these rules.

`simulation_fill_confirmed` records actual quantity, exact rounded economics,
selected floor, pricing snapshots and inventory diagnostics. Public-tape
allocations explicitly say `actual_exchange_fill: false`. `paper_trade_match`
records trade price/quantity, allocations and rejections. These are hypothetical
competitive opportunities: there is no RFQ-award attribution, queue model or
guarantee we would have traded. They are not realized P&L.

The fill-edge report now sizes quote-horizon markouts to each partial allocation
and uses its rounded fee. Horizons remain measured from the quote decision,
not from fill time; these are model markouts, not independent market marks.

Direction and timestamp fields follow Kalshi's
[public trade schema](https://docs.kalshi.com/websockets/public-trades) and
[direction documentation](https://docs.kalshi.com/getting_started/order_direction).

## Launch

Use a **fresh run directory**; old runtime manifests intentionally reject code
or policy changes. Do not resume an older policy's database with these settings.

```sh
.venv/bin/python scripts/run_shadow.py --seconds 14400
```

For the 0.05-cent comparison, in a separate fresh run:

```sh
.venv/bin/python scripts/run_shadow.py --seconds 14400 --hedge-floor-cents 0.05
```

The wrapper persists a comparison policy in its run directory. If resuming
that run, pass the same comparison option and the same `--run-dir` with
`--resume`. These commands are foreground long-running captures, not immediate
CLI completions. No run was started during this implementation.

Fee metadata was reverified from public endpoints, preserving the reviewed
mapping identities. Evidence is in `runs/shadow_inventory_metadata_20260910/`.
Static preflight passed with 1,561 eligible mappings on 15 pregame fixtures;
128 mappings were excluded for the pregame cutoff. This does not certify
current feed health. Validity is bounded by the recorded timestamps and any
scheduled fee change, not extended by launching a run.

For a later session, refresh metadata before launch using a new evidence
directory and the appropriate verified season/week endpoint:

```sh
.venv/bin/python scripts/refresh_nfl_fee_metadata.py \
  --config config/runtime_nfl_authorized_shadow_20260910.json \
  --raw-dir runs/shadow_fee_refresh_NEW_SESSION \
  --polymarket-events-url 'https://gamma-api.polymarket.com/events?series_id=12185&event_week=1&limit=100' \
  --refresh-combo-terms
```

Do not refresh a configuration in use by an active/resumed session. The refresh
checks the saved Polymarket condition IDs and fails rather than replacing a
reviewed payoff with another market. Combo grids remain sampled-series
evidence; per-market grid and account precision verification are still required
before any future live implementation.

## Verification

Tests cover mixed signed/gross cap order, filled-only credits, opposing positions
that increase variance, selective floors and last look, stale held inventory,
partial allocations/fees/expiry, duplicate prints across restart, atomic rollback,
collector filtering, comparison launch configuration and allocation-sized markouts.
Existing runtime, creator and correlation tests also pass. The full suite's
five existing failures are the old frozen-candidate hash check and four MLB
scratch-lock cleanup checks; no old freeze was rewritten to claim approval.

Final full-suite result: **1,162 passed, 5 failed** (the failures above), in
43.09 seconds. Machine-readable results are saved in
`runs/shadow_inventory_metadata_20260910/final_verification.xml`; static launch
checks are in the adjacent `preflight.json`. A small synthetic benchmark of
500 eligible-hedge evaluations with one held position measured 0.280 ms median
and 0.312 ms p99; this is not a loaded-book or production throughput claim.
