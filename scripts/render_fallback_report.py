"""Human-readable expanded coverage replay and conservative capital scenario."""
import json,hashlib
from pathlib import Path
from collections import defaultdict,Counter
from bisect import bisect_left
from corrected_shadow_review import fillstats
from shadow_trade_review import stamp
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'runs/shadow_exchange_fallback_20260909'
def read(name):return json.loads((D/name).read_text())
s=read('summary.json');p=read('performance.json');risk=read('joint_risk_summary.json');fills=read('joint_risk_fills.json')
qs={q['quote_key']:q for q in map(json.loads,(D/'quotes.jsonl').open())}
validation=read('fill_and_model_mark_validation.json');valid=read('validated_potential_fills.json')
marks={(r['allocation'],r['horizon']):r for r in validation};tapes=defaultdict(list)
for t in map(json.loads,(D/'quoted_market_trades.jsonl').open()):tapes[t['ticker']].append(t)
for tape in tapes.values():tape.sort(key=lambda t:t['created_time'])
modelmarks={};publicmarks={}
for h in (5,30,120):
    model=[];public=[]
    for f in fills:
        m=marks.get((f['allocation'],h))
        if m and m['available']:model.append(dict(quantity=f['quantity'],dollars=m['model_value_dollars'],edge_cents=m['edge_cents']))
        tape=tapes[f['ticker']];times=[stamp(t['created_time']) for t in tape];i=bisect_left(times,f['at']+h)
        if i<len(times) and times[i]<=min(f['at']+h+30,1788999600):
            public.append(dict(quantity=f['quantity'],dollars=f['quantity']*(f['hypothetical_yes_price']-float(tape[i]['yes_price_dollars']))))
    modelmarks[str(h)]=dict(allocations=len(model),contracts=sum(m['quantity'] for m in model),model_value_dollars=sum(m['dollars'] for m in model),negative_edges=sum(m['edge_cents']<0 for m in model))
    publicmarks[str(h)]=dict(allocations=len(public),contracts=sum(m['quantity'] for m in public),markout_dollars=sum(m['dollars'] for m in public))
markets=[];groups=defaultdict(list)
for f in fills:groups[f['ticker']].append(f)
for ticker,fs in groups.items():
    qty=sum(f['quantity'] for f in fs)
    markets.append(dict(ticker=ticker,legs=qs[fs[0]['quote_key']]['request']['mve_selected_legs'],**fillstats(fs),
        ask_cents=100*sum(f['quantity']*f['hypothetical_yes_price'] for f in fs)/qty,
        public_price_cents=100*sum(f['quantity']*f['public_yes_price'] for f in fs)/qty))
markets.sort(key=lambda r:r['collateral_dollars'],reverse=True)
reportdata=dict(model_marks=modelmarks,public_marks=publicmarks,markets=markets,
    fill_time_validated=fillstats(valid),funded=fillstats(fills),funded_leg_sources=dict(Counter(source for f in fills for source in qs[f['quote_key']]['pricing']['source_sets'])))
(D/'funded_performance.json').write_text(json.dumps(reportdata,indent=2)+'\n')
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(map(str,row))+' |' for row in rows])
def fm(v):return f'{v:,.2f}'
counts=s['counts'];raw=p['scenarios']['0']
fixture_rows=sorted(((k.removeprefix('fixture:'),v) for k,v in risk['ending_used'].items() if k.startswith('fixture:') and v>1e-6),key=lambda r:r[1],reverse=True)
lines=['# Expanded source-fallback session replay','',
'## Main result','',
f"Across the September 9 16:11:32–19:20 Central session, {counts['priceable']:,} of {counts['requests']:,} retained RFQs are priceable using the reconstructed available-source state. An initial conservative pending-reservation pass admits {p['quotes']:,} quote intents. A second chronological scenario combining pending quotes and held fills admits {risk['counts']['quote_intents_admitted']:,} of those intents and produces {risk['quote_count']} potential quote fills across {risk['market_count']} markets: {fm(risk['contracts'])} contracts, ${fm(risk['collateral_dollars'])} held collateral, and ${fm(risk['model_edge_dollars'])} quote-time model edge. None are actual executions or settlement profit.", '',
'## Implemented policy','',
'- 1,689 exact week-one mappings, including all 61 previously verified period spread/total mappings and 1,235 additional Kalshi-only mappings from retained contract definitions. September 20 games are excluded.',
'- Available-source liquidity/freshness weighted fair. Fresh Kalshi/PM exchanges can stand alone; no Pinnacle-only pricing. Unavailable or unreviewed Pinnacle selectors exclude Pinnacle, not the combo.',
'- Exchange source gate: at least $100 displayed on BOTH top-book sides and raw spread at most 5 cents. These configurable initial thresholds are not calibrated. A valid source must also meet the existing age, payoff and provenance checks.',
'- Single exchange gets weight 1. Two exchange sources retain the 60% cap. One exchange plus Pinnacle allows the exchange up to 80% and retains Pinnacle at most 20%. The consensus lean requires all three sources.',
'- Point fair plus 0.30-cent minimum net charge, rounded up to permitted ticks; no added uncertainty/dependence reserve. Existing rho 0.05 correlation-tail test remains active.',
'- Existing $250 ticket, $500 contract/combo, $1,000 fixture and $10,000 total limits. Conservative gross accounting; no cash-netting credit. Creator policy and pregame restrictions remain.',
'- Optional PM/Pinnacle collector failure no longer automatically stops the entire fallback run; source age checks still prevent continued use of stale prices. Kalshi and core worker failures remain fatal.',
'- Six working NFL configurations updated. No collector run or live order submission started. Current fee validity, metadata freshness and live execution readiness remain independent prerequisites.', '',
'## Coverage funnel','',
table(['Stage / first failure','RFQs'],[[k,f'{v:,}'] for k,v in counts.items()]),'',
'The `priceable` count overlaps subsequent quote/risk outcomes; other failure labels reflect their first failed check. Only 14,030 requests remain unmapped; their missing legs are September 20 moneylines. Same-fixture combinations remain outside this joint model. The 4,646 missing-source-reference failures were not assigned invented source prices.', '',
f"The captured fallback state quotes {p['markets']:,} tickers versus 310 previously; {p['markets_with_public_trades']:,} have public trades in the full session. Newly quoted requests include {p['original_reasons_of_new_quotes']['reviewed_mapping_missing']:,} originally mapping-rejected requests.", '',
'## Recovered market volume','',
f"Retrieved and retained all pages across 38 time buckets: {p['public_session']['trades']:,} deduplicated public trades over the session. The {p['markets']:,} newly quoted tickers contain {p['quoted_market_public_session']['trades']:,} trades, {fm(p['quoted_market_public_session']['contracts'])} contracts, and ${fm(p['quoted_market_public_session']['yes_seller_collateral'])} unhedged YES-seller collateral turnover. Comparable YES-taker turnover is ${fm(p['quoted_market_public_session']['yes_taker_seller_collateral'])}.", '',
f"Within the candidate quote lifetimes there are {p['active_window_trades']:,} distinct trades and ${fm(p['active_window_yes_taker_collateral'])} comparable YES-taker seller collateral. These windows are from the initial quote-intent cohort, not solely the smaller funded scenario. Across {p['active_comparisons']['pairs']:,} overlapping quote/trade comparisons, mean public-minus-ask is {p['active_comparisons']['public_minus_ask_cents']['mean']:.3f} cents; median {p['active_comparisons']['public_minus_ask_cents']['median']:.3f} cents. Repeated pairs are not independent observations.", '',
'All retrieved trades are flagged `is_block_trade=false`. This is public order-book competitiveness and conditional participation, not verified RFQ acceptance. Seller collateral turnover is contracts × (1 − YES price), without public fee/margin offsets; it is not measured peak market margin. Broader retrieval and earlier per-ticker windows also change the denominator versus the old report.', '',
'## Potential fills versus capital-constrained participation','',
table(['Scenario','Quote fills','Markets','Contracts','Collateral $','Model edge $'],[
    ['Prior consensus replay',10,4,'260.61','199.19','0.855'],
    ['Expanded initial quotes, before held-inventory limits',raw['quote_count'],raw['market_count'],fm(raw['contracts']),fm(raw['collateral_dollars']),fm(raw['model_edge_dollars'])],
    ['After fill-time source/edge checks',reportdata['fill_time_validated']['quote_count'],reportdata['fill_time_validated']['market_count'],fm(reportdata['fill_time_validated']['contracts']),fm(reportdata['fill_time_validated']['collateral_dollars']),fm(reportdata['fill_time_validated']['model_edge_dollars'])],
    ['Combined pending + held gross-risk scenario',risk['quote_count'],risk['market_count'],fm(risk['contracts']),fm(risk['collateral_dollars']),fm(risk['model_edge_dollars'])]]),'',
f"In the funded scenario, {risk['trade_count']} unique public prints support {len(fills)} allocations across {risk['quote_count']} quote responses. Volume is never allocated twice. Our volume-weighted charge is {100*risk['model_edge_dollars']/risk['contracts']:.3f} cents versus {100*risk['public_price_edge_at_quote_fair_dollars']/risk['contracts']:.3f} cents at the corresponding public price against the same quote-time fair. The latter is a selected matched sample, not all market trades.", '',
'The $29,515 unconstrained collateral figure must NOT be presented as attainable deployment under a $10,000 budget. Both pending and held exposure are checked in the final scenario. It intentionally does not revive initially risk-blocked quote intents or reassign failed matches to other quotes, so it is not an exhaustive policy-optimal full-engine simulation.', '',
'## Largest funded markets','',
table(['Selected legs','Quote fills','Contracts','Ask ¢','Public ¢','Collateral $','Model edge $'],[[
    ' + '.join(l['market_ticker']+' '+l['side'] for l in m['legs']),m['quote_count'],fm(m['contracts']),f"{m['ask_cents']:.3f}",f"{m['public_price_cents']:.3f}",fm(m['collateral_dollars']),fm(m['model_edge_dollars'])] for m in markets[:12]]),'',
'All 45 markets are in funded_performance.json. Fixture exposure below is overlapping: a combo contributes to each constituent fixture, so these rows must not be summed into cash collateral.', '',
table(['Fixture','Ending attributed liability $'],[[k,fm(v)] for k,v in fixture_rows]),'',
'## Markouts on the funded allocations','',
table(['Horizon seconds','Model-mark allocations','Model-mark contracts','Marked model value $','Negative model edges'],[[h,v['allocations'],fm(v['contracts']),fm(v['model_value_dollars']),v['negative_edges']] for h,v in modelmarks.items()]),'',
table(['Horizon (+30s public-print grace)','Public-mark allocations','Contracts','Public markout $'],[[h,v['allocations'],fm(v['contracts']),fm(v['markout_dollars'])] for h,v in publicmarks.items()]),'',
'Model marks use the same fallback fair reconstructed at fill time plus the stated horizon. They are not independent evidence. Public marks use the first subsequent same-ticker trade at/after the horizon, allowing 30 seconds; positive means favorable to our YES-selling quote. They are not executable liquidation prices and missing observations are not zero returns.', '',
'## Replay boundaries and verification','',
'- Original databases remain read-only. Recovered Kalshi prices/depth come from recorded unmapped-book events, not today’s prices or assumed liquidity. Additional Pinnacle observations are reconstructed from recorded raw snapshots using the existing delivery-age policy. Missing PM books are not manufactured.',
'- State at original source sequence is used with original decision/publication timestamps. Creator eligibility and backlog decisions remain historical; new worker throughput and changed blacklist history are not simulated.',
'- Quote lifetime is three seconds from decision time. Fill-time source, minimum edge, fair-move and risk-regime checks remove 80 of 2,015 initial allocations. Every intermediate cancellation is NOT replayed, so potential participation can still be optimistic.',
'- Full-game moneyline tie normalization is retained; exact period spread selectors receive no double tie discount. No separate reserve has been introduced.',
'- Fallback/config/runtime regression checks pass. The broad suite still has the previously identified frozen-candidate hash mismatch and four scratch-lock cleanup failures; frozen production approval has not been renewed.', '',
'## Interpretation','',
'The prior low volume was largely an eligibility/capture artifact. Expanded mappings and fallback pricing produce ample priceable traffic. Under these assumptions, event/contract concentration and pending reservations constrain participation much more than the total cash ceiling. This does not establish live acceptance rates or justify relaxing caps/edge from one session.', '',
'Artifacts: quotes.jsonl; quoted_market_trades.jsonl; potential_fills.json; validated_potential_fills.json; joint_risk_fills.json; funded_performance.json; fill_and_model_mark_validation.json; active_price_comparisons.json; public_session/manifest.json and compressed raw pages.']
(D/'REPORT.md').write_text('\n'.join(lines)+'\n')
paths=[ROOT/'config/runtime_nfl_authorized_shadow_20260910.json',ROOT/'config/weighting.json',ROOT/'src/combos/pricing_service.py',ROOT/'src/combos/weighted_fair.py',ROOT/'scripts/replay_exchange_fallback.py']
(D/'replay_provenance.json').write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},indent=2)+'\n')
print(json.dumps(dict(model_marks=modelmarks,public_marks=publicmarks,fixture_exposure=fixture_rows,peak_total=risk['peak_used']['total']),indent=2))
