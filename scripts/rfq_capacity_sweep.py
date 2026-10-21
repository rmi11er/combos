"""Full-RFQ capacity under no-fill expiry and all-fill retained-cash scenarios."""
import json,sys,hashlib
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.research_capacity import CapacityReplay


def run(terms,source,out):
    rows=json.loads(terms.read_text()); original={r['source_seq']:r for r in json.loads(source.read_text())};results=[];summaries=[]
    policies={'original':{'contract':100,'combo':100,'fixture':250},'500_each':dict.fromkeys(('contract','combo','fixture'),500),'1000_each':dict.fromkeys(('contract','combo','fixture'),1000),'2000_each':dict.fromkeys(('contract','combo','fixture'),2000),'cash_only':dict.fromkeys(('contract','combo','fixture'),10000)}
    for alpha in (0,.25,1):
        for name,caps in policies.items():
            for mode,lifetime in [('unfilled_expiry_3s',3),('all_admitted_fill_no_release',None)]:
                ledger=CapacityReplay(10000,caps,lifetime);counts=Counter();bindings=Counter()
                for r in sorted((r for r in rows if r['reserve_fraction']==alpha),key=lambda r:(original[r['source_seq']]['at'],r['source_seq'])):
                    o=original[r['source_seq']];result={'source_seq':r['source_seq'],'reserve_fraction':alpha,'policy':name,'mode':mode}
                    if r['status']!='priced':result.update(admitted=False,binding_limits=[r['reason']])
                    else:
                        buckets={'contract':[l['key'] for l in r['leg_risks']],'combo':[o['market_ticker']],'fixture':r['fixtures']}
                        result.update(ledger.admit(r['rfq_id'],o['at'],r['fragmentation_cash_bound'],buckets))
                    counts['admitted' if result['admitted'] else 'rejected']+=1;bindings.update(result['binding_limits']);results.append(result)
                summaries.append({'reserve_fraction':alpha,'policy':name,'mode':mode,'counts':dict(counts),'binding_counts':dict(bindings),'peak_committed_dollars':ledger.peak/10000})
    out.mkdir(parents=True,exist_ok=False)
    summary={'scenarios':summaries,'decision_count':len(results),'hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (terms,source,Path(__file__),Path('src/combos/research_capacity.py'))},'limitations':['no acceptance probability or profitability inferred','expiry assumes no fill and immediate release; not live release authority','all-fill mode retains every admitted reservation for entire capture','cash charged in full to each unique underlying and fixture; no hedge credit','upstream payoff, balance precision and sampled market grid assumptions retained']}
    (out/'summary.json').write_text(json.dumps(summary,indent=2));(out/'decisions.json').write_text(json.dumps(results));print(json.dumps([s for s in summaries if s['reserve_fraction']==0],indent=2))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('terms','source','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.terms,a.source,a.out)
