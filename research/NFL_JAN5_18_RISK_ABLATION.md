# NFL January 5–18 isolated risk-limit sweep

All 21 named scenarios / 84 model portfolios completed. Root verified every source/input/output hash and every independent integer exposure audit. The existing funded baseline reproduces exactly, including all summaries, 95,236 decisions, 107 fills, 84,726 curve rows and 56 daily records. Seven focused tests pass.

The same 23,809 common 2–4-leg pregame moneyline prints and 0.3c/combo edge hurdle are used throughout. Source models lack Pinnacle; historical .035 maker fees remain an unverified scenario. Each portfolio begins with $10k, uses full observed print sizes and releases funding only at actual settlement. These are hypothetical executions, not RFQ acceptance evidence.

## Main result

Increasing fixture limits with the $100 underlying/$100 combo limits unchanged does not change the baseline portfolio. The tighter underlying constraint dominates in this nine-game, complementary-moneyline scope. With the other caps relaxed to $10k, cash deployment rises, but results are model-dependent rather than monotonically better.

| Model | Event cap / other caps | Fills | Net P&L | Peak cash | Minimum net after one game omission |
|---|---|---:|---:|---:|---:|
| exchange_blend_equal | 250 / baseline | 23 | $37.38 | $118.02 | $6.74 |
| exchange_blend_pm75 | 250 / baseline | 20 | $-26.73 | $174.50 | $-66.34 |
| kalshi | 250 / baseline | 21 | $-29.40 | $139.07 | $-64.61 |
| polymarket | 250 / baseline | 43 | $-73.66 | $208.57 | $-111.69 |
| exchange_blend_equal | 1,000 / 10,000 | 71 | $343.27 | $1,829.73 | $23.36 |
| exchange_blend_pm75 | 1,000 / 10,000 | 104 | $-145.16 | $1,721.16 | $-689.09 |
| kalshi | 1,000 / 10,000 | 89 | $589.93 | $1,273.91 | $151.94 |
| polymarket | 1,000 / 10,000 | 82 | $-1,109.60 | $2,027.48 | $-1,319.12 |
| exchange_blend_equal | 2,000 / 10,000 | 101 | $-1,029.21 | $2,868.79 | $-1,625.77 |
| exchange_blend_pm75 | 2,000 / 10,000 | 142 | $-198.79 | $3,805.83 | $-1,283.63 |
| kalshi | 2,000 / 10,000 | 144 | $1,393.15 | $3,201.51 | $230.49 |
| polymarket | 2,000 / 10,000 | 169 | $-2,138.41 | $3,775.70 | $-2,303.05 |

At a $1k event cap with other caps relaxed, K/equal remain profitable after every single-game omission; PM75/PM lose. At $2k, K remains positive after every omission, but equal becomes negative. These retrospective omissions remove accepted prints without reallocating to alternatives; they are not confidence intervals. They do not establish stable optimal risk limits.

Fixture and underlying caps can become economically equivalent for complementary moneyline families. Some named scenarios deliberately duplicate baseline or each other, and are not independent trials. Partial sizing, spread/total-specific risk, more independent games, and prospective three-source pricing remain untested by this sweep. No live limits changed.

[Event-cap plots](../runs/morning_research_20260908/nfl_risk_ablation_review/fixture.png) · [Underlying-cap plots](../runs/morning_research_20260908/nfl_risk_ablation_review/underlying.png) · [All 84 portfolios](../runs/morning_research_20260908/nfl_risk_ablation_v2/summary.json) · [Workflow](RISK_ABLATION_WORKFLOW.md)

Peak-cash representation check: the integer risk ledger rounds each reservation upward to $0.0001; the economic curve retains unrounded cost. Across all84portfolios, ledger peaks exceed economic peaks by at most $0.0022, within the per-fill rounding bound. This is not a fee or profit difference; no production accounting was changed. The independent ledger audit checks exact admission/exposure mechanics. See `nfl_risk_ablation_review/root_verification.json`.
