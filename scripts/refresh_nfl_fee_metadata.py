"""Refresh public market-specific fees, preserving reviewed payoff identities."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import time
import requests

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from combos.nfl_matching import kalshi_rates,polymarket_fee
from combos.payoff_risk import nfl_risk_identity


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default='config/runtime_nfl_week1.json')
    parser.add_argument('--raw-dir',required=True)
    parser.add_argument('--polymarket-events-url',required=True)
    parser.add_argument('--refresh-combo-terms',action='store_true',
                        help='also reverify configured combo series fees and sampled price grids')
    args=parser.parse_args()
    if not args.polymarket_events_url.startswith('https://gamma-api.polymarket.com/events?'):
        raise ValueError('expected public Gamma events endpoint')
    path=Path(args.config);config=json.loads(path.read_text());folder=Path(args.raw_dir);folder.mkdir(parents=True,exist_ok=False)
    combo_ids={prefix:prefix.rstrip('-') for prefix in config['combo_terms']} if args.refresh_combo_terms else {}
    ids=sorted({m['kalshi_ticker'].split('-')[0] for m in config['mappings']} | set(combo_ids.values()))
    base='https://external-api.kalshi.com/trade-api/v2'
    jobs=[('polymarket',args.polymarket_events_url)]
    jobs.extend(('series_'+s,base+'/series/'+s) for s in ids)
    jobs.extend(('changes_'+s,base+'/series/fee_changes?series_ticker='+s+'&show_historical=true') for s in ids)
    for prefix,sid in combo_ids.items():
        url=config['combo_terms'][prefix]['grid_reference']
        if not url.startswith(base+'/markets/'):raise ValueError('unexpected combo grid reference')
        jobs.append(('grid_'+sid,url))
    def fetch(job):
        name,url=job;r=requests.get(url,timeout=40);r.raise_for_status()
        record={'url':url,'retrieved_at':time.time(),'payload':r.json()}
        raw=json.dumps(record,indent=2);(folder/(name+'.json')).write_text(raw)
        return name,{**record,'sha256':hashlib.sha256(raw.encode()).hexdigest()}
    with ThreadPoolExecutor(max_workers=3) as pool:sources=dict(pool.map(fetch,jobs))
    events=sources['polymarket']['payload']
    if len(events)>=100:raise ValueError('event response may require pagination')
    pm={str(m['id']):m for e in events for m in e['markets']}
    for mapping in config['mappings']:
        sid=mapping['kalshi_ticker'].split('-')[0];source=sources['series_'+sid];changes=sources['changes_'+sid]
        checked=min(source['retrieved_at'],changes['retrieved_at']);expiry=checked+86400
        for change in changes['payload']['series_fee_change_arr']:
            at=datetime.fromisoformat(change['scheduled_ts'].replace('Z','+00:00')).timestamp()
            if at>checked:expiry=min(expiry,at)
        mapping['fees']['kalshi'].update(rate=kalshi_rates(source['payload']['series'])['taker'],
            fee_model='venue_cash_v2',balance_precision='.0001',precision_basis='direct_member_reference; verify account before execution',
            verified_at=checked,valid_until=expiry,reference=source['url']+'#sha256='+source['sha256'])
        if mapping.get('polymarket_market_id'):
            market=pm[str(mapping['polymarket_market_id'])]
            if market['conditionId']!=mapping['polymarket_condition_id']:raise ValueError('Polymarket payoff identity changed')
            mapping['fees']['polymarket'].update(rate=polymarket_fee(market),fee_model='venue_cash_v2',
                verified_at=sources['polymarket']['retrieved_at'],valid_until=sources['polymarket']['retrieved_at']+86400,
                reference='https://gamma-api.polymarket.com/markets/'+str(market['id'])+'#events-sha256='+sources['polymarket']['sha256'])
        mapping['risk_identity']=nfl_risk_identity(mapping)
    for prefix,sid in combo_ids.items():
        source=sources['series_'+sid];changes=sources['changes_'+sid];grid=sources['grid_'+sid]
        market=grid['payload']['market']
        if not market['ticker'].startswith(prefix) or not market.get('price_ranges'):
            raise ValueError('combo grid identity or ranges missing')
        checked=min(source['retrieved_at'],changes['retrieved_at'],grid['retrieved_at']);expiry=checked+86400
        for change in changes['payload']['series_fee_change_arr']:
            at=datetime.fromisoformat(change['scheduled_ts'].replace('Z','+00:00')).timestamp()
            if at>checked:expiry=min(expiry,at)
        config['combo_terms'][prefix].update(maker_fee_rate=kalshi_rates(source['payload']['series'])['maker'],
            fee_reference=source['url']+'#sha256='+source['sha256'],price_ranges=market['price_ranges'],
            verified_at=checked,valid_until=expiry,fee_changes=changes['payload'],
            metadata_sha256={'series':source['sha256'],'changes':changes['sha256'],'grid':grid['sha256']})
    report={'mappings_checked':len(config['mappings']),'risk_families':len({m['risk_identity']['key'] for m in config['mappings']}),
        'kalshi_taker_rates':sorted({m['fees']['kalshi']['rate'] for m in config['mappings']}),
        'polymarket_taker_rates':sorted({m['fees']['polymarket']['rate'] for m in config['mappings'] if m.get('polymarket_market_id')}),
        'sources':{k:{f:v[f] for f in ('url','retrieved_at','sha256')} for k,v in sources.items()},
        'execution_balance_precision':'not account-verified; reference uses direct-member .0001',
        'combo_terms':'refreshed series fees and sampled grids' if combo_ids else 'not refreshed; retain independent validity gate'}
    (folder/'report.json').write_text(json.dumps(report,indent=2))
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(config,indent=2)+'\n');temp.replace(path)
    print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2))


if __name__=='__main__':main()
