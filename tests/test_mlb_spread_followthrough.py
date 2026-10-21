import gzip
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import mlb_spread_followthrough as module


def test_extraction_preserves_all_moneyline_prints_without_edge_or_outcome_filter(tmp_path,monkeypatch):
    day=tmp_path/'day';(day/'replay').mkdir(parents=True)
    json.dump({'opportunities':[{'evaluation_id':'a','quote_allowed':False},{'evaluation_id':'b'}]},open(day/'replay/opportunities.json','w'))
    legs=[{'market_ticker':'KXMLBGAME-game1-A','side':'yes'}, {'market_ticker':'KXMLBGAME-game2-B','side':'no'}]
    ctx=[{'kalshi':{'fee_basis':{'taker_rate':.035}}}]*2
    with gzip.open(day/'replay/pricing_context.jsonl.gz','wt') as f:
        for key in ('a','b'):
            f.write(json.dumps({'evaluation_id':key,'at':100.,'legs':legs,'context':ctx})+'\n')
    class Provider:
        def __init__(self,*args): self.used=set()
        def pair(self,*args): return {'raw_width_cents':2.,'width':.04,'age_seconds':[60,60],'state_skew_seconds':0}
    monkeypatch.setattr(module,'PairHistory',Provider)
    result=module.extract(day,tmp_path/'out')
    assert result['paired_prints']==2
    assert result['counts']['eligible_moneyline_prints']==2
    assert result['complete']
    with gzip.open(tmp_path/'out/features.jsonl.gz','rt') as f:
        rows=[json.loads(x) for x in f]
    assert {r['evaluation_id'] for r in rows}=={'a','b'}
    assert all(r['synchronized_recent'] for r in rows)
