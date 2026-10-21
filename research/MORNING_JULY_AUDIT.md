# July 1 MLB independent audit

Audited the completed July 1, 2026 Chicago trading-day outputs; this is one observed trade date, with some bets resolving on later dates. No frozen scripts or running artifacts were modified. All monetary results below use the archived **unverified historical fee scenario**.

## Coverage and what the benchmark represents

- Raw completed census: 9,360,606 public prints; 1,431,089 unique combo prints; 248,174 pure-MLB prints across 113,070 definitions.
- Full-game pregame-proxy candidates: 71,052. Primary replay restricts to 2–4 legs, distinct fixtures, eligible print direction, and at least 60 seconds before native scheduled start: 35,437 prints.
- Kalshi prices 35,237; Polymarket and both fixed exchange blends price 31,263. The common comparison therefore covers 88.22% of primary eligible prints. Pinnacle is unavailable, not zero fills.
- The common sell-all benchmark is **31,263 eligible, jointly priceable prints**, not every one of the 248,174 MLB prints. Broader SGP, 5+ leg and unpriceable subsets must remain separately reported.
- All common outcomes are known. However, 1,516 prints settle after the trading-day endpoint. Trade-attributed final P&L must not be called spendable end-of-day profit.

## Universe profitability and concentration

The common sell-all portfolio earns $506,508.08 after $41,631.73 assumed maker fees, on $1,535,819.74 YES premium and $8,881,242.39 payout notional. It requires $4,907,108.42 peak committed cash. These are observed-price capacity results, not attainable fills on a $10k account.

**Removing all combos touching July 1 MIA–COL changes P&L to −$98,931.84.** That fixture contributes $605,439.92 under overlapping any-leg attribution. LAD–ATH contributes $407,188.05. These contributions cannot be added as independent game profits, since combos share fixtures. There are 37 fixture identities, including future games; the large print count is not an independent sample size.

| Legs | Prints | Payout notional | Net P&L |
|---|---:|---:|---:|
| 2 | 10,755 | $2,648,925.91 | $218,378.33 |
| 3 | 12,018 | $3,107,535.13 | $160,409.39 |
| 4 | 8,490 | $3,124,781.35 | $127,720.36 |

## Selection at the frozen 0.3c per-combo threshold

| Model | Funded fills | Funded final P&L | Peak cash | Unlimited fills | Unlimited P&L |
|---|---:|---:|---:|---:|---:|
| kalshi | 49 | $118.39 | $463.74 | 147 | $19,149.92 |
| exchange_blend_equal | 58 | $147.09 | $509.70 | 165 | $21,881.23 |
| exchange_blend_pm75 | 82 | $188.69 | $654.28 | 959 | $84,397.17 |
| polymarket | 117 | $301.57 | $840.21 | 2,588 | $154,392.19 |

All four funded baseline selections remain positive after individually removing any fixture. Unlimited 0.3c selections also remain positive in this single-date fixture-removal sensitivity. This is a useful contrast with sell-all, but it does not establish held-out profitability or identify a winning threshold.

The all-print model compensation is negative: Kalshi −$32,681.85, PM −$14,132.59, equal blend −$23,381.71, PM75 −$18,750.78. Most realized profit is favorable outcome residual, not estimated edge. Quantity-weighted Brier: K 0.102258; PM 0.101515; equal blend 0.101880; PM75 0.101696. These are descriptive on the same known-outcome cohort and not cluster-adjusted significance tests.

## Capacity and threshold findings

Sell-all with existing $100 underlying/$100 combo/$250 fixture limits accepts 213 prints, earns $188.86 eventual P&L, and reaches only $1,412.99 peak cash. At the day endpoint, only $12.37 of that P&L is actually settled and $848.83 remains committed. Lowering the edge cutoff alone does not consume $10k.

| Model | $1000/$1000/$2000 limits: P&L | Peak cash | Capital-only P&L | Peak cash |
|---|---:|---:|---:|---:|
| kalshi | $121.56 | $4,420.77 | $3,426.00 | $10,420.59 |
| exchange_blend_equal | $701.01 | $4,402.83 | $671.26 | $10,607.10 |
| exchange_blend_pm75 | $1,135.90 | $6,211.91 | $-501.06 | $10,550.74 |
| polymarket | $1,756.37 | $7,781.19 | $716.10 | $10,466.61 |

Capital-only can exceed $10k committed cash after already-settled profits are reinvested; $10k is initial funding. The PM75 capital-only loss despite positive baseline demonstrates that relaxing limits changes which prints survive. Fixed print quantity is accepted or rejected wholesale; the current backtest does not optimize or partially size a larger requested ticket to remaining risk. Thus capacity estimates do not establish the best executable sizing policy.

## Accounting and implementation checks

- Independently recalculated common-cohort P&L from quantity × (YES price − YES settlement) − fee; reconciles to $506,508.0793.
- Recomputed archived maker fees for all 35,237 Kalshi-priced rows using decimal arithmetic, .035 rate, direct-account .0001 precision and NO-buy cash mechanics; maximum difference is zero. This verifies implementation of the chosen scenario, not the historical fee rate or account precision.
- All 32 risk scenarios report successful independent integer-ledger reconciliation. Source inspection confirms cash is released only at actual settlement, while eventual P&L is attributed to trade time.
- Changing maker rate to .07 on the exact fixed common sell-all cohort gives fees $83,261.92 and P&L $464,877.89. This demonstrates that doubling that fee does not erase this slate's favorable outcome result; it is not a reselected policy or a validated historical fee case.
- The scenario explicitly marks July combo .035 as unverified; only KXMLBGAME .07 is supported by a dated native override. July spread/total and PM effective dates remain unverified. Native historical rule-parity and actual-start exceptions also remain unresolved.
- Pricing exclusion counts are per-leg diagnostics and can exceed print counts; do not describe 104,070 missing Pinnacle observations as 104,070 missing trades.
- No broad accounting sign error found in inspected common P&L, fee mechanics or settlement release. Historical execution, live acceptance, and historical fee certification remain outside what this audit proves.

## Required follow-through

1. Run the same concentration and compensation/residual decomposition on every completed date. Report sample coverage separately from model selection.
2. Complete held-out August comparisons with cross-date fixture purge and continuous cash ledger; do not choose risk or thresholds from July 1 or the previously inspected September 5.
3. Preserve all-universe outcomes separately for the broader pure-MLB census. The common 2–4-leg comparison cannot support claims about all SGP/5+ leg trade profitability.
4. Run explicit dated fee sensitivities and a separately versioned partial-size execution study before inferring that idle capital requires larger bucket limits.
5. Shadow operation should measure pricing coverage, fresh depth, decision latency and quote lifecycle; public print replay provides no fill-probability evidence.

## Authoritative inputs

- `runs/mlb_historical_20260907/dated_fee_primary/2026-07-01/cohort/summary.json` — SHA256 `e32604177403c8c8ddce0ab04582c3f702e346d051302450232225d49ce77c6a`
- `runs/mlb_historical_20260907/dated_fee_primary/2026-07-01/cohort/fee_scenario.json` — SHA256 `691da9c9a2b1b3b27e488fd68a97ba8136bfaec5eae96eccba0f8a53888023f4`
- `runs/mlb_historical_20260907/dated_fee_primary/2026-07-01/replay/coverage.json` — SHA256 `31b3ab6291d98c4289101c845144e10774eb84a4aca30d8df5730965538cd6c0`
- `runs/mlb_historical_20260907/dated_fee_primary/2026-07-01/replay/opportunities.json` — SHA256 `50bb46e390bcbc75c76cab6afb8f83ab011902a5d35cb9b6e20900837dcd80a2`
- `runs/mlb_historical_20260907/dated_fee_primary/2026-07-01/common_model_report/common_cohort_metrics.json` — SHA256 `0379537dc3f48b423749eb8be72d4a2158338ef779fec95b195b1c570282922d`
- `runs/mlb_historical_20260907/dated_fee_primary/2026-07-01/entry_sweep/summary.json` — SHA256 `0420a232bce547e0511f5c18a8fb51e55f486d52d99cd8f9718d20f612ca2b39`
- `runs/mlb_historical_20260907/dated_fee_primary/2026-07-01/risk_capacity/summary.json` — SHA256 `96a75cd518bc4d27060fdd7e467a6ff17ce1e0d5b6b12a127d9aaf9653395ab7`
