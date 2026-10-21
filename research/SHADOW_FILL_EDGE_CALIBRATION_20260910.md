# Shadow fill-edge calibration

Every accepted `simulation_fill` now emits a `simulation_fill_confirmed`
derived event immediately after last-look validation. The event records the
requested and confirmed price/quantity, initial and confirmation fair points,
fair movement in cents, gross and fee-adjusted net edge per share, aggregate
net edge dollars, and the complete initial/confirmation pricing objects. Those
objects retain each leg's Kalshi, Polymarket and Pinnacle point/bounds, fee
expanded spread, top-of-book depth proxy, freshness, score and final weight.

This separates three quantities that had been easy to conflate:

* **quoted gross edge:** quote price minus fair at publication;
* **confirmed gross edge:** fill price minus fair at last-look confirmation;
* **confirmed net edge:** fill price minus confirmation reference value minus
  the applicable maker fee.

The `too_tight_at_confirmation` label compares confirmed net edge with the
configured hurdle. It is a diagnostic label, not a retrospective admission
rule. Last-look cancellations remain separate so rejected quotes do not enter
the fill-edge sample.

Run `scripts/shadow_fill_edge_report.py --events <events.sqlite> --out <dir>`
to produce row-level CSV and grouped summaries by edge bucket, leg count and
creator. The report also joins later markouts and settlement transitions,
classifying settled fills as `maker_win`, `maker_loss`, or `break_even`. It
reports interim mark-to-model P&L and terminal settlement P&L separately; they
must not be added as two independent cash flows. This is intentionally based
on actual/explicitly injected shadow fills; public prints alone are not treated
as fills. The output should be reviewed by source disagreement, fair movement,
venue weights and creator history before changing the edge hurdle or risk
limits.
