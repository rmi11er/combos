"""Deterministic traded-market sample for creator context, not a full RFQ tape."""
import concurrent.futures as cf
import gzip,hashlib,heapq,json
from pathlib import Path
from fetch_inputs import fetch_rfq,ROOT

if __name__=='__main__':
    pools={'long_legs':[],'other_two_leg':[]};seen=set()
    for file in (ROOT/'data/raw/metadata').glob('*.json.gz'):
        with gzip.open(file,'rt') as f:payload=json.load(f)['payload']
        for m in payload['markets']:
            tick=m['ticker']
            if tick in seen:continue
            seen.add(tick);legs=m.get('mve_selected_legs',[])
            group='long_legs' if len(legs)>=20 else 'other_two_leg' if len(legs)==2 else None
            if group:
                h=int(hashlib.sha256(tick.encode()).hexdigest(),16)
                heapq.heappush(pools[group],(-h,tick))
                if len(pools[group])>250:heapq.heappop(pools[group])
    ticks=sorted({t for pool in pools.values() for _,t in pool})
    (ROOT/'data/derived/creator_sample_manifest.json').write_text(json.dumps({'sampled_market_count':len(ticks),'sampling':'250 smallest SHA-256 per structural stratum among metadata recovered at sampling time','metadata_market_count':len(seen),'tickers':ticks},indent=2))
    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        for i,_ in enumerate(pool.map(fetch_rfq,ticks)):
            if i%100==0:print('creator context',i,'/',len(ticks),flush=True)
