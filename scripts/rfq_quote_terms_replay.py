"""Apply captured series terms and publication-causal creator state to RFQs."""
import json,sys,sqlite3,zlib,hashlib
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.research_rfq_quote import solve_quote
from combos.payoff_risk import canonical_leg_risk
from combos.event_store import rfq_payload


def run(capture,source,out):
    runtime=json.loads((capture/'runtime.json').read_text());inputs=json.loads(source.read_text())
    wanted={r['source_seq']:r for r in inputs if r['status']=='scenario_priced'}
    maps={m['market_key']:m for m in runtime['mappings']}; states={}; rows=[]
    db=sqlite3.connect(str((capture/'events.sqlite').resolve()))
    for seq,kind,at,payload in db.execute("select seq,kind,received_at,payload from events where kind in ('creator_policy','kalshi','rfq') order by seq"):
        if kind!='creator_policy' and seq not in wanted:continue
        p=json.loads(zlib.decompress(payload))
        if kind=='creator_policy':states[p['creator_id']]={'publication_seq':seq,**p['state']};continue
        r=wanted[seq];msg=rfq_payload({'kind':kind,'payload':p});state=states.get(msg.get('creator_id'),{'status':'clear'})
        status=state['status']
        if status=='cooldown' and at>=state['expires_at']:status='watch'
        terms=next((v for k,v in sorted(runtime['combo_terms'].items(),key=lambda kv:-len(kv[0])) if r['market_ticker'].startswith(k)),None)
        s=next(v for v in r['scenarios'] if v['assumed_usd_per_native_unit']==1)
        for alpha in (0,.25,1):
            row={'source_seq':seq,'rfq_id':r['rfq_id'],'reserve_fraction':alpha,'creator_status':status,'creator_publication_seq':state.get('publication_seq')}
            try:
                if not msg.get('creator_id'):raise ValueError('creator_missing')
                if status in ('blocked','cooldown'):raise ValueError('creator_'+status)
                if not terms or not terms.get('fee_reference'):raise ValueError('missing_terms')
                if not terms['verified_at']<=at<terms['valid_until']:raise ValueError('terms_not_causal_or_expired')
                q=solve_quote(s['independent_combo_point'],s['independent_marginal_upper'],alpha,'.003',contracts=r.get('requested_contracts'),target_cost=r.get('target_cost_dollars'),rate=terms['maker_fee_rate'],ranges=terms['price_ranges'])
                row.update(q,status='priced',maker_rate=terms['maker_fee_rate'],fee_reference=terms['fee_reference'],grid_validation=terms['grid_validation'],
                    leg_risks=[canonical_leg_risk(maps[l['market_key']],l['side'],'sell',q['quantity_bound']) for l in s['legs']],
                    fixtures=sorted(set(maps[l['market_key']]['fixture_key'] for l in s['legs'])))
            except ValueError as exc:row.update(status='excluded',reason=str(exc))
            rows.append(row)
    db.close();assert len(rows)==len(wanted)*3
    out.mkdir(exist_ok=False,parents=True)
    summary={'rfqs':len(wanted),'rows':len(rows),'counts':dict(Counter(r.get('reason',r['status']) for r in rows)),
        'maker_rates':dict(Counter(str(r['maker_rate']) for r in rows if r['status']=='priced')),
        'creator_statuses':dict(Counter(r['creator_status'] for r in rows)),
        'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'limitations':['series grids sampled from representative markets; per-combo validation pending','balance precision scenario .0001','no portfolio allocations or executions']}
    (out/'summary.json').write_text(json.dumps(summary,indent=2));(out/'decisions.json').write_text(json.dumps(rows,default=str));print(json.dumps(summary,indent=2))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('capture','source','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.capture,a.source,a.out)
