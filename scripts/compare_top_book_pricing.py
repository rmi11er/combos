"""Fixed-source RFQ and markout comparison with causal top-only certificates."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sqlite3
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from combos.event_store import rfq_payload
from combos.rfq_scenario_consumer import RFQScenarioConsumer
from combos.weighted_fair import WeightPolicy
from combos.research_quote_consumer import ResearchQuoteConsumer
from top_book_state_research import TopBookState


def closed(path):
    return sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)


def run(a):
    runtime=json.loads((a.capture/'runtime.json').read_text())
    weights=WeightPolicy(**json.loads((a.capture/'weighting.json').read_text()))
    catalog=json.loads(a.catalog.read_text())
    base=RFQScenarioConsumer(runtime,catalog,weights)
    alt=RFQScenarioConsumer(runtime,catalog,weights)
    replay=json.loads((a.verifications/'rows.json').read_text())
    certificates={(r['source_reference'],r['token']):{'raw_seq':r['raw_seq'],'evidence':r['top']['evidence']}
        for r in replay if r['full']['status']=='rejected' and r['top']['status']=='verified'}
    alt.pm=TopBookState({m['polymarket_yes_token']:m['market_key'] for m in runtime['mappings']
        if m.get('polymarket_yes_token')},certificates)
    policy=json.loads(a.policy.read_text())
    base_quotes=ResearchQuoteConsumer(base,runtime,policy)
    alt_quotes=ResearchQuoteConsumer(alt,runtime,policy)
    policy_counts={'baseline':Counter(),'top':Counter()};policy_changes=[]
    src=closed(a.capture/'events.sqlite');dec=closed(a.worker/'worker/decisions.sqlite');marks=closed(a.worker/'markouts/markouts.sqlite')
    targets=defaultdict(list)
    needed=set()
    for raw, in marks.execute('SELECT value FROM labels'):
        r=json.loads(raw);targets[r['available_source_seq']].append(r);needed.add(r['decision_seq'])
    messages={};rfq_pairs=Counter();mark_pairs=Counter();fair_changes=[];recovered=[];checked=0;mark_checked=0
    decisions=iter(dec.execute('SELECT source_seq,result FROM candidate_decisions ORDER BY source_seq'))
    next_decision=next(decisions,None)
    relevant={'observation','venue_reset','external_raw','book_verification','book_verification_status','book_rebuild','kalshi','rfq','creator_policy'}
    for seq,kind,source,at,raw in src.execute('SELECT seq,kind,source,received_at,payload FROM events ORDER BY seq'):
        payload=json.loads(zlib.decompress(raw)) if kind in relevant else {}
        event=dict(seq=seq,kind=kind,source=source,received_at=at,payload=payload)
        base_quotes.consume(event,price_rfqs=False);alt_quotes.consume(event,price_rfqs=False)
        if seq in needed:messages[seq]=rfq_payload(event)
        if next_decision and seq==next_decision[0]:
            original=json.loads(next_decision[1]);msg=rfq_payload(event)
            expected={k:v for k,v in original['pricing'].items() if k!='research_policy'}
            p=base.revalue(msg,original['evaluation_at'],seq);q=alt.revalue(msg,original['evaluation_at'],seq)
            assert p==expected,('baseline_decision',seq)
            bpq=base_quotes.evaluate(event,p,original['evaluation_at'])
            apq=alt_quotes.evaluate(event,q,original['evaluation_at'])
            assert bpq==original['pricing']['research_policy'],('baseline_policy',seq)
            for name,result in (('baseline',bpq),('top',apq)):
                policy_counts[name][result.get('reason',result['status'])]+=1
            if bpq!=apq:policy_changes.append({'source_seq':seq,'baseline':bpq,'top':apq})
            checked+=1;rfq_pairs[(p['status'],q['status'])]+=1
            if p['status']=='scenario_priced' and q['status']=='scenario_priced':
                bp=next(s for s in p['scenarios'] if s['assumed_usd_per_native_unit']==1)
                ap=next(s for s in q['scenarios'] if s['assumed_usd_per_native_unit']==1)
                fair_changes.append(100*(ap['independent_combo_point']-bp['independent_combo_point']))
            if p['status']!='scenario_priced' and q['status']=='scenario_priced':
                recovered.append({'source_seq':seq,'previous_reason':p.get('reason'),'pricing':q})
            next_decision=next(decisions,None)
        for label in targets.pop(seq,[]):
            msg=messages[label['decision_seq']]
            p=base.revalue(msg,label['valuation_at'],label['decision_seq'])
            q=alt.revalue(msg,label['valuation_at'],label['decision_seq'])
            assert p==label['future_pricing'],('baseline_markout',seq,label['decision_seq'])
            mark_checked+=1;mark_pairs[(p['status'],q['status'])]+=1
    assert next_decision is None and not targets
    summary={'baseline_decisions_exact':checked,'baseline_markout_fairs_exact':mark_checked,
        'rfq_status_pairs':{str(k):v for k,v in rfq_pairs.items()},
        'markout_status_pairs':{str(k):v for k,v in mark_pairs.items()},
        'common_fair_changed':sum(v!=0 for v in fair_changes),
        'max_absolute_common_fair_change_cents':max(map(abs,fair_changes),default=0),
        'additional_priced_rfqs':len(recovered),
        'policy_counts':{k:dict(v) for k,v in policy_counts.items()},
        'peak_committed_dollars':{'baseline':base_quotes.risk.peak/10000,'top':alt_quotes.risk.peak/10000},
        'policy_decisions_changed':len(policy_changes),
        'capacity_mode':policy['capacity_mode'],
        'limitations':['Recorded collection/rebuild actions held fixed; alternative collector behavior not simulated.',
            'Existing entry horizons only; new-entry markouts are not evaluated.',
            'Capacity is a scenario under the reported policy mode, not actual quote acceptance.',
            'No actual acceptance or PnL inference.']}
    a.out.mkdir(parents=True,exist_ok=False)
    (a.out/'summary.json').write_text(json.dumps(summary,indent=2))
    (a.out/'recovered.json').write_text(json.dumps(recovered,indent=2))
    (a.out/'policy_changes.json').write_text(json.dumps(policy_changes,indent=2))
    for db in (src,dec,marks):db.close()
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('capture','worker','verifications','catalog','policy','out'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())
