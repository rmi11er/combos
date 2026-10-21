import datetime as dt
import hashlib,json
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output'
def dollars(x):return ('-' if x<0 else '')+f'${abs(x):,.2f}'

def main():
    s=json.loads((OUT/'summary.json').read_text());t=s['totals'];f=pd.read_csv(OUT/'cfb_trade_opportunities.csv');good=f[f.exclusion.isna()];h=pd.read_csv(OUT/'hourly_volume.csv');rfq=pd.read_csv(OUT/'cfb_rfq_quoteability.csv');watch=json.loads((OUT/'creator_watchlist.json').read_text())
    bins=[0,.01,.05,.25,.5,.75,1];b=good.copy();b['fair_band']=pd.cut(b.fair_mid,bins,include_lowest=True)
    bands=b.groupby('fair_band',observed=True).agg(prints=('trade_id','count'),premium=('premium','sum'),signed_edge=('edge_upper','sum'))
    ref=s['capital_upper_bound_scenarios']['upper'];peak=h.loc[h.cfb_premium.idxmax()]
    concentration=f.groupby('ticker').premium.sum().sort_values(ascending=False)
    text=f'''# September 5, 2026: two-leg college-football combo opportunity study

The recovered data support a **completed-print opportunity envelope**, but not yet
the requested Kalshi/Polymarket/Pinnacle liquidity-weighted estimate. Pinnacle
historical odds/capacity and comparable historical liquidity are missing. The
reported pricing numbers are explicitly **Kalshi-only proxies**; the strict
three-venue result is null, not zero.

## Recovered flow

| Measure | Result |
|---|---:|
| Entire RFQ-combo universe, public prints | {int(t['all_combo_trades']):,} |
| Entire RFQ-combo universe, taker-side premium | {dollars(t['all_combo_taker_premium'])} |
| Traded combo markets with recovered composition | {s['catalog']['metadata_markets']:,} / {s['catalog']['unique_requested_markets']:,} |
| Two-leg September 5 CFB prints | {int(t['cfb_two_leg_trades']):,} |
| Two-leg CFB taker-side premium | {dollars(t['cfb_two_leg_premium'])} |
| Cross-game short-YES prints with primary price coverage | {s['eligible_priced_prints']:,} |
| Those prints with both Polymarket leg-price matches | {s['polymarket_diagnostic_coverage']:,} |
| Highest CFB traded-premium hour, CDT | {int(peak['hour']):02d}:00–{int(peak['hour'])+1:02d}:00 |

Dollar volume is the premium paid on the taker's side, not face-value contract
notional or exchange fee revenue. The whole RFQ-combo series frame uses `KXMVE`.
Flow is highly concentrated: the largest market accounts for
{concentration.iloc[0]/f.premium.sum():.1%} of CFB traded premium; the five largest
account for {concentration.head(5).sum()/f.premium.sum():.1%}. Large gross volume
does not establish many independently accessible $10 opportunities.
A separate audit of similarly named non-MVE composites is retained under
`data/derived/nonprefix_composite_audit.json`; it found no traded prepackaged CFB
series omitted from the two-leg scope.

![Time-of-day results](opportunity_by_time.png)

## Opportunity without a ticket cap, starting with $10,000 capital

These scenarios select historically observed YES-taker prints with at least
0.3 cents per share of net modeled edge and allocate at most once per market per
second. There is no customer-spend ticket cap. Each allocation uses the observed
print quantity, reduced only when necessary to fit available cash for principal
plus fees, in 0.01-contract increments. Allocation proceeds chronologically;
there is no hindsight optimization over which later opportunities to fund.
They reserve full principal plus modeled maker fees. All combo fair values are
allowed; no old 2%–5% restriction remains. Same-game combinations are excluded
from the edge calculation until their joint probability is modeled.
Settled cash is released after an assumed 60-second delay and gains can be
reinvested, so reserved exposure can exceed the initial $10,000. There is no
additional per-fixture cap in these capacity scenarios.

| Fair scenario | Allocated print tickets | Modeled edge | Terminal net P&L on hypothetical allocations | Largest single-fixture exposure |
|---|---:|---:|---:|---:|
'''
    names={'mid':'Kalshi midpoint product','upper':'Fee-expanded upper product','rho002':'Upper product + 0.02 correlation stress','rho005':'Upper product + 0.05 correlation stress','upper_small_prints':'Fee upper, only observed $5–$20 prints'}
    for key,name in names.items():
        r=s['capital_upper_bound_scenarios'][key]
        text+=f"| {name} | {r['allocations']:,} | {dollars(r['expected_edge'])} | {dollars(r['terminal_net_pnl'])} | {dollars(r['maximum_single_fixture_loss'])} |\n"
    text+=f'''
The reference case concentrates as much as {dollars(ref['maximum_single_fixture_loss'])}
of gross maximum loss in fixture `{ref['fixture_at_maximum']}`. Two legs per
ticket do not eliminate dependence across tickets sharing the same game.
Positive modeled edge and terminal P&L measure different things; neither is
evidence of actual quote acceptance. The printed prices may not have been
available to this strategy. The scenario also permits partial allocation of a
public print; it is not a simulation of full-size RFQ execution.

The final row separately restricts source prints to $5–$20 of taker premium.
It is a small-trade diagnostic, not a ticket cap on the main scenarios, and does
not prove those trades would have been available to this strategy.
Each scenario selects and funds a different set of tickets. Stricter pricing
can preserve cash for later opportunities, so capital-constrained modeled edge
need not fall monotonically as the pricing reserve increases.

## How much apparent edge survives widening?

At full observed trade size, the sum of positive edge falls from
{dollars(s['observed_size_mid']['positive_edge_dollars'])} using midpoint fair to
{dollars(s['observed_size_upper']['positive_edge_dollars'])} using the fee-expanded
upper fair. The latter is before a capital constraint and is conditional on
completed trades and independence across the two games.

![Sensitivity results](pricing_sensitivity.png)

Taker-fee widening creates an uncertainty interval, not a new midpoint. Actual
combo maker fees are subtracted separately. Historical book/price publication
latency is unobserved: the primary convention uses a completed minute candle
at least 60 seconds before the print and allows 120 additional seconds of age.
The lag sensitivity uses the same primary priced cohort; rows lacking an
alternative snapshot remain excluded rather than future-filled.

| Primary midpoint fair band | Priced prints | Taker premium | Signed upper-fair edge across all priced prints |
|---|---:|---:|---:|
'''
    for band,row in bands.iterrows():text+=f"| {band} | {int(row['prints']):,} | {dollars(row['premium'])} | {dollars(row['signed_edge'])} |\n"
    text+='\n## Pregame and in-play attribution\n\nThe fee-expanded upper-fair scenario uses one shared capital ledger. These are\ncontributions from its allocated tickets, not separate independently funded strategies.\n\n| Phase at allocation | Tickets | Modeled edge | Terminal net P&L |\n|---|---:|---:|---:|\n'
    for phase,row in ref['phase_attribution'].items():text+=f"| {phase} | {row['allocations']:,} | {dollars(row['expected_edge'])} | {dollars(row['terminal_net_pnl'])} |\n"
    text+='\nA ticket is in-play once either matched fixture has started. Unknown schedule\ncoverage remains explicitly unknown; scheduled start does not identify actual\nkickoff delays, game clock, suspensions or reopening latency.\n'
    costs=rfq[rfq.target_cost>0].target_cost
    text+=f'''
## RFQ and creator evidence

The recovered CFB-market RFQ sample contains {s['rfq_sample'].get('cfb_requests',0):,}
requests. Among positive target budgets, the median is
{dollars(float(costs.median())) if len(costs) else 'unavailable'}; {int(((costs>=5)&(costs<=20)).sum()):,}
requests are in the $5–$20 range. These are repeated requests, not unique customer
orders or accepted quotes. Hypothetical quoteability is evaluated one request
at a time with a one-second decision delay; it does not reserve capital for all
concurrent quotes or imply that those quotes would be accepted.

Creator identities are **unavailable in this recovered sample**:
{s['rfq_sample'].get('requests_without_creator_id',0):,} studied-day requests have
blank `creator_id` and {s['rfq_sample'].get('requests_with_creator_id',0):,} have a
usable value. The watchlist/blacklist files explicitly record unavailable
identity, rather than treating an empty blacklist as a clean bill of health.
No creator filter can be applied to these historical quoteability estimates.

The implemented starter policy flags long leg counts and same-fixture
combinations for review when identity is available. Blacklisting requires three
separate observed duplicate-RFQ bursts, each at least 30 requests in 60 seconds
with at least 80% identical leg sets. This is a stated operational research rule,
not a calibrated adverse-selection model. Histories are incomplete and market
sampled. No blacklist is enabled for live execution.

Creator state is designed to be calculated before each request using only earlier
retained identified requests. Public trades also have no creator/RFQ identity, so creator-level adverse
fill markouts and correlation-pickoff attribution are **not established**.
The code supports future labeled observations, and preserves sample sizes and
reasons in `creator_watchlist.json` and `creator_blacklist.json`.

## What remains unavailable

- Historical Pinnacle paired odds, exact line/period mapping and capacity.
- Comparable historical executable liquidity for the three venues. Kalshi
  minute candles have volume/open interest but no historical book depth;
  sampled Polymarket historical-book requests returned no usable depth. Present
  liquidity or full-day final volume must not be used as historical weights.
- The full RFQ opportunity tape, including never-traded markets. The retained
  RFQ population here is conditioned on traded markets and a context sample.
- Competing makers' quoted prices/volume, which are private. The chart therefore
  shows observed trades and clearly labeled sampled RFQ budgets, not fabricated
  all-universe quoted volume.

The three-venue blending function is implemented with strict source, timestamp,
payoff and liquidity checks. Matched Polymarket histories are preserved for
cross-venue price diagnostics; an equal-weight price diagnostic must not be
described as the requested liquidity-weighted blend.

Automated Polymarket matches align teams, period, line and selected outcome for
a normally completed game. Postponement/cancellation rules differ: for example,
Kalshi's 48-hour start window and fair-price resolution do not match Polymarket's
indefinite postponement provision and 50–50 cancellation outcome. These matches
are not yet certified as identical payoffs in every state.

## Implementation audit

The most consequential findings are the old target-cost denominator, fractional
RFQ quantities, occurrence-versus-kickoff semantics, market-specific fee
coefficients, and differences between documented and implemented paper risk
limits. See [the detailed audit](../research/IMPLEMENTATION_AUDIT.md) for evidence,
formulas and source links. The original `../kalshi_mm` project was not changed.

## Coverage and reproducibility

Catalog complete: **{s['catalog_complete']}**. Unresolved traded market definitions:
**{len(s['catalog']['missing_tickers'])}**. Their public volume is included in the
whole-universe totals; unresolved composition cannot be assigned to the CFB subset.
Quote exclusions:

| Reason | Prints |
|---|---:|
'''
    for reason,count in s['exclusions'].items():text+=f"| {reason or 'Priced'} | {count:,} |\n"
    text+='\nRaw response envelopes retain retrieval timestamps. `summary.json` records assumptions and coverage. `artifact_manifest.json` hashes the study inputs and outputs. No source data were repaired or replaced by inferred values.\n'
    (OUT/'REPORT.md').write_text(text)
    files=[ROOT/'config/study.json',ROOT/'data/raw/trades/manifest.json',ROOT/'data/derived/catalog_summary.json',ROOT/'data/derived/polymarket_mapping.json',OUT/'summary.json',OUT/'raw_input_sha256.jsonl',OUT/'input_coverage.json',OUT/'cfb_trade_opportunities.csv',OUT/'cfb_rfq_quoteability.csv',OUT/'hourly_volume.csv',OUT/'REPORT.md']
    files+=list(OUT.glob('capital_path_*.csv'))+list(OUT.glob('*.png'))+list(OUT.glob('*.svg'))+[OUT/'creator_watchlist.json',OUT/'creator_blacklist.json']
    files+=list((ROOT/'src').rglob('*.py'))+list((ROOT/'scripts').glob('*.py'))+list((ROOT/'tests').glob('*.py'))+list((ROOT/'research').glob('*.md'))+[ROOT/'requirements.txt',ROOT/'README.md']
    files+=[ROOT/'config/weighting.json',*sorted((ROOT/'config').glob('runtime*.json')),
            ROOT/'research/nfl_week1_mapping_review.json']
    manifest={'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'files':[]}
    for path in files:
        if path.exists():manifest['files'].append({'path':str(path.relative_to(ROOT)),'bytes':path.stat().st_size,'sha256':hashlib.file_digest(path.open('rb'),'sha256').hexdigest()})
    (OUT/'artifact_manifest.json').write_text(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
