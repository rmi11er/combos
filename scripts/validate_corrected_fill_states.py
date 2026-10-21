"""Validate corrected tape candidates against as-of recorded feed state."""
import argparse,json,sqlite3,sys,zlib
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from combos.pricing_service import PricingService
from combos.weighted_fair import WeightPolicy

class State:
    def __init__(self):self.data={}
    def get(self,owner,key,default=None):return self.data.get((owner,key),default)

p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--replay-weights',type=Path);a=p.parse_args()
qs={q['quote_key']:q for q in map(json.loads,(a.directory/'corrected_quotes.jsonl').read_text().splitlines())}
fills=json.loads((a.directory/'edge_0.003_delay_0.json').read_text());byrun=defaultdict(list);out=[]
for f in fills:byrun[qs[f['quote_key']]['run']].append(f)
for run,targets in byrun.items():
    targets.sort(key=lambda f:f['at']);c=sqlite3.connect('file:'+str(ROOT/'runs'/run/'events.sqlite')+'?mode=ro',uri=True)
    manifest=json.loads(c.execute("SELECT value FROM state WHERE owner='runtime' AND key='manifest'").fetchone()[0])
    weights=json.loads(a.replay_weights.read_text())[run] if a.replay_weights else manifest['weights']
    state=State();pricer=PricingService(state,manifest['config'],WeightPolicy(**weights))
    index=0;clock=0
    def validate(f):
        q=qs[f['quote_key']];r=dict(f)
        try:
            pricing=pricer.price(q['request']['mve_selected_legs'],f['at'])
            edge=q['yes_ask']-pricing['joint']['point']-q['economics']['maker_fee']/q['quantity']
            reasons=[]
            if not pricing['quote_allowed']:reasons.append(pricing.get('block_reason','pricing_guard'))
            if abs(pricing['joint']['point']-q['pricing']['joint']['point'])>.01+1e-12:reasons.append('fair_move_exceeded')
            if pricing['risk_multiplier']<q['pricing']['risk_multiplier']:reasons.append('risk_regime_tightened')
            if edge+1e-12<.003:reasons.append('point_edge_below_hurdle')
            r.update(passed=not reasons,reasons=reasons,fill_time_point=pricing['joint']['point'],fill_time_edge_cents=100*edge)
        except (KeyError,ValueError,TypeError) as exc:r.update(passed=False,reasons=[str(exc)])
        out.append(r)
    for seq,kind,at,raw in c.execute("SELECT seq,kind,received_at,payload FROM events WHERE kind IN ('observation','fixture_status','venue_reset','heartbeat') ORDER BY seq"):
        clock=max(clock,at)
        while index<len(targets) and targets[index]['at']<clock:
            validate(targets[index]);index+=1
        if index==len(targets):break
        if kind=='heartbeat':continue
        d=json.loads(zlib.decompress(raw))
        if kind=='observation':state.data[('observations',d['market_key']+':'+d['venue'])]=d
        elif kind=='fixture_status':
            old=state.get(kind,d['fixture_key'],{});state.data[(kind,d['fixture_key'])]=dict(d,started=old.get('started',False) or d['phase'] in ('in_play','finished'))
        elif kind=='venue_reset':
            for (owner,key),value in state.data.items():
                if owner=='observations' and value['venue']==d['venue']:value.update(active=False,available_at=at,observed_at=at)
    while index<len(targets):validate(targets[index]);index+=1
    c.close()
(a.directory/'fill_time_validation.json').write_text(json.dumps(out,indent=2))
print(json.dumps([dict(quote_key=f['quote_key'],passed=f['passed'],reasons=f['reasons'],edge=f.get('fill_time_edge_cents')) for f in out],indent=2))
