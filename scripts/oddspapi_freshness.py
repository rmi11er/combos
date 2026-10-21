#!/usr/bin/env python3
"""Bounded repeated-poll validation, account usage and market catalog evidence."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from combos.oddspapi import OddsPapi
from combos.feed_freshness import FreshnessAudit
from combos.request_budget import RequestBudget


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--key-file',type=Path);p.add_argument('--delete-key-file',action='store_true')
    p.add_argument('--polling',type=Path,default=ROOT/'config/oddspapi_polling.json')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--polls',type=int,default=11);p.add_argument('--interval',type=float,default=30)
    args=p.parse_args()
    if not 2<=args.polls<=21 or not 30<=args.interval<=60:raise ValueError('bounded probe requires 2–21 polls, 30–60s apart')
    if args.delete_key_file and not args.key_file:raise ValueError('no key file to delete')
    args.out.mkdir(parents=True,exist_ok=False)
    audit=FreshnessAudit();report={'complete':False,'requests_attempted':0};budget=None;handle=None
    try:
        key=args.key_file.read_text().strip() if args.key_file else os.getenv('ODDSPAPI_API_KEY')
        if not key:raise ValueError('API key unavailable')
        cfg=json.loads(args.polling.read_text());bookmaker=cfg['bookmakers'][0]
        audit.bookmaker=bookmaker
        budget_path=Path(cfg['budget_path']).resolve();budget_path.parent.mkdir(parents=True,exist_ok=True)
        handle=open(str(budget_path)+'.collector.lock','a');fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        budget=RequestBudget(budget_path,cfg['billing_cycle_start'],cfg['billing_cycle_end'],
            cfg['subscription_request_limit'],cfg['reserve_fraction'],cfg['known_used'])
        class CappedBudget:
            def claim(self,endpoint):
                if report['requests_attempted']>=args.polls+5:raise ValueError('probe request ceiling reached')
                report['requests_attempted']+=1;budget.claim(endpoint)
        client=OddsPapi(args.out/'raw',api_key=key,request_budget=CappedBudget())
        account=client.get('account',refresh=True)
        active=[s for s in account['payload'].get('subscriptions',[]) if s.get('is_active') and bookmaker in s.get('bookmakers',{})]
        if len(active)!=1:raise ValueError('unique active bookmaker subscription required')
        report['vendor_usage_before']=active[0]['request_count']
        budget.db.execute('UPDATE request_budget SET used=MAX(used,?) WHERE cycle_start=?',(active[0]['request_count'],budget.start))
        catalog=client.get('markets',{'language':'en'},refresh=True)
        nfl=[m for m in catalog['payload'] if m.get('sportId')==cfg['sport_id']]
        (args.out/'football_market_catalog.json').write_text(json.dumps(nfl,indent=2)+'\n')
        for i in range(args.polls):
            envelope=client.get('odds-by-tournaments',{'tournamentIds':','.join(map(str,cfg['tournament_ids'])),
                'bookmakers':bookmaker,'verbosity':3,'oddsFormat':'decimal'},refresh=True)
            row=audit.add(envelope)
            report['freshness']=audit.report()
            (args.out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps({'poll':i+1,'fixtures':row['fixtures'],'counts':row['counts'],
                'request_elapsed_seconds':row['request_elapsed_seconds'],'issues':row['issues']}),flush=True)
            if i<args.polls-1:time.sleep(args.interval)
        after=client.get('account',refresh=True)
        report['vendor_usage_after']=next(s['request_count'] for s in after['payload']['subscriptions'] if s.get('is_active') and bookmaker in s.get('bookmakers',{}))
        report['vendor_quota_consumed']=report['vendor_usage_after']-report['vendor_usage_before']
        report['local_budget_used']=budget.used()
        report['complete']=True
    except Exception as exc:
        report['error_type']=type(exc).__name__
        if isinstance(exc,ValueError):report['error']=str(exc)
    finally:
        if budget:budget.close()
        if handle:handle.close()
        if args.delete_key_file:
            args.key_file.unlink(missing_ok=True);report['temporary_key_file_deleted']=not args.key_file.exists()
        report['freshness']=audit.report()
        (args.out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({k:v for k,v in report.items() if k!='freshness'}),flush=True)
    return 0 if report['complete'] else 1


if __name__=='__main__':sys.exit(main())
