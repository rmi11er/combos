"""Full-census integrated policy comparison to independently audited staged outputs."""
import json,sys,time,argparse,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.event_store import EventStore
from combos.rfq_scenario_consumer import RFQScenarioConsumer
from combos.research_quote_consumer import ResearchQuoteConsumer
from combos.weighted_fair import WeightPolicy


def run(a):
    runtime=json.loads((a.capture/'runtime.json').read_text());weights=WeightPolicy(**json.loads((a.capture/'weighting.json').read_text()))
    policy={'reserve_fraction':0,'edge_per_combo':.003,'native_stake_usd_scale':1,'capacity_mode':'all_admitted_fill_no_release','capital_dollars':10000,'caps':dict.fromkeys(('contract','combo','fixture'),1000)}
    c=ResearchQuoteConsumer(RFQScenarioConsumer(runtime,json.loads(a.catalog.read_text()),weights),runtime,policy)
    terms={r['source_seq']:r for r in json.loads((a.terms/'decisions.json').read_text()) if r['reserve_fraction']==0}
    risk={r['source_seq']:r for r in json.loads((a.capacity/'decisions.json').read_text()) if r['reserve_fraction']==0 and r['policy']=='1000_each' and r['mode']==policy['capacity_mode']}
    store=EventStore(a.capture/'events.sqlite');seq=0;rfqs=0;matched=set();start=time.perf_counter()
    try:
        while True:
            events=store.read(seq,1000)
            if not events:break
            for e in events:
                seq=e['seq'];r=c.consume(e)
                if r is None:continue
                rfqs+=1
                if seq not in terms:continue
                p=r['research_policy'];t=terms[seq];k=risk[seq]
                for name,value in p['quote'].items():
                    if t[name]!=value:raise ValueError('quote mismatch '+name)
                for name,value in p['admission'].items():
                    if k[name]!=value:raise ValueError('risk mismatch '+name)
                if p['creator_status']!=t['creator_status'] or p['leg_risks']!=t['leg_risks']:raise ValueError('creator/canonical risk mismatch')
                matched.add(seq)
    finally:store.close()
    if matched!=set(terms):raise ValueError('incomplete priced census')
    result={'rfqs':rfqs,'priced_policy_rows_matched':len(matched),'exact_quote_risk_creator_parity':True,'elapsed_seconds':time.perf_counter()-start,'policy':policy,'scope':'one diagnostic policy, full saved RFQ census; not production selection'}
    a.out.mkdir(parents=True,exist_ok=False);(a.out/'verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('capture','catalog','terms','capacity','out'):p.add_argument('--'+n,type=Path,required=True)
    run(p.parse_args())
