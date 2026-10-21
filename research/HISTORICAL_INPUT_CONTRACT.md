# Inputs needed to complete the requested blend

The adapter reads `data/external/historical_venue_books.jsonl`. Each line must
describe one historical venue observation of the canonical Kalshi YES payoff:

| Field | Meaning |
|---|---|
| `kalshi_market_ticker` | Exact individual-leg ticker, not the combo |
| `venue` | `kalshi`, `polymarket`, or `pinnacle` |
| `available_at` | UTC Unix seconds when the observation was available |
| `liquidity_available_at` | UTC Unix seconds when its capacity was available |
| `liquidity_payout_dollars` | Positive, comparable historical payout capacity |
| `mapping_verified` | `true` only after reviewing all payoff states |
| `source_reference` | Retrievable source/snapshot and mapping evidence |
| `yes_bid`, `yes_ask` | Exchange YES-side book, in dollars per $1 payout |
| `historical_taker_rate` | Applicable exchange quadratic fee coefficient |
| `decimal_odds_yes`, `decimal_odds_no` | Paired Pinnacle odds, instead of exchange fields |

Exchange observations are widened by their taker fee. Pinnacle opposing odds
already contain bookmaker margin; the adapter uses a multiplicative de-vig
center and the executable opposing-odds interval. It requires all three venues
with price and liquidity observations no more than 120 seconds old. It rejects
future observations, duplicate timestamps, missing capacity and unverified
mapping. NO-selected legs complement the entire blended YES interval.

The capacity input needs its own reproducible methodology. Exchange contract
depth has $1 payout per share; bookmaker maximum stake multiplied by decimal
odds gives gross payout capacity. Matching units alone is insufficient: record
both sides' depth/limits and use a consistent definition of price tolerance,
currency conversion and two-sided capacity. Daily volume, open interest and
today's book are not historical executable capacity. Preserve the calculations
behind each supplied weight in the referenced source material.

Teams, date, period and line alone do not establish identical settlement.
Postponement, cancellation, push and overtime provisions must be reconciled.
The recovered Polymarket matches explicitly cover normal completed games only;
they do not set `mapping_verified` for this adapter. No placeholder historical
data or synthetic weights have been supplied.

The current analysis evaluates strict blends only within its otherwise-priced
Kalshi candle cohort. If a complete independent historical three-venue feed
becomes available, extend that coverage path before estimating a broader
universe. Private quote/fill history is separately needed to estimate capture;
three-venue fair values alone do not identify acceptance probabilities.
