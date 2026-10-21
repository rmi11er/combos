# NFL whole-contract partial sizing experiment

Twenty-four portfolios compare point and stressed entry under three risk configurations on the same January 5–18 matched NFL cohort. Each begins with $10,000. The research sizer takes the largest whole-contract quantity no greater than the observed print that fits cash and every canonical bucket. It recomputes the archived .035 maker-fee scenario at that quantity and rechecks the 0.3c/combo hurdle. Actual settlement alone releases cash; eventual trade-attributed P&L cannot fund earlier trades.

## Point-fair results

| Caps | Model | Fills | Net P&L | Peak committed cash | Minimum P&L after one game omission |
|---|---|---:|---:|---:|---:|
| Existing | Kalshi | 11 | −$25.39 | $199.55 | −$83.79 |
| Existing | Equal | 12 | $81.57 | $210.04 | $38.57 |
| Existing | PM75 | 9 | −$100.69 | $194.14 | −$170.86 |
| Existing | PM | 8 | −$342.45 | $251.90 | −$288.07 |
| Event $1,000; other caps $10,000 | Kalshi | 54 | $954.17 | $2,217.90 | −$251.96 |
| Event $1,000; other caps $10,000 | Equal | 44 | $523.28 | $2,163.61 | −$638.74 |
| Event $1,000; other caps $10,000 | PM75 | 55 | $431.57 | $2,100.48 | −$479.11 |
| Event $1,000; other caps $10,000 | PM | 50 | −$1,511.59 | $2,054.49 | −$1,397.25 |
| Event $2,000; other caps $10,000 | Kalshi | 88 | $2,196.06 | $4,241.57 | −$285.02 |
| Event $2,000; other caps $10,000 | Equal | 78 | $2,158.38 | $4,236.24 | −$278.02 |
| Event $2,000; other caps $10,000 | PM75 | 108 | $1,858.16 | $4,193.21 | −$327.47 |
| Event $2,000; other caps $10,000 | PM | 100 | −$1,239.56 | $4,046.78 | −$2,080.35 |

Existing caps are $100 underlying, $100 combo and $250 event. Partial sizing need not increase fill count: previously rejected large early prints now consume capacity and displace later prints. Whole-contract sizing also excludes sub-contract orders; the experiment does not claim to reproduce exchange-supported minimum quantity increments.

Compared with the full-print $1,000 event-cap experiment, Kalshi profit rises from $589.93 to $954.17 and equal from $343.27 to $523.28, but their positive single-game-omission minima become negative. Greater deployment therefore comes with increased realized concentration. Omissions delete selected trades without reallocating capacity; they are not confidence intervals.

## Stressed pricing

Stressed entry produces only 2–6 fills per model/configuration. At a $1,000 event cap, K/equal earn $360.40 and peak near $1,000 cash; PM75 earns $595.29 and PM $687.74. At $2,000, K/equal earn $759.01, PM75 $993.91 and PM $1,086.35. These few positions do not validate broad execution or dependable return. K/equal/PM75 have a game omission that eliminates all profit; PM's minimum remains $92.44.

## Verification and implications

All 24 admission sets produced by the standalone integer sizer match the existing backtester replay. All 24 independent integer exposure audits pass. Three focused tests cover fee repricing, settlement-only reuse, pre-settlement outcome invariance and shared risk buckets with reduced multipliers. Original fee amounts reproduce before resizing, and source/input hashes remain unchanged. Decisions, fills, curves and daily statistics are retained as compressed artifacts.

Disabled rows in the normalized replay represent the sizer's non-admissions; their generic quote-guard rejection is not a live feed failure. Each retains its original observed quantity, available risk budget and maximum quantity that fits in `source.sizing_research`. Inspect those fields rather than interpreting normalized rejection counts as production guard diagnostics.

Next test an explicit allocation fraction/per-ticket risk budget to avoid exhausting event capacity on the first qualifying print, jointly with reserve models and fee-aware margins. Parameters must be evaluated across development slates and then frozen before held-out evaluation. Do not choose them from this nine-game NFL sample. No live risk configuration or production pricing module changed. Pinnacle is absent, historical fee dates remain unverified, and assumed partial participation at public print prices is not observed RFQ acceptance.

[Results](../runs/morning_research_20260908/nfl_partial_sizing/summary.json) · [Verification](../runs/morning_research_20260908/nfl_partial_sizing/verification.json) · [Run script](../runs/morning_research_20260908/nfl_partial_sizing/run.py) · [Research sizer](../scripts/research_partial_sizing.py)
