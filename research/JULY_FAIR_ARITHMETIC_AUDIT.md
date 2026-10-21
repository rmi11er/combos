# Independent July point-pricing audit

All **1,483,540 model decisions** pass independent point-pricing reconstruction across **370,885 common prints on13completed July dates**. The auditor read468,720pricing-context records and root independently verified27distinct source/input hashes. The run includes July1,3,5,7,9,11,15,17,19,21,23,25,29. July13 is explicitly unpriced; July27/31 and all August validation remain outside this checkpoint.

The reusable audit independently calculates fee-expanded Kalshi intervals, the recorded historical PM spread proxy and fee expansion, equal/PM75leg blends, YES/NO orientation and the product of selected leg probabilities. It checks source availability against decision time and the recorded60second historical publication-delay convention. It imports no production pricing functions. Five tests exercise correct reconstruction and deliberate orientation, interval, decision-time and future-availability faults.

This is stronger evidence against a basic point-calculation/sign error than checking only P&L arithmetic. It does not establish the truth of input probabilities or recorded timestamp semantics. Raw venue-response reconstruction, exact cross-venue payoff parity, PM history price semantics, dated fee applicability, joint dependence, execution capture and three-source liquidity weighting remain separate requirements. Passing this audit cannot explain away adverse selection or outcome concentration.

No model, risk threshold or source weight was changed by this audit. The available-date checkpoint does not replace the full study. Extend the same check to remaining July dates as they complete; preserve August's outcome holdout.

[Completed run](../runs/morning_research_20260908/july_fair_arithmetic/status.json) · [Independent hash verification](../runs/morning_research_20260908/july_fair_arithmetic/root_verification.json) · [Auditor](../scripts/audit_exchange_fair_points.py)

## Raw-source follow-through

All13completed July dates also pass the separate raw-capture audit: **1,345,939Kalshi native-state matches and1,206,598Polymarket as-of-state matches** across the same468,720context rows. Root independently verified7,679distinct raw/input/auditor hashes. The PM check independently chooses the latest archived active point at the modeled60second cutoff. Kalshi verifies recorded bid/ask values and timestamp against the cited native candle.

The first raw-source run stopped on July5 because exact Decimal equality treated a floating-point midpoint representation as an error:0.4985versus0.49850000000000005. The original auditor and failed log are preserved. Version2allows at most two floating-point ULPs around the native PM probability and records every nonzero difference. Across all13dates,670leg contexts differ numerically; the maximum is7e−17probability units. Five tests include accepted rounding plus rejected stale PM selections and materially wrong prices. No production pricing, source data or outcomes were changed.

These checks do not independently resolve all overlapping Kalshi capture intervals, certify actual historical publication latency, establish PM price-history points as executable midpoints/depth, or certify cross-venue payoff semantics. They cannot validate the absent Pinnacle source. The original July25exact-equality receipt refers to the auditor preserved at `runs/morning_research_20260908/july_raw_source_audit/auditor_original.py`; current reusable source is the bounded-rounding version.

[Raw-source run](../runs/morning_research_20260908/july_raw_source_audit_v2/status.json) · [Root verification and measured rounding](../runs/morning_research_20260908/july_raw_source_audit_v2/root_verification.json)
