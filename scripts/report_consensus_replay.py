"""Market comparison and descriptive liquidity analysis; no causal claims."""
import json
import math
from collections import defaultdict
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
D = ROOT/'runs/shadow_consensus_replay_20260909'
R = D/'results'
def read(p): return json.loads(p.read_text())
def write(p, x): p.write_text(json.dumps(x, indent=2, allow_nan=False)+'\n')
qs = {q['quote_key']:q for q in map(json.loads, (R/'corrected_quotes.jsonl').read_text().splitlines())}
s = read(R/'summary.json'); audits = read(D/'source/replay_audit.json')
old = read(ROOT/'runs/shadow_corrected_point_fair_20260909/summary.json')
fills = read(R/'edge_0.003_delay_0.json'); pairs = read(R/'trade_price_comparisons.json')

def features(q):
    out = {}
    for venue in ('kalshi', 'polymarket'):
        mids=[]; bids=[]; asks=[]; widths=[]; depths=[]
        for leg in q['pricing']['legs']:
            detail=leg['venues'][venue]; sides=detail['fee_context']['sides']
            bid=sides['bid']['price']; ask=sides['ask']['price']
            if leg['selected_side']=='no': bid, ask=1-ask, 1-bid
            mids.append((bid+ask)/2); bids.append(bid); asks.append(ask)
            widths.append(detail['fee_expanded_spread_cents'])
            depths.append(detail['two_sided_depth_payout_dollars'])
        out[venue+'_mean_leg_raw_width_cents']=round(100*sum(a-b for a,b in zip(asks,bids))/len(mids), 10)
        out[venue+'_mid']=math.prod(mids)
        out[venue+'_raw_width_cents']=100*(math.prod(asks)-math.prod(bids))
        out[venue+'_fee_width_cents']=sum(w*math.prod(mids[:i]+mids[i+1:]) for i,w in enumerate(widths))
        out[venue+'_min_depth']=min(depths)
    return out

# One row per unique trade: latest completed quote still alive at that trade.
# This avoids counting the same market print once for every overlapping quote.
unique={}
for p in pairs:
    previous=unique.get(p['trade_id'])
    if previous is None or qs[p['quote_key']]['decision_completed_at']>qs[previous['quote_key']]['decision_completed_at']:
        unique[p['trade_id']]=p
tapes={}
for p in (D/'source/public_tape').glob('*.json'):
    tape=read(p)
    for t in tape['trades']: tapes[t['trade_id']]=t
rows=[]
for p in unique.values():
    q=qs[p['quote_key']]; f=features(q); trade=tapes[p['trade_id']]
    side=trade.get('taker_outcome_side') or trade.get('taker_side')
    rows.append(dict(**p, **f, taker_side=side, contracts=float(trade['count_fp']),
        snapshot_age_seconds=p['at']-q['decision_at'],
        trade_minus_kalshi_mid_cents=100*(p['public_price']-f['kalshi_mid']),
        trade_minus_pm_mid_cents=100*(p['public_price']-f['polymarket_mid']),
        pm_minus_kalshi_mid_cents=100*(f['polymarket_mid']-f['kalshi_mid'])))
write(R/'liquidity_trade_features.json', rows)
yes=[r for r in rows if r['taker_side']=='yes']
def rank(v):
    x=np.asarray(v); return np.array([np.sum(x<a)+(np.sum(x==a)-1)/2 for a in x])
def corr(x,y):
    if len(x)<3 or np.ptp(x)<1e-10 or np.ptp(y)<1e-10: return None
    return float(np.corrcoef(x,y)[0,1])
keys=['kalshi_mean_leg_raw_width_cents','polymarket_mean_leg_raw_width_cents',
      'kalshi_raw_width_cents','polymarket_raw_width_cents','kalshi_fee_width_cents',
      'polymarket_fee_width_cents','kalshi_min_depth','polymarket_min_depth','pm_minus_kalshi_mid_cents']
correlations={k:dict(pearson=corr([r[k] for r in yes],[r['trade_minus_kalshi_mid_cents'] for r in yes]),
    spearman=corr(rank([r[k] for r in yes]),rank([r['trade_minus_kalshi_mid_cents'] for r in yes])),
    distinct_values=len(set(r[k] for r in yes))) for k in keys}

def regression(keys):
    y=np.array([r['trade_minus_kalshi_mid_cents'] for r in yes])
    X=np.array([[1]+[r[k] for k in keys] for r in yes]); b=np.linalg.lstsq(X,y,rcond=None)[0]
    residual=y-X@b; total=np.sum((y-y.mean())**2)
    errors=[]
    for market in set(r['market'] for r in yes):
        mask=np.array([r['market']==market for r in yes]); fit=np.linalg.lstsq(X[~mask],y[~mask],rcond=None)[0]
        errors.extend((y[mask]-X[mask]@fit).tolist())
    return dict(coefficients=dict(zip(['intercept']+keys,map(float,b))),rank=int(np.linalg.matrix_rank(X)),
        parameters=X.shape[1],in_sample_r_squared=float(1-np.sum(residual**2)/total) if total>0 else None,
        leave_one_market_out_rmse_cents=float(np.sqrt(np.mean(np.array(errors)**2))))
models={name:regression(ks) for name,ks in [
    ('intercept_only',[]),('kalshi_width',['kalshi_raw_width_cents']),
    ('both_widths',['kalshi_raw_width_cents','polymarket_raw_width_cents']),
    ('widths_and_cross_venue_gap',['kalshi_raw_width_cents','polymarket_raw_width_cents','pm_minus_kalshi_mid_cents'])]}
liquidity=dict(unique_trades=len(rows),yes_taker_trades=len(yes),markets=len({r['market'] for r in yes}),
    correlations=correlations,models=models,
    snapshot_age_seconds=dict(median=float(np.median([r['snapshot_age_seconds'] for r in rows])),maximum=max(r['snapshot_age_seconds'] for r in rows)))
write(R/'liquidity_analysis.json',liquidity)

marketrows=[]
for ticker in sorted({f['ticker'] for f in fills}):
    fs=[f for f in fills if f['ticker']==ticker]; q=qs[fs[0]['quote_key']]; qty=sum(f['quantity'] for f in fs)
    marketrows.append(dict(ticker=ticker,legs=' + '.join(l['market_ticker'].removeprefix('KXNFLSPREAD-26')+' '+l['side'] for l in q['request']['mve_selected_legs']),
        quotes=len({f['quote_key'] for f in fs}),contracts=qty,
        ask_cents=100*sum(f['quantity']*f['hypothetical_yes_price'] for f in fs)/qty,
        public_cents=100*sum(f['quantity']*f['public_yes_price'] for f in fs)/qty,
        edge_cents=100*sum(f['point_edge_dollars'] for f in fs)/qty,
        ev=sum(f['point_edge_dollars'] for f in fs),collateral=sum(f['liability_dollars'] for f in fs)))
write(R/'market_breakdown.json',marketrows)
def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(map(str,r))+' |' for r in rows])
base=s['scenarios']['edge_0.003_delay_0']; prior=old['scenarios']['edge_0.003_delay_0']
changed=sum(any(l['applied'] for l in a['legs']) for a in audits)
oldqs={q['quote_key']:q for q in map(json.loads,(ROOT/'runs/shadow_corrected_point_fair_20260909/corrected_quotes.jsonl').read_text().splitlines())}
asks_changed=sum(abs(q['yes_ask']-oldqs[k]['yes_ask'])>1e-10 for k,q in qs.items())
lines=['# September 9 consensus-weighted shadow replay','',
'## Scope and verification','',
'Repriced 2,257 retained quotes and 2,332 observed model marks using the recorded event-sequence snapshots. The old policy reproduced every saved point fair within 1e-9 before applying the consensus policy: zero snapshot errors and zero newly blocked quotes. All source databases and original results are preserved.', '',
f'Kalshi-outlier signal detected on {sum(any(l["detected"] for l in a["legs"]) for a in audits)} quotes; actual weight transfer on {changed}. Tick-rounded asks changed on {asks_changed} quotes. Maximum absolute joint-fair change: {max(abs(a["new_point"]-a["old_point"])*100 for a in audits):.4f} cents. All 4,707 leg instances contained three sources.', '',
'The default comparison retains the prior 0.30-cent minimum edge, approximately 0.35 cents after tick rounding, with no additional reserve charge. The rho 0.05 tail calculation and 23.9065-cent rejection threshold remain active. Recorded cancellations/expirations and the original opportunity cohort are held fixed; this is not a full scheduling, inventory, blacklist or fill-response counterfactual.', '',
'## Trading versus the market','',
table(['Measure','Prior point-fair replay','Consensus replay'],[[label,f'{prior[k]:.4f}',f'{base[k]:.4f}'] for label,k in [('Candidate quote matches','quote_count'),('Distinct public trades','trade_count'),('Markets','market_count'),('Contracts','contracts'),('Model edge ($), not P&L','model_edge_dollars'),('Held collateral ($)','collateral_dollars')]]),'',
table(['Legs','Quotes','Contracts','Our ask ¢','Public price ¢','Our edge ¢','Model EV $'],[[m['legs'],m['quotes'],f"{m['contracts']:.2f}",f"{m['ask_cents']:.3f}",f"{m['public_cents']:.3f}",f"{m['edge_cents']:.3f}",f"{m['ev']:.4f}"] for m in marketrows]),'',
f"Across matched contracts, our charge is {100*base['model_edge_dollars']/base['contracts']:.3f} cents; the public price was {100*base['public_price_edge_at_quote_fair_dollars']/base['contracts']:.3f} cents above our quote-time fair. Difference: {100*(base['public_price_edge_at_quote_fair_dollars']-base['model_edge_dollars'])/base['contracts']:.3f} cents. These are selected matching trades, not an unbiased estimate of the whole market.", '',
f"Across all active quote/trade pairs: {s['competitiveness']['quote_trade_pairs']} pairs, {s['competitiveness']['unique_trades']} unique trades, {s['competitiveness']['unique_markets']} markets. {s['competitiveness']['quote_trade_pairs_meeting_price']} pairs meet our ask price (before side and duplicate-volume allocation). Mean public-minus-ask: {s['competitiveness']['public_minus_new_cents']['mean']:.3f} cents; median {s['competitiveness']['public_minus_new_cents']['median']:.3f} cents.", '',
'Potential matches require a YES-taker trade at or above our ask during the recorded quote lifetime. Shared trade volume is allocated only once, chronologically, up to quote size. This does not establish RFQ acceptance, queue priority, access to that flow, or actual fills.', '',
'## Sensitivity and markouts','',
table(['Scenario','Quotes','Contracts','Model EV $'],[[k,v['quote_count'],f"{v['contracts']:.2f}",f"{v['model_edge_dollars']:.4f}"] for k,v in s['scenarios'].items()]),'',
f"Expiry-only sensitivity (ignoring recorded cancellations): {s['expiry_only_sensitivity']['quote_count']} quotes / {s['expiry_only_sensitivity']['contracts']:.2f} contracts. Held-inventory scenario rejected {s['held_inventory_scenario']['risk_rejected_allocations']} allocations; it does not simulate pending reservations or signed portfolio hedges.", '',
table(['Model-mark horizon','Observed quotes','Matched marked contracts','Marked model value $'],[[h,v['observed'],f"{v['matched_quantity']:.2f}",f"{v['matched_model_value_dollars']:.4f}"] for h,v in s['markouts'].items()]),'',
table(['Public-print horizon (+30s grace)','Marked allocations','Contracts','Markout $'],[[h,v['allocations_observed'],f"{v['quantity']:.2f}",f"{v['markout_dollars']:.4f}"] for h,v in s['public_marks'].items()]),'',
'Model marks use the newly replayed fair, not the old fair. Public marks use later trades, not executable liquidation quotes; sparse or absent marks are not zero-return evidence. Neither measure is settlement P&L.', '',
'## Does apparent Kalshi-mid edge relate to liquidity?','',
 'Critical identification limit: all 30 leg snapshots in these 15 trade observations have a raw 1-cent spread on BOTH Kalshi and Polymarket. Actual leg spread variation is zero. The apparent synthetic-width relationship is driven by leg probability levels, not wider versus narrower underlying books. It cannot establish a liquidity-width premium. Adding PM synthetic width barely improves in-sample fit and worsens held-out prediction. Depth varies, but its weak descriptive association is not an established effect.', '',
f"Primary sample: {len(yes)} unique YES-taker trades across {liquidity['markets']} markets; each uses the latest completed still-active quote snapshot. Median snapshot age {liquidity['snapshot_age_seconds']['median']:.2f}s; maximum {liquidity['snapshot_age_seconds']['maximum']:.2f}s. No post-trade snapshots are used.", '',
'Outcome = 100 × (trade YES price − product of selected-side Kalshi leg midpoints). This is apparent gross edge against an independence baseline, not true fair value or fee-net profit. Raw synthetic width = 100 × (product of selected-side leg asks − product of selected-side leg bids). These are underlying-leg books, NOT a recorded executable combo order book. Fee-expanded widths use first-order leg sensitivities; depth is the minimum two-sided displayed leg capacity.', '',
table(['Feature versus apparent Kalshi-mid edge','Pearson r','Spearman rho','Distinct values'],[[k, 'NA' if v['pearson'] is None else f"{v['pearson']:.3f}", 'NA' if v['spearman'] is None else f"{v['spearman']:.3f}",v['distinct_values']] for k,v in correlations.items()]),'',
table(['Linear model','In-sample R²','Leave-one-market-out RMSE ¢','Rank / parameters'],[[k,f"{v['in_sample_r_squared']:.3f}",f"{v['leave_one_market_out_rmse_cents']:.3f}",f"{v['rank']}/{v['parameters']}"] for k,v in models.items()]),'',
'Regressions are unweighted by trade size to prevent one large print dominating. Market-held-out validation reduces repeated-market leakage but cannot remove shared-event dependence. Width/mid construction has mechanical relationships; venue disagreement and stale leg prices can masquerade as liquidity compensation. Coefficients/correlations here are descriptive, not significance tests or a validated trading signal.', '',
'## Blacklist and concentration','',
'Creator policy is preserved, not refit. The recorded cooldown windows contain 6,281 retained requests: 6,259 lacked reviewed mappings and 22 were backlog-skipped. No priceable quote in this cohort was blacklist-blocked, so avoided adverse-selection P&L cannot be estimated. The replay does not establish blacklist efficacy. Correlation-tail filtering newly excluded zero retained quotes; this is not evidence that the filter has no value.', '',
'The potential fills share the NE–SEA event (three spread combos and one totals combo), and several also share the same second fixture. Four combo tickers are not four independent risk bets. This sample cannot support a dependable equity curve or an earnings projection.', '',
'Machine-readable artifacts: liquidity_trade_features.json, liquidity_analysis.json, market_breakdown.json, trade_price_comparisons.json, corrected_quotes.jsonl, fill_time_validation.json and scenario fill files. Per-leg before/after weights and causal replay checks are in ../source/.']
if (R/'fill_time_validation.json').exists():
    validation=read(R/'fill_time_validation.json')
    lines += ['',f"Fill-time state check: {sum(f['passed'] for f in validation)}/{len(validation)} allocations pass fresh-source, fair-move, pricing-guard, risk-regime and minimum-edge checks. This does not recreate every intermediate cancellation check."]
(R/'REPORT.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(dict(liquidity=liquidity,marketrows=marketrows,asks_changed=asks_changed),indent=2))
