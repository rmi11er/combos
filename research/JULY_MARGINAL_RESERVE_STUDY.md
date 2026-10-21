# July marginal-reserve comparison

The reusable feature database at `runs/mlb_july_quote_features_v2_20260909/features.sqlite` covers every common July print and all four exchange-only models: 467,583 prints / 1,870,332 model rows across 15 priced dates. It stores point fair, the product of selected-side marginal upper endpoints, summed marginal interval width and leg count. It contains no settlement outcomes.

The builder verifies every context timestamp against the certified index, checks Kalshi/Polymarket availability is no later than the decision, reconstructs each model's point fair, checks the marginal upper against the recorded joint upper, and verifies complete common-cohort coverage, input hashes and SQLite integrity. The first build is retained separately; v2 adds exact decision-time and joint-bound checks. Its source is `scripts/build_quote_features.py`.

The marginal upper is a reference under independent leg payoffs, not a dependence-robust confidence bound. Recorded historical intervals include scenario assumptions and fee padding; their width must not be described as observed live depth or a directly measured Polymarket spread.

`scripts/mlb_marginal_reserve_sweep.py` compares three pricing references:

- point fair;
- point fair plus 25% of the distance to the independent marginal upper;
- the full independent marginal upper.

Every reference retains the same 0.3c/combo minimum net edge and original point fair for reporting. The original joint upper remains in each decision's provenance. The intermediate fraction is an explicit pricing-policy hypothesis, not an estimated probability quantile. This experiment isolates marginal uncertainty from the existing much larger worst-case joint allowance.

The study runs all four models in funded and unlimited regimes: 24 portfolios. Funded portfolios start with $10k, enforce a separate $10k outstanding-cash ceiling, and use $1k underlying/combo/event limits. Only actual settlements release funds. Unlimited portfolios ignore capital and risk limits. Public print prices and full observed quantities remain hypothetical executions; this does not estimate customer acceptance of newly submitted quotes.

Eight focused tests passed across feature construction, reserve interpolation and capped partial-sizing integration. The full sweep is running at `runs/mlb_july_marginal_reserves_20260909`. Completion must be followed by provenance, pricing-rule and admission audits, point-reference parity with the completed studies, and readable curve comparisons. No candidate is frozen or promoted; August outcomes remain uninspected.

## Independent audit workflow

`scripts/audit_marginal_reserve_sweep.py` now pairs every decision with the original certified opportunity, checks unchanged quantities/prices/fees/outcomes/buckets, reconstructs its reserve from the feature database, checks edge eligibility, and independently audits funded cash/exposure admissions. Unlimited admission must equal pricing eligibility exactly. Zero-reserve variants must reproduce the original point-policy fill identities, sizes, prices, fees, settlement times and P&L. The auditor preserves the exact progress snapshot it reads, so an active writer cannot silently change its evidence scope.

Two focused tests passed, including deliberate corruption of quantity, reserve, selection and the pricing-to-risk handoff. The first completed audit covers the Kalshi point-funded, point-unlimited and 25%-reserve-funded portfolios: 1,402,749 decisions. All checks passed, including point-baseline fill parity. This is an early subset receipt, explicitly not a full 24-portfolio validation. Evidence: `runs/mlb_july_marginal_reserves_20260909/early_verification.json` and its retained `.input.json` snapshot.
