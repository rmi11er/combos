# NFL fees and equivalent-payoff risk — September 7, 2026

All 299 configured NFL mappings were checked against fresh public Polymarket
event/market metadata and Kalshi series metadata. The observed taker coefficients
are 0.05 on Polymarket and 0.07 on Kalshi for moneyline, full-game spreads and
full-game totals. Source responses, retrieval times and hashes are in
`runs/nfl_fee_verification_20260907/full/report.json` and adjacent raw files.
The refresh tool preserves payoff reviews and does not clear any Pinnacle pricing
block or independently expired combo fee/grid gate.

## Fair-value fee formulation

For quantity q, selected-outcome price p in dollars and current market coefficient r:

`model_fee_dollars = q * r * p * (1 - p)`

Use the market's current schedule, not legacy Polymarket `makerBaseFee` or
`takerBaseFee` fields. All checked PM markets have `feesEnabled=true`,
`feeSchedule.rate=0.05`, `exponent=1`, `takerOnly=true`; the legacy fields read
1000 and must not be interpreted as the applicable 10% taker fee. Kalshi series
have multiplier 1, hence r = 0.07 × 1. At 100 shares priced at $0.50 this gives
$1.25 PM and $1.75 Kalshi before rounding, not 5%/7% of contract premium.

The current [Polymarket fee documentation](https://docs.polymarket.com/trading/fees)
specifies cash fees rounded to five decimal places. Its [order documentation](https://docs.polymarket.com/trading/place-orders)
states that market-buy fees are charged on top of pre-fee notional. Do not use the
archived exchange-v1 fee-in-shares implementation. We implement five-decimal
rounding; midpoint tie-breaking is not specified publicly, so HALF_UP is an
explicit convention pending fill validation. Fair-value bounds use a conservative
ceiling that covers either nearest-rounding tie. Future rebates and third-party
builder charges are not assumed; this is the native platform fee schedule.

The current [Kalshi rounding documentation](https://docs.kalshi.com/getting_started/fee_rounding)
specifies, for signed fill revenue R (negative on buys):

1. `trade_fee = ceil(model_fee / 0.000001) * 0.000001`.
2. `aligned_change = floor((R - trade_fee) / u) * u`.
3. `rounding_fee = R - trade_fee - aligned_change`.
4. Add that rounding fee to the order's existing accumulator.
5. Rebate whole multiples of u from the accumulator, capped at the fill's trade
   plus rounding fee so that net fees cannot be negative.

`net_fee = trade_fee + rounding_fee - rebate`.

u is $0.0001 for direct members and $0.01 for non-direct members. The reference
fair uses direct-member precision, explicitly recorded in each Kalshi mapping;
actual account precision must be checked before execution. The fee accumulator
is per order and spans taker/maker fills. Our new Decimal helper takes and returns
the accumulator and handles buy and sell revenue signs. The frozen study's legacy
single-fill `total_fee` is retained for reproducibility; it is not a general
multi-fill ledger. New live observations use `fee_model=venue_cash_v2` and include
the finite-size fee context in decision logs.

For top-of-book bid b/size qb and ask a/size qa, the no-arbitrage interval is:

`lower = max(0, b - fee_sell(qb,b)/qb)`

`point = (b+a)/2`

`upper = min(1, a + fee_buy(qa,a)/qa)`

The fee allowances conservatively include rounding and never fall below the smooth
r p(1-p) allowance. No already-earned rounding rebates are assumed for this
hypothetical taker. The liquidity score uses the resulting spread. Selected NO
intervals are obtained by complementing both endpoints. This widens uncertainty;
it does not shift the midpoint merely because fees are high. Pinnacle's vig is
already in its odds bracket and receives no invented additional exchange fee.

## Canonical risk grouping and directions

The original implementation used one bucket per selected team's market key.
That could allow $100 on Lions YES plus another $100 on Bengals NO. The risk
family now uses one canonical orientation for the full-game payoff. All 32 NFL
moneyline mappings collapse into 16 families; total configured families are 283.

For a Bengals/Lions fixture whose canonical outcome is Bengals:

| Position | Conditional payoff-change sign |
|---|---:|
| Buy Bengals YES / buy Lions NO | + |
| Sell Bengals YES / sell Lions NO | − |
| Buy Lions YES / buy Bengals NO | − |
| Sell Lions YES / sell Bengals NO | + |

The sign flips independently for the selected YES/NO side and buy/sell action.
Each quote records quantity times that sign, conditional on the other selected
combo leg paying one. This diagnostic is not an unconditional delta or hedge.

The $100 family cap aggregates **gross maximum-loss commitments**, including open
reservations and simulated fills, across equivalent tickers and both directions.
The same canonical identities and selected signs also identify equivalent combos.
The fixture cap remains $250 across moneyline/spread/total families, and the
defensive regime halves both caps. Neither opposite signs nor economically
equivalent aliases release cash collateral or grant automatic netting credit.

Different parlays generally cannot offset simply because a shared leg points in
opposite directions: `Lions AND A` and `Bengals AND B` can both create losses in
different joint outcomes. Exact portfolio offsets need full joint-payoff scenario
accounting. The current gross cap is deliberately conservative. The runtime still
quotes only the maker's NO side of a selected-leg combo; the sign helper supports
buy/sell normalization for future adapters without claiming those adapters exist.

Moneyline ties pay 0.5 on both team contracts under the reviewed normal-game rules,
so the normal-game complement includes ties. Exceptional settlement differences
remain a separate pricing block and are not assumed to create redeemable aliases.
Opposing half-point spreads share a family only at the exact negated threshold;
integer-line pushes are rejected. Different thresholds are not fungible. A
moneyline is not automatically equivalent to a −0.5 spread because tie payouts
differ. Totals over/under share an exact-line family; nested totals and different
spreads still share the broader fixture concentration cap.

## Pinnacle product scope

The current universe needs continuously refreshed **pregame full-game moneyline,
spread and total odds**, including the exact alternate lines used by our mappings
and two-sided stake limits. It does not need in-play odds or player props.
Player passing/rushing/receiving/TD contracts are outside our model and remain
unquoted. If added later, they need their own odds coverage, settlement/participation
rules, liquidity checks and joint-dependence model; a team moneyline does not price
a player prop. Request alternate-line coverage explicitly: main lines alone leave
many currently mapped contracts without a Pinnacle match.

Validation covers alias aggregation across RFQs, buy/sell sign identities, exact
spread complements, preservation of different lines, fee examples, balance
alignment, accumulator/rebate caps, and finite-size fee bounds.
