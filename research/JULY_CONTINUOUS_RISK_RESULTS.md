# Full July continuous funded risk results

All 16 portfolios completed; independent integer exposure audits reconciled every admission across 467,583 decisions per portfolio. Exact baseline decisions, fills and curves now match the completed 48-policy run for all four models; input hashes remained unchanged during comparison. The cohort includes 15 priced July dates; July 13 remains an explicit identity gap. August outcomes were not inspected.

Each portfolio starts with $10,000 and reinvests only actually settled profits. The entry threshold is 0.3 cents per combo contract using point fair; observed full print sizes and prices are hypothetical executions. Pinnacle is absent. The historical .035 maker coefficient remains an unverified applicability scenario.

| Model | Risk configuration | Fills | Trade-attributed net P&L | Peak cash | Minimum P&L after one fixture omission | Modeled net edge |
|---|---|---:|---:|---:|---:|---:|
| kalshi | baseline | 621 | $506.45 | $1,140.04 | $415.97 | $148.81 |
| kalshi | balanced1000 | 1,163 | $1,972.04 | $6,245.38 | $1,513.40 | $975.37 |
| kalshi | fixture2000 | 1,442 | $2,487.39 | $10,608.70 | $1,695.09 | $1,490.18 |
| polymarket | baseline | 1,206 | $637.04 | $1,292.86 | $455.36 | $226.39 |
| polymarket | balanced1000 | 2,143 | $1,864.23 | $7,348.08 | $1,353.15 | $1,293.84 |
| polymarket | fixture2000 | 2,582 | $-2,082.52 | $11,247.79 | $-3,012.35 | $1,942.68 |
| exchange_blend_equal | baseline | 703 | $45.45 | $1,038.38 | $-23.61 | $167.05 |
| exchange_blend_equal | balanced1000 | 1,362 | $2,894.47 | $6,328.02 | $2,482.28 | $1,011.50 |
| exchange_blend_equal | fixture2000 | 1,592 | $-2,432.23 | $10,662.74 | $-3,392.51 | $1,599.44 |
| exchange_blend_pm75 | baseline | 931 | $244.99 | $1,152.54 | $103.71 | $192.01 |
| exchange_blend_pm75 | balanced1000 | 1,767 | $3,515.80 | $6,846.35 | $2,920.51 | $1,143.41 |
| exchange_blend_pm75 | fixture2000 | 2,133 | $-369.59 | $10,479.14 | $-1,404.14 | $1,777.21 |

`baseline`: $100 underlying / $100 combo / $250 event. `balanced1000`: $1,000 for all three. `fixture2000`: $10,000 underlying/combo and $2,000 event. The additional $1,000 event/$10,000 other-caps scenario exactly matches balanced1000 in portfolio and selected metrics for every model. It is not an independent result.

At the $1,000 limits, all four models are positive and remain positive after deleting trades touching any one fixture without reallocating. Larger event allowances turn PM, equal and PM75 negative. These omissions are influence diagnostics, not independent tests or confidence intervals. Portfolio path and capacity allocation matter; unconstrained model ranking is insufficient for parameter selection.

The $2,000 scenarios exceed a fixed $10,000 deployment ceiling by reinvesting settled gains. They are valid initial-bankroll experiments, not hard-cap experiments. The separate candidate deployment ledger must be integrated and replayed before live risk limits are chosen.

The sampled dates are nonconsecutive; annualized Sharpe is not promoted from these incomplete calendar observations. Freeze a limited candidate set after consistent quote-reserve, sizing and deployment-policy comparisons, then evaluate held-out August. Do not choose a winner from these inspected development results alone.

[Exposure verification](../runs/morning_research_20260908/july_continuous_risk_audit/exposure_verification.json) · [All portfolios](../runs/mlb_july_continuous_risk_20260908/summary.json) · [Capital-ceiling audit](JULY_CAPITAL_CEILING_AUDIT.md)

[Equity curves](../runs/morning_research_20260908/july_continuous_risk_plots_v2/trade_attributed_equity.png) · [Committed cash](../runs/morning_research_20260908/july_continuous_risk_plots_v2/committed_cash.png) · [Modeled edge](../runs/morning_research_20260908/july_continuous_risk_plots_v2/point_edge_equity.png). The reusable `scripts/plot_continuous_risk.py` preserves every economic change, verifies source curve hashes and checks terminal equity/peak cash against summaries. All three v2 plots were visually inspected. The first rendering is retained separately; v2 fixes literal dollar-sign labels and places Sharpe N/A explicitly in the equity legends. The variance is across sampled-date P&Ls, not a full-calendar return variance.
