#!/usr/bin/env python3
"""Bounded read-only account/discovery/NFL odds probe; never starts trading."""
import argparse
import gzip
import json
from pathlib import Path
import sys
import time
import requests

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from combos.oddspapi import OddsPapi, redact_credentials


def subscribed_pinnacle(account, sport_id):
    slugs={book for s in account.get('subscriptions',[]) if s.get('is_active') is True
           and sport_id in s.get('sport_ids',[]) for book in s.get('bookmakers',{})
           if book in ('pinnacle','pinnacle+30')}
    if len(slugs)!=1:raise ValueError('unique entitled Pinnacle feed not found')
    return next(iter(slugs))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--key-file',type=Path,required=True)
    p.add_argument('--delete-key-file',action='store_true')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--discovery-from',type=Path,help='Reuse sport/tournament IDs from a prior probe summary')
    args=p.parse_args(); report={'requests':[], 'complete':False}
    try:
        key=args.key_file.read_text().strip()
        if not key:raise ValueError('empty key file')
        args.out.mkdir(parents=True,exist_ok=True)
        previous=float('-inf'); session=requests.Session()
        def get(endpoint,params=None):
            nonlocal previous
            if len(report['requests'])>=6:raise ValueError('six-request probe limit reached')
            time.sleep(max(0.,5.05-(time.monotonic()-previous)))
            previous=time.monotonic(); start=time.time()
            item={'endpoint':endpoint,'params':params or {},'started_at':start}
            report['requests'].append(item)
            try:
                r=session.get(OddsPapi.BASE+'/'+endpoint,params={**(params or {}),'apiKey':key},
                              timeout=20,allow_redirects=False)
            except requests.RequestException:
                raise RuntimeError('transport failed; credential-bearing details suppressed') from None
            item.update(status=r.status_code,elapsed_seconds=time.time()-start)
            try: payload=redact_credentials(r.json())
            except ValueError:raise RuntimeError('non-JSON response') from None
            # Also scrub the actual value if a provider echoes it in an error URL.
            payload=json.loads(json.dumps(payload).replace(key,'[REDACTED]'))
            envelope={'request':{'endpoint':endpoint,'params':params or {}},
                      'retrieved_at':time.time(),'http_status':r.status_code,'payload':payload}
            name=f'{len(report["requests"]):02d}_{endpoint}.json.gz'
            with gzip.open(args.out/name,'wt') as f:json.dump(envelope,f,separators=(',',':'))
            item['file']=name
            print(json.dumps({'endpoint':endpoint,'status':r.status_code,'elapsed_seconds':item['elapsed_seconds']}),flush=True)
            if r.status_code!=200:raise RuntimeError(f'HTTP {r.status_code} on {endpoint}; see redacted response')
            return payload
        def account_summary(payload):
            return [{k:s.get(k) for k in ('is_active','valid_from','valid_until','bookmakers','sport_ids',
                                          'request_limit','request_count','websocket_access')}
                    for s in payload.get('subscriptions',[]) if s.get('is_active') is True]
        account=get('account');report['account_before']=account_summary(account)
        if args.discovery_from:
            prior=json.loads(args.discovery_from.read_text());sport=prior['sport'];tournament=prior['tournament']
            if sport['slug']!='american-football' or tournament['tournamentSlug']!='nfl':
                raise ValueError('prior discovery is not NFL')
            report['discovery_reference']=str(args.discovery_from)
        else:
            sports=get('sports',{'language':'en'})
            candidates=[s for s in sports if s.get('slug')=='american-football' or s.get('sportName','').lower()=='american football']
            if len(candidates)!=1:raise ValueError('unique American football sport not found')
            sport=candidates[0]
            tournaments=get('tournaments',{'sportId':sport['sportId'],'language':'en'})
            candidates=[t for t in tournaments if t.get('tournamentSlug','').lower()=='nfl' or t.get('tournamentName','').lower()=='nfl']
            if len(candidates)!=1:raise ValueError('unique NFL tournament not found')
            tournament=candidates[0]
        report.update(sport=sport,tournament=tournament)
        bookmaker=subscribed_pinnacle(account,sport['sportId']);report['bookmaker']=bookmaker
        odds=get('odds-by-tournaments',{'tournamentIds':str(tournament['tournamentId']),
                 'bookmakers':bookmaker,'verbosity':3,'oddsFormat':'decimal'})
        report['odds_shape']={'type':type(odds).__name__,
            'length':len(odds),'keys':list(odds)[:20] if isinstance(odds,dict) else None}
        report['account_after']=account_summary(get('account'))
        report['complete']=True
    except Exception as exc:
        # Known local errors are safe; unexpected exceptions may include request URLs.
        report['error']=str(exc) if isinstance(exc,(RuntimeError,ValueError)) else type(exc).__name__
    finally:
        if args.delete_key_file:
            args.key_file.unlink(missing_ok=True)
            report['temporary_key_file_deleted']=not args.key_file.exists()
        args.out.mkdir(parents=True,exist_ok=True)
        (args.out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    return 0 if report['complete'] else 1


if __name__=='__main__':sys.exit(main())
