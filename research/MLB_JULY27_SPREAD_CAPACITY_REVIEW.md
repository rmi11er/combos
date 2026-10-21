# July27 liquidity, margin and capacity review

All48entry-summary partitions reconcile to the44,890print common cohort. All32risk outputs report independent integer-ledger reconciliation, and the four baseline portfolios match the entry sweep. Source/input/output hashes and regression component identities were checked. This is a retained-output review, not another full risk-ledger execution.

## Margin and risk

Every unlimited margin variant is profitable this day. At0c/combo net is$70,503/$202,789/$335,463/$451,971for K/equal/PM75/PM, versus$34,037/$43,104/$117,467/$209,015at0.3c/combo. At0.3c/leg the values are$238/$6,237/$9,055/$69,394. These are selection hurdles at observed prices; they do not measure a new quote's acceptance rate.

| Scenario | Kalshi net / peak cash | Equal net / peak cash | PM75 net / peak cash | PM net / peak cash |
|---|---:|---:|---:|---:|
| Baseline | 138 /454 | −14 /433 | 13 /671 | 133 /904 |
| Balanced1,000 | 317 /3,159 | 283 /5,318 | 706 /6,805 | 901 /9,512 |
| Capital only | 479 /4,585 | 183 /9,974 | 1,701 /10,108 | 3,097 /10,130 |

Balanced1,000improves all four models here, unlike July25. Actual-settlement profits can be reused, so capital-only peak commitments can slightly exceed initial funding. These daily paths must not be added to manufacture one continuous account. The final candidate needs chronological pooled sizing/risk tests and the separately identified point-versus-shadow-reserve gap addressed. No live limits changed.

## Spread decomposition

47,954eligible moneyline prints produce47,654paired opposite-market features; the common calibration cohort is33,081prints and7,480,108.59contracts. Its net is$1,050,184.00. Kalshi average compensation is−0.3956c, residual+14.4353c, net+14.0397cper contract.

| Feature / regression | Compensation slope | Net slope | Net slope after fixture omission |
|---|---:|---:|---:|
| Raw / spread only | +0.1133 | −3.6578 | [−4.6437,−2.3964] |
| Raw / price and leg count adjusted | −0.0759 | +0.8952 | [−0.2339,+2.1045] |
| Fee-expanded / spread only | +0.0514 | −1.5800 | [−1.9150,−0.8348] |
| Fee-expanded / adjusted | −0.0735 | +1.0150 | [+0.0213,+1.9903] |

Units are cents of component P&L per contract per one-cent increase in the spread feature. Adjusted compensation slopes remain negative under all omissions. Unadjusted net slopes are negative, unlike July25; controlling for price/leg count changes their sign. Hence spread alone is not a stable toxicity classifier or direct estimate of collectible compensation. Outcomes, price and leg-count composition materially affect the relationship. No IID confidence claim is made from overlapping fixture omissions.

The feature is a historical opposite-moneyline proxy, not measured depth. Pinnacle remains absent and historical maker-fee applicability remains an unverified scenario. Preserve all dates in pooled development and held-out validation.

[Components and sweeps](../runs/morning_research_20260908/july27_spread_capacity_review/verification.json) · [Root checks](../runs/morning_research_20260908/july27_spread_capacity_review/root_verification.json)
