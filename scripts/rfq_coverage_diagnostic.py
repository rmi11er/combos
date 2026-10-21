"""Causal per-leg source coverage failures at every mapped RFQ arrival."""
import json,sys
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.event_store import EventStore,rfq_payload
from combos.verified_book_state import VerifiedBookState


def reason(book,at,maximum_age=15):
    if not book:return 'not_observed'
    if book['available_at']>at:return 'not_yet_available'
    if not book['active']:return 'inactive'
    if min(book.get('yes_bid_size',0),book.get('yes_ask_size',0))<=0:return 'missing_two_sided_depth'
    if book['observed_at']>at:return 'future_timestamp'
    if at-book['observed_at']>maximum_age:return 'old_timestamp'
    return 'usable'


def run(capture,source,out):
    source_rows=json.loads(source.read_text());excluded={'scenario_priced','exchange_candidate_coverage_missing','kalshi: future or stale','pinnacle_not_yet_available','exact_pinnacle_selector_missing','pinnacle_outcome_inactive_or_changed'}
    wanted={r['source_seq']:r for r in source_rows if r.get('reason',r['status']) in excluded}
    runtime=json.loads((capture/'runtime.json').read_text());maps={m['kalshi_ticker']:m for m in runtime['mappings']}
    state=VerifiedBookState();kalshi={};rows=[];store=EventStore(capture/'events.sqlite');seq=0
    try:
        while True:
            events=store.read(seq,1000,payload_kinds={'observation','book_verification','venue_reset','kalshi','rfq'})
            if not events:break
            for e in events:
                seq=e['seq'];state.consume(e);p=e['payload'];at=e['received_at']
                if e['kind']=='observation' and p.get('venue')=='kalshi':kalshi[p['market_key']]=p
                if e['kind']=='venue_reset' and e['source']=='kalshi':kalshi.clear()
                if seq not in wanted:continue
                msg=rfq_payload(e);details=[]
                for leg in msg['mve_selected_legs']:
                    key=maps[leg['market_ticker']]['market_key'];native=state.books.get(key);candidate=state.pair(key,at)['candidate'];cert=state.certificates.get(key)
                    details.append({'key':key,'kalshi':reason(kalshi.get(key),at),'pm_native':reason(native,at),'pm_candidate':reason(candidate,at),
                        'pm_missing_candidate_reason':None if candidate else reason(native,at),
                        'pm_native_age':None if not native else at-native['observed_at'],
                        'pm_certificate_age':None if not cert else at-cert['evidence']['verified_at']})
                rows.append({'source_seq':seq,'at':at,'original_status':wanted[seq].get('reason',wanted[seq]['status']),'legs':details,
                    'all_exchange_legs_usable':all(l['kalshi']=='usable' and l['pm_candidate']=='usable' for l in details)})
    finally:store.close()
    assert len(rows)==len(wanted)
    bad=Counter(l['key'] for r in rows for l in r['legs'] if l['pm_candidate']!='usable')
    summary={'mapped_rfqs':len(rows),'all_exchange_legs_usable':sum(r['all_exchange_legs_usable'] for r in rows),
        'leg_occurrences':sum(len(r['legs']) for r in rows),
        'kalshi_reasons':dict(Counter(l['kalshi'] for r in rows for l in r['legs'])),
        'pm_candidate_reasons':dict(Counter(l['pm_missing_candidate_reason'] or 'usable' for r in rows for l in r['legs'])),
        'top_pm_missing_keys':bad.most_common(15),'notes':['counts overlap across RFQs sharing legs','old timestamp is not proof the market moved','diagnostic does not fill missing data or change eligibility']}
    out.mkdir(parents=True,exist_ok=False);(out/'summary.json').write_text(json.dumps(summary,indent=2));(out/'decisions.json').write_text(json.dumps(rows));print(json.dumps(summary,indent=2))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('capture','source','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.capture,a.source,a.out)
