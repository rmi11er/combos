import sys,gzip,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from mlb_streaming_longitudinal import evaluate_one,Compact
from mlb_longitudinal_sweep import evaluate,compact_curve,bounds
from test_mlb_longitudinal_sweep import plan,opportunity
from combos.backtest import BacktestConfig
import pytest

def gzrows(path):
 with gzip.open(path,'rt') as f:return [json.loads(l) for l in f]

def test_stream_parity_shared_timestamps_gaps_unknown_and_risk(tmp_path,monkeypatch):
 import mlb_longitudinal_sweep as old
 p=plan();p['primary_models']=['kalshi'];at=bounds('2026-07-01',p['timezone'])[0]+3600;gap=bounds('2026-07-02',p['timezone'])[0]+100
 rows=[opportunity('2026-07-01','a',settlement=gap,result=0),opportunity('2026-07-01','b',settlement=gap,result=1),opportunity('2026-07-03','c')]
 rows[1]['quantity']=1.01;rows[1]['maker_fee']=.0002;rows[1]['risk_multiplier']=.5
 rows[2]['quantity']=2.01;rows[2]['maker_fee']=.0004
 coverage={'observed_dates':list(p['dates']),'missing_dates':[]}
 for variant,label,overrides in old.VARIANTS:
  cfg=BacktestConfig(entry_basis='point',**p['baseline_limits'],**overrides)
  refdir=tmp_path/variant;refdir.mkdir();monkeypatch.setattr(old,'VARIANTS',((variant,label,overrides),))
  reference,curves=evaluate(rows,coverage,p,refdir)
  for constrained in (True,False):
   regime='funded' if constrained else 'unlimited';prefix=tmp_path/(variant+regime)
   record,path=evaluate_one(iter(rows),'kalshi',variant,label,cfg,constrained,coverage,p,prefix)
   expected=next(r for r in reference['records'] if r['regime']==regime)
   assert record==expected, {k:(record['selected'][k],expected['selected'][k]) for k in record['selected'] if record['selected'][k]!=expected['selected'][k]}
   refprefix=refdir/('kalshi__'+variant+'__'+regime)
   for suffix in ('.decisions.jsonl.gz','.fills.jsonl.gz','.curves.jsonl.gz'):
    assert gzrows(prefix.with_suffix(suffix))==gzrows(refprefix.with_suffix(suffix))
   assert path==curves['kalshi',variant,regime]

def test_compact_exact_extrema_ties_and_constant_memory():
 rows=[{'at':i,'trade_attributed_pnl':i%17,'accepted_point_edge':i%11,'committed_cash':10000 if i==499 else i%7} for i in range(5000)]
 c=Compact(len(rows),80)
 for i,r in enumerate(rows):c.add(i,r)
 assert c.output==compact_curve(rows,80)
 assert c.first is None and len(c.extrema)==0

def test_duplicate_failure_even_unlimited(tmp_path):
 p=plan();r=opportunity('2026-07-01','same');cov={'observed_dates':list(p['dates'])}
 with pytest.raises(ValueError,match='duplicate'):
  evaluate_one(iter([r,r]),'kalshi','v','v',BacktestConfig(entry_basis='point'),False,cov,p,tmp_path/'dupe')

@pytest.mark.parametrize('constrained',[True,False])
@pytest.mark.parametrize('case',['empty','all_guarded','settlement_tie','fractional_cap'])
def test_adversarial_exact_economics(tmp_path,monkeypatch,constrained,case):
 import mlb_longitudinal_sweep as old
 p=plan();p['primary_models']=['kalshi'];coverage={'observed_dates':list(p['dates']),'missing_dates':[]}
 day3=bounds('2026-07-03',p['timezone'])[0]+3600
 rows=[] if case=='empty' else [opportunity('2026-07-01','a',settlement=day3,result=1),opportunity('2026-07-03','b',settlement=day3+1,result=0)]
 if case=='all_guarded':
  for r in rows:r['quote_allowed']=False
 if case=='fractional_cap':
  rows[0].update(quantity=142.85,maker_fee=.01,yes_price=.3)
  rows[1].update(quantity=142.86,maker_fee=.01,yes_price=.3)
 variant='all';overrides={'entry_filter':'all_priced'};monkeypatch.setattr(old,'VARIANTS',((variant,variant,overrides),))
 refdir=tmp_path/'oracle';refdir.mkdir();reference,paths=evaluate(rows,coverage,p,refdir)
 cfg=BacktestConfig(entry_basis='point',**p['baseline_limits'],**overrides)
 regime='funded' if constrained else 'unlimited';prefix=tmp_path/'candidate'
 result,path=evaluate_one(iter(rows),'kalshi',variant,variant,cfg,constrained,coverage,p,prefix)
 if case=='empty':
  assert result['portfolio']['fills']==0 and result['portfolio']['ending_equity']==10000
  assert gzrows(prefix.with_suffix('.decisions.jsonl.gz'))==[]
  return
 assert result==next(r for r in reference['records'] if r['regime']==regime)
 for suffix in ('.decisions.jsonl.gz','.fills.jsonl.gz','.curves.jsonl.gz'):
  assert gzrows(prefix.with_suffix(suffix))==gzrows((refdir/('kalshi__all__'+regime)).with_suffix(suffix))
 assert path==paths['kalshi',variant,regime]

def test_out_of_order_and_unsupported_ticket_config_fail_closed(tmp_path):
 p=plan();rows=[opportunity('2026-07-03','z'),opportunity('2026-07-01','a')];cov={'observed_dates':list(p['dates'])}
 with pytest.raises(ValueError,match='chronological'):
  evaluate_one(iter(rows),'kalshi','v','v',BacktestConfig(entry_basis='point'),True,cov,p,tmp_path/'late')
 with pytest.raises(ValueError,match='no_ticket_cap'):
  evaluate_one(iter([]),'kalshi','v','v',BacktestConfig(maximum_yes_premium_dollars=50),True,cov,p,tmp_path/'cap')
