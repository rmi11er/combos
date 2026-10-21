# July marginal-reserve comparison — full audit passed

The 24-portfolio sweep and full independent audit have passed. `runs/mlb_july_marginal_reserves_20260909/full_verification.json` verifies 11,221,992 decisions, all 12 funded exposure paths, all eight fraction-zero baseline fill sets, source preservation, reserve formulas, pricing admission and native P&L reconciliation. Historical fee applicability and execution assumptions are not certified by these arithmetic checks.

All portfolios use the same 467,583 matched prints across 15 July development dates, four exchange-only fair models, and a 0.3c/combo minimum edge. July 13 remains an identity gap. Pinnacle is absent; the historical .035 maker-fee coefficient remains a scenario. Full observed quantities are assumed executable at public print prices. A reserve fraction changes selection, not the actual historical price or fee of a selected print.

The reference is point fair plus fraction times the difference between the independent marginal upper and point fair. Fractions 0, .25 and 1 are explicit pricing assumptions, not confidence levels. The additional worst-case joint dependence allowance is excluded in these candidates and remains a separate benchmark.

| Fair model | Funded net, fraction 0 | Funded net, fraction .25 | Funded net, fraction 1 |
|---|---:|---:|---:|
| Kalshi | $1,972 | $785 | −$732 |
| Polymarket | $1,864 | $2,174 | $514 |
| Equal blend | $2,894 | $954 | −$59 |
| PM75 | $3,516 | $983 | $362 |

Funded portfolios have $10k starting cash, a fixed $10k outstanding-cash ceiling and $1k underlying/combo/event caps. Settlement alone releases funding. Eventual P&L is attributed retrospectively to trade time. Fraction-zero peak commitments range from $6,245 to $7,348; fraction-quarter from $4,340 to $5,292. None needs looser cash ceilings to implement the observed path.

Every fraction-zero and fraction-quarter funded portfolio remains positive after deleting accepted prints touching any one fixture, without reallocating capacity. At fraction one, every model has a negative single-fixture omission. These are overlapping influence diagnostics, not confidence intervals or held-out tests.

| Fair model | Unlimited net, fraction 0 | Unlimited net, fraction .25 | Unlimited net, fraction 1 |
|---|---:|---:|---:|
| Kalshi | $131,052 | $26,295 | −$6,529 |
| Polymarket | $658,093 | $217,133 | $50,923 |
| Equal blend | $267,946 | $96,350 | −$7,519 |
| PM75 | $443,060 | $137,344 | −$2,271 |

Unlimited results require much more funding and assume participation at all qualifying print sizes. They are not returns achievable on $10k. Their larger outcome residuals also cannot be equated with model-implied compensation.

## Interpretation and next comparison

More reserve does not monotonically improve outcomes. The quarter reserve improves funded PM-only P&L while reducing its unlimited P&L: admission timing and capacity displacement matter. Full marginal endpoints dramatically reduce participation and do not consistently protect realized P&L. This argues for testing liquidity-sensitive reserves and explicit sizing/allocation policies rather than selecting the widest reserve by default.

Do not pick the largest P&L cell as a final hyperparameter. Inspect funded/unlimited equity and modeled-edge curves, and compare leg-count, liquidity and fixture influence before freezing a small candidate set. Avoid another broad search over this same development sample. NFL findings remain separate. August outcomes remain uninspected, with fixtures already represented by July trades requiring purge from held-out evaluation.

The renderer `scripts/plot_marginal_reserves.py` requires a successful full audit matched to the exact summary hash. It produced separate equity, modeled-edge and cash plots with three reserve rows and funded/unlimited columns, using shared scales within each funding column. Sampled-date P&L variance is labeled; annual Sharpe remains unavailable because the observations have calendar gaps and shared fixtures.

## Funded path diagnostics

At zero marginal reserve, equal blend has $2,894 net, $1,011 modeled point compensation and $1,123 maximum retrospective drawdown. PM75 has $3,516 net, $1,143 compensation and $1,635 drawdown. Removing the best observed date leaves $1,865 and $2,130 respectively. These date omissions delete trades without reallocating capacity and overlap fixtures; they are not independent tests.

PM-only with quarter reserve has $2,174 net, $1,327 compensation, $1,649 drawdown, 11 positive observed dates out of 15, and $611 after removing its best date. PM75 with quarter reserve has $983 net but becomes negative when its best date is omitted. Thus a positive single-fixture omission result alone misses some date concentration.

The higher-profit blended point policies still earn materially more than their model-implied compensation. Neither the endpoint nor the historical drawdown should be treated as a forward return or loss bound. Candidate ranking should compare predictive accuracy, expected compensation, path concentration and deployment together. A historically favorable fixed exchange blend is not yet validation of the proposed live three-source liquidity-weighted fair.

All three PNGs have been visually reviewed. [Equity](../runs/mlb_july_marginal_reserve_plots_20260909/trade_attributed_equity.png) · [Modeled point edge](../runs/mlb_july_marginal_reserve_plots_20260909/point_edge_equity.png) · [Outstanding cash](../runs/mlb_july_marginal_reserve_plots_20260909/committed_cash.png). Renderer and visual-review receipts retain input and output hashes.
