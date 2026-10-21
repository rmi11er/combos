#!/usr/bin/env python3
"""Compile captured definitions and odds into a reproducible non-player config."""
import argparse, copy, gzip, hashlib, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.nfl_nonplayer_matching import build_nonplayer_mappings
from combos.pinnacle_matching import bind_selectors
from combos.market_families import FAMILIES


def build(raw_dir, base, odds_path, catalog_path, season=2026, week=1):
    sources={}
    def read(path):
        data=path.read_bytes();sources[str(path)]={'sha256':hashlib.sha256(data).hexdigest()}
        record=json.loads(gzip.decompress(data) if path.suffix=='.gz' else data)
        if isinstance(record,dict) and 'payload' in record:
            if record.get('status',record.get('http_status'))!=200:raise ValueError('unsuccessful capture')
            sources[str(path)]['retrieved_at']=record['retrieved_at']
        return record
    series_capture=read(raw_dir/'kalshi_series.json')
    series={s['ticker']:s for s in series_capture['payload']['series']}
    markets=[]
    for sid in FAMILIES:
        if sid not in series:continue
        page=0
        while True:
            capture=read(raw_dir/f'{sid}_{page}.json');markets.extend(capture['payload']['markets'])
            if not capture['payload'].get('cursor'):break
            page+=1
    pm=read(raw_dir/f'pm_week{week}.json')
    if len(pm['payload'])>=100:raise ValueError('event pagination required')
    mappings,review=build_nonplayer_mappings(markets,pm['payload'],series,season,week)
    old={m['kalshi_ticker']:m for m in base['mappings']}
    for m in mappings:
        m.setdefault('period','full_game');m['player_prop']=False
        # New series stay fee-blocked until the regular metadata refresh checks
        # their scheduled changes. Never inherit expiry across series.
        prior=old.get(m['kalshi_ticker'])
        for venue in ('kalshi','polymarket'):
            fee=m['fees'][venue]
            if venue=='polymarket':fee.update(verified_at=pm['retrieved_at'],valid_until=pm['retrieved_at']+86400)
            elif prior and prior['fees'][venue]['rate']==fee['rate']:
                fee.update({k:v for k,v in prior['fees'][venue].items() if k in ('verified_at','valid_until')})
            else:fee.update(verified_at=series_capture['retrieved_at'],valid_until=0,validation='scheduled_fee_changes_not_yet_checked')
    review['pinnacle']=bind_selectors(mappings,read(odds_path)['payload'],read(catalog_path))
    config=copy.deepcopy(base);config['mappings']=mappings
    config['comment']='NFL 2–4-leg distinct-fixture pregame shadow; full-game/1H/1Q non-player moneyline, spread, total and team-total families. Exact payoff mappings and feed reviews gate pricing. No ticket cap or probability restriction.'
    review.update(sources=sources,total_mappings=len(mappings),scope=config['comment'])
    return config,review


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw-dir',type=Path,required=True);p.add_argument('--base-config',type=Path,required=True)
    p.add_argument('--odds',type=Path,required=True);p.add_argument('--catalog',type=Path,required=True)
    p.add_argument('--out-config',type=Path,required=True);p.add_argument('--out-review',type=Path,required=True)
    args=p.parse_args();config,review=build(args.raw_dir,json.loads(args.base_config.read_text()),args.odds,args.catalog)
    for path,obj in ((args.out_config,config),(args.out_review,review)):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,indent=2)+'\n')
    print(json.dumps({'mappings':review['total_mappings'],'by_family':review['mappings_by_family'],
                      'pinnacle_candidates':review['pinnacle']['candidate_mappings'],'pricing_ready':False},indent=2))
if __name__=='__main__':main()
