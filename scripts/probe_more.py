import sys,json,os,gzip
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from probe_sources import save,BASE,ROOT

for offset in [100,200]:
    save('polymarket_cfb_slate_'+str(offset),'https://gamma-api.polymarket.com/events',{'limit':100,'offset':offset,'tag_id':100351,'end_date_min':'2026-09-05T00:00:00Z','end_date_max':'2026-09-07T00:00:00Z'})
p=json.load(open(ROOT/'data/raw/probes/polymarket_cfb_slate.json'))
event=next(r for r in p if r['slug'].endswith('2026-09-05') and r['markets'])
market=event['markets'][0]
token=json.loads(market['clobTokenIds'])[0]
save('polymarket_history_example','https://clob.polymarket.com/prices-history',{'market':token,'startTs':1788580800,'endTs':1788670800,'fidelity':1})
save('polymarket_market_example','https://clob.polymarket.com/markets/'+market['conditionId'])
sys.path.insert(0,'../kalshi_mm')
from src.kalshi_v2 import KalshiRequestSigner
signer=KalshiRequestSigner(os.environ['KALSHI_API_KEY_ID'],Path(os.environ['KALSHI_PRIVATE_KEY_PATH']).expanduser().read_text())
tick='KXMVECROSSCATEGORY-SHARD1-S2026B47875FA09D-273F2E75690'
p=save('yesterday_rfqs_example',BASE+'/communications/rfqs',{'market_ticker':tick,'limit':100},signer.headers('GET','/trade-api/v2/communications/rfqs'))
rows=p.get('rfqs',[])
print('yesterday rfqs',len(rows),[(r.get('created_ts'),r.get('status'),r.get('target_cost_dollars'),r.get('contracts_fp')) for r in rows[:5]])
print('creator fields',sorted({k for r in rows for k in r if 'creator' in k or 'user' in k}))
