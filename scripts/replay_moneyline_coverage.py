"""Causal mapping/pricing coverage replay, not simulated executions."""
import json,sqlite3,zlib,hashlib
from collections import Counter
from pathlib import Path
from enable_nfl_moneylines import enable
from combos.pricing_service import PricingService
from combos.rfq_scope import check_mappings
from combos.weighted_fair import WeightPolicy

ROOT=Path(__file__).resolve().parents[1]
class State:
    def __init__(self):self.data={}
    def get(self,owner,key,default=None):return self.data.get((owner,key),default)

source=ROOT/'runs/morning_research_20260908/pinnacle_delivery_mapping_review/runtime_reviewed_candidates.json'
review=ROOT/'runs/nfl_all_payoff_enumeration_20260909/rows.json'
candidates=json.loads(source.read_text())['mappings'];reviews={r['market_key']:r['review'] for r in json.loads(review.read_text())}
digest=hashlib.sha256(review.read_bytes()).hexdigest()
results=[]
for run in ('shadow_20260909_161131','shadow_20260909_172437'):
    c=sqlite3.connect(f'file:{ROOT}/runs/{run}/events.sqlite?mode=ro',uri=True)
    manifest=json.loads(c.execute("SELECT value FROM state WHERE owner='runtime' AND key='manifest'").fetchone()[0])
    config,_=enable(manifest['config'],candidates,reviews,digest)
    state=State();pricer=PricingService(state,config,WeightPolicy(**manifest['weights']))
    decisions={seq:json.loads(raw).get('reason') or json.loads(raw)['status'] for seq,raw in c.execute('SELECT source_seq,result FROM decisions')}
    counts=Counter();coverage=Counter();missing_sources=Counter();new_tickers=set()
    for seq,kind,at,raw in c.execute("SELECT seq,kind,received_at,payload FROM events WHERE kind IN ('kalshi','observation','fixture_status','venue_reset') ORDER BY seq"):
        if kind=='kalshi' and seq not in decisions:continue
        d=json.loads(zlib.decompress(raw))
        if kind=='observation':state.data[('observations',d['market_key']+':'+d['venue'])]=d
        elif kind=='fixture_status':
            old=state.get(kind,d['fixture_key'],{})
            state.data[(kind,d['fixture_key'])]=dict(d,started=old.get('started',False) or d['phase'] in ('in_play','finished'))
        elif kind=='venue_reset':
            for (owner,key),value in state.data.items():
                if owner=='observations' and value['venue']==d['venue']:value.update(active=False,available_at=at,observed_at=at)
        else:
            original=decisions[seq];counts['total_rfqs']+=1
            if original!='reviewed_mapping_missing':continue
            counts['original_mapping_rejected']+=1
            q=d.get('msg',d);legs=q['mve_selected_legs'];mappings=pricer.registry.resolve(legs)
            if any(m is None for m in mappings):counts['still_missing_mapping']+=1;continue
            counts['all_legs_now_mapped']+=1;new_tickers.add(q['market_ticker'])
            try:check_mappings(legs,mappings,config)
            except ValueError as exc:counts[str(exc)]+=1;continue
            counts['newly_mapped_distinct_fixture_rfqs']+=1
            absent={v for m in mappings for v in ('kalshi','polymarket','pinnacle') if state.get('observations',m['market_key']+':'+v) is None}
            for v in absent:missing_sources[v]+=1
            if absent:coverage['missing_recorded_observations:'+','.join(sorted(absent))]+=1;continue
            try:
                pricing=pricer.price(legs,at)
                coverage['priceable' if pricing['quote_allowed'] else pricing.get('block_reason','pricing_guard')]+=1
            except (ValueError,KeyError,TypeError) as exc:coverage[str(exc)]+=1
    c.close()
    result=dict(run=run,counts=dict(counts),newly_mapped_tickers=len(new_tickers),pricing_coverage=dict(coverage),missing_source_rfqs=dict(missing_sources))
    results.append(result);print(json.dumps(result),flush=True)
total=Counter();coverage=Counter();missing=Counter()
for r in results:total.update(r['counts']);coverage.update(r['pricing_coverage']);missing.update(r['missing_source_rfqs'])
out=dict(runs=results,total=dict(total),pricing_coverage=dict(coverage),missing_source_rfqs=dict(missing),
    limitation='Newly eligible requests priced at source receipt using prior recorded observations; no assumed missing prices, no execution/risk/creator replay. Mapping checks are exact. Priceability is not a response or fill count.')
folder=ROOT/'runs/shadow_consensus_replay_20260909/results'
(folder/'moneyline_coverage_replay.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
