from probe_sources import save,ROOT,BASE
import json,gzip
p=json.load(open(ROOT/'data/raw/probes/polymarket_cfb_slate.json'))
m=next(e for e in p if e['slug']=='cfb-ohio-nebr-2026-09-05')['markets'][0]
t=json.loads(m['clobTokenIds'])[0]
for path in ['orderbook-history','ohlc']:
    data=save('pm_'+path,'https://clob.polymarket.com/'+path,{'asset_id':t,'startTs':1788620000,'endTs':1788623600,'limit':2,'fidelity':'1m'})
    print(str(data)[:1800])
save('pm_book_condition','https://clob.polymarket.com/orderbook-history',{'market':m['conditionId'],'startTs':1788584400,'endTs':1788670800,'limit':1000})
files=list((ROOT/'data/raw/legs').glob('*.json.gz'))
if files:
    with gzip.open(files[0],'rt') as f: m=json.load(f)['payload']['market']
    print('leg',json.dumps({k:v for k,v in m.items() if k in ['ticker','event_ticker','title','subtitle','yes_sub_title','no_sub_title','floor_strike','cap_strike','strike_type','rules_primary','expected_expiration_time','occurrence_time']}))
    ticker=m['ticker']
    with gzip.open(ROOT/'data/raw/candles'/f'{ticker}.json.gz','rt') as f: p=json.load(f)['payload']
    print('candles',str(p)[:2200])
