# NFL three-source shadow run

Run: `runs/nfl_verified_candidate_shadow_capture_20260910`.

This was a 125-second no-order run using 235 exact-selector/payoff-reviewed
candidate mappings (all supported pregame periods except tie-basis moneylines),
the live Kalshi and Polymarket collectors, and the live `pinnacle+30` REST
collector. The Pinnacle feed used the explicitly labeled shadow assumption that
numeric OddsPapi limits are USD stake limits. That assumption is not approved
for production.

The runtime processed 79,646 decision candidates and drained both creator and
shadow consumers. Five RFQs reached complete three-source pricing and emitted
shadow quotes; all were 2-leg RFQs. Thirteen additional candidates were
rejected because a Pinnacle observation was unavailable, while the broader
decision census was dominated by out-of-scope legs and unmapped markets.

For the ten observed leg weights in the five quotes, the medians were:

| Venue | Median weight | Range |
|---|---:|---:|
| Kalshi | 53.7% | 38.5%–58.2% |
| Polymarket | 35.0% | 26.7%–41.5% |
| Pinnacle | 12.4% | 6.8%–20.0% |

This is the intended behavior of the liquidity/freshness blend: Polymarket and
Pinnacle receive substantial weight, but the books do not receive a fixed
sharpness override when their available depth is lower.

The quotes used the 0.3¢ edge floor. Their YES asks were 27.1¢–30.5¢, with
modeled expected edge of approximately $0.12–$0.27 per quote. These are model
outputs, not realized P&L or evidence of customer acceptance. Three 5-second
markouts were observed; the 30-second markouts were unavailable in this short
run.

The run inherited the older $100 per-underlying and $250 per-fixture limits.
That is documented as a limitation of this capture. The recommended candidate
runtime now records explicit $500 per-underlying/combo/fixture limits and a
$5,000 maximum committed budget at
`runs/nfl_verified_candidate_shadow_recommended_20260910`.

The runtime recorded 27 creator `watch` transitions across 5,560 observed
creators and applied no sanctions. Processing lag was 0.125 seconds median and
0.234 seconds at p99. No order or quote submission adapter was invoked.
