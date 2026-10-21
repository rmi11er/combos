# Backtests and opportunity reviews

A reading room for the existing combos research. Start with a summary review below, then use the daily cohorts for drilldown. This collection was organized September 9, 2026; it is a navigation snapshot, not an automated latest-result selector.

## Start with these reviews

New September 10 study: [volume clocks, markout curves, hedge costs, inventory relief, and same-game offsets](07-research-program/README.md), with 20 charts and a reproducible historical analysis. This addition is separate from the September 9 image inventory below.

| Question | Open |
|---|---|
| Fifteen August validation dates, frozen policies and a continuous funded ledger. Compare funded and unlimited exposure; public prints are hypothetical fills and historical fees are unverified scenarios. | [MLB August — held-out validation](01-mlb/mlb_august_frozen_validation_report_20260909/README.md) |
| Development-period model portfolios and selected/rejected flow. Daily funded runs must not be summed to replace this continuous ledger. | [MLB July — continuous development replay](01-mlb/mlb_july_development_snapshot_20260908/README.md) |
| Final-named full-window paired moneyline plots. The funded replay has tight underlying risk caps; unlimited P&L requires much greater capital. January has already been inspected as development evidence. | [NFL January 5–18 — funded and unlimited replay](02-nfl/nfl_moneyline_replay_20260907--jan5_18--plots_final/README.md) |
| September 9 short capture: 694 matched priced RFQs, 144 portfolios. No-fill/expiry and all-fill/no-release are research assumptions, not observed acceptance rates. | [NFL captured RFQs — charge and capacity sensitivity](02-nfl/nfl_charge_capacity_sweep_20260909/README.md) |
| All, selected and rejected public prints on a shared cohort. Known-outcome P&L excludes unresolved outcomes; model edge is not realized profit. | [CFB — common-cohort selection audit](03-cfb/cfb_performance_audit_20260907--common_point_no_cap/README.md) |
| Weekday opportunity volume and market/leg scope. Saturday census and sampled weekdays have different coverage and uncertainty. | [CFB August 31–September 6 — volume and scope](03-cfb/cfb_week_20260831/README.md) |

## Browse the collection

- [MLB — development and held-out reviews](01-mlb/README.md) — 34 review folders.
- [NFL — historical replay and opportunity reviews](02-nfl/README.md) — 6 review folders.
- [College football — opportunity and selection reviews](03-cfb/README.md) — 13 review folders.
- [Cross-sport pricing and spread reviews](04-cross-sport/README.md) — 2 review folders.
- [Daily cohorts — MLB dates and calibration](05-daily-drilldowns/README.md) — 180 review folders.
- [Earlier variants, pilots and synthetic checks](06-earlier-and-qa/README.md) — 27 review folders.

## How to read the plots

- **Funded / constrained:** portfolio under the run’s cash and concentration rules. Compare cash tied up as well as profit.
- **Unlimited / unconstrained:** exposure diagnostic requiring a different capital budget; not a scalable funded return.
- **Common cohort:** models compared on the same priceable observations. **Available cohort:** each model may price a different set.
- **Point edge:** a model forecast at entry. **Trade-attributed P&L:** eventual known settlement profit assigned to trade time. **Cash:** released at actual settlement. These are different measurements.
- **Selected versus rejected:** identifies how the pricing/selection rule changes the observed opportunity set.
- **Development versus held-out:** July MLB and inspected NFL January are development evidence; the August frozen MLB review is the held-out evaluation.
- **Historical public prints versus captured RFQs:** hypothetical backtest fills and prospective pricing opportunities do not measure live quote acceptance.
- Read original reports for source coverage, fee assumptions, unknown settlements and fixture concentration. Do not compare totals across different cohorts or add independently funded daily ledgers.

## Organization and provenance

This collection indexes **1,512 image files in 262 source folders**. PNG/SVG variants are grouped into **760 figures**. Each review contains readable titles, format links, previews and its original source path. The [file inventory](inventory.csv) maps every browse link to its original file.

Images are relative symbolic links. Existing run folders, raw data, manifests and source code are untouched, preserving report references and other agents’ work. Opening the links in Finder or a Markdown preview reads the original artifact. Moving this collection out of the workspace alone will break those links.

Earlier/QA placement means the folder name or retained provenance identifies a pilot, prior rendering, archive or test; it is not a fresh numerical audit. Unclassified detailed runs remain visible with their original labels. New artifacts produced after this inventory need to be added to the collection.
