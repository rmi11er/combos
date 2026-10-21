import gzip,json,sys,importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import mlb_exchange_acquire as acquire
import mlb_model_replay as replay
AL='KXMLBGAME-26JUL142000ALNL-AL'
ORDINARY='KXMLBGAME-26JUL141910PHICIN-PHI'
def leg(t):return {'market_ticker':t,'side':'yes'}
def writegz(p,x):
 with gzip.open(p,'wt') as f:json.dump(x,f)
def cohort(tmp_path,tickers):
 c=tmp_path/'cohort';c.mkdir();at=acquire.stamp('2026-07-11T12:00:00Z')
 row={'trade':{'ticker':'combo','trade_id':'id','created_time':'2026-07-11T12:00:00Z','taker_side':'yes','count_fp':'10','yes_price_dollars':'.2'},'classification':{'distinct_fixtures':True,'nlegs':2,'earliest_scheduled_start':at+86400,'series':['KXMLBGAME']},'source_window':[at-100,at+100],'sampling_method':'census','settlement_at':at+90000,'settlement_value':0,'maker_fee_dollars':.056,'fee_basis':'synthetic'}
 writegz(c/'combo_markets.json.gz',{'combo':{'mve_selected_legs':[leg(t) for t in tickers]}})
 writegz(c/'underlying_markets.json.gz',{t:{'strike_type':'structured'} for t in tickers})
 with gzip.open(c/'candidate_trades.jsonl.gz','wt') as f:f.write(json.dumps(row)+'\n')
 return c

def test_ordinary_parser_matches_preserved_source():
 path=Path('runs/morning_research_20260908/july11_identity_recovery/source_before/mlb_exchange_acquire.py')
 spec=importlib.util.spec_from_file_location('old_exchange',path);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
 for t in [ORDINARY,'KXMLBGAME-26JUL071415MILSTLG1-MIL','KXMLBSPREAD-26JUL071945MILSTLG2-STL1']:
  assert acquire.identity(t)==old.identity(t)
  assert acquire.unsupported_identity_legs([leg(t)])==[]

def test_narrow_exclusion_does_not_mask_other_unknown_identity():
 assert acquire.unsupported_identity_legs([leg(AL),leg(ORDINARY)])==[{'ticker':AL,'reason':'unsupported_exhibition_identity'}]
 for ticker in ['KXMLBGAME-26JUL142000FOOBAR-FOO','KXMLBGAME-26JUL142000ALNL-UNKNOWN']:
  with pytest.raises(ValueError):acquire.unsupported_identity_legs([leg(AL),leg(ticker)])

@pytest.mark.parametrize('ticker',[
 'KXMLBSPREAD-26JUL142000ALNL-AL2',
 'KXMLBSPREAD-26JUL142000ALNL-NL5',
 'KXMLBTOTAL-26JUL142000ALNL-10'])
def test_allstar_fixture_families_are_explicitly_unpriced(ticker):
 assert acquire.unsupported_identity_legs([leg(ticker),leg(ORDINARY)])==[
  {'ticker':ticker,'reason':'unsupported_exhibition_identity'}]

@pytest.mark.parametrize('ticker',[
 'KXMLBTOTAL-26JUL152000ALNL-10',
 'KXMLBSPREAD-26JUL142000ALNL-FOO2',
 'KXMLBTOTAL-26JUL142000ALNL-10garbage'])
def test_exhibition_policy_does_not_swallow_other_fixtures_or_malformed_lines(ticker):
 with pytest.raises(ValueError):acquire.unsupported_identity_legs([leg(ticker)])

def test_batch_distinguishes_unpriced_identity_from_supported_candidates(tmp_path):
 from mlb_historical_batch import identity_scope
 c=cohort(tmp_path,[AL,ORDINARY]);result=identity_scope(c)
 assert result['candidates']==1 and result['supported']==0
 assert result['excluded'][0]['trade_id']=='id' and not result['outcomes_used']
 writegz(c/'combo_markets.json.gz',{'combo':{'mve_selected_legs':[leg(ORDINARY),leg('KXMLBGAME-26JUL141910NYMTB-NYM')]}})
 result=identity_scope(c)
 assert result['candidates']==result['supported']==1 and result['excluded']==[]

def test_acquisition_keeps_supported_leg_and_logs_whole_combo(tmp_path,monkeypatch):
 c=cohort(tmp_path,[AL,ORDINARY]);out=tmp_path/'exchange'
 monkeypatch.setattr(sys,'argv',['acquire','--cohort',str(c),'--out',str(out),'--prepare-only','--write-reviewed-mapping'])
 monkeypatch.setattr(acquire,'get_cached',lambda cache,key,*a:[] if key=='pm_events' else {'market_settled_ts':'2026-01-01T00:00:00Z'})
 acquire.main();plan=json.loads((out/'acquisition_plan.json').read_text());coverage=json.loads((out/'identity_coverage.json').read_text())
 assert set(plan['windows'])=={ORDINARY} and coverage['candidate_prints']==coverage['unsupported_combo_prints']==1
 assert coverage['excluded_combos'][0]['trade_id']=='id'
 assert json.loads((out/'polymarket_mapping_reviewed.json').read_text())[AL]['status']=='unmatched'

def test_all_unsupported_never_becomes_silent_empty_day(tmp_path,monkeypatch):
 c=cohort(tmp_path,[AL,AL.replace('-AL','-NL')]);out=tmp_path/'exchange'
 monkeypatch.setattr(sys,'argv',['acquire','--cohort',str(c),'--out',str(out),'--prepare-only'])
 monkeypatch.setattr(acquire,'get_cached',lambda *a:pytest.fail('must not request providers'))
 with pytest.raises(ValueError,match='complete_census_unpriced_identity'):acquire.main()
 assert (out/'identity_coverage.json').is_file() and not (out/'acquisition.json').exists()

def test_replay_exclusion_precedes_fair_and_risk_and_preserves_denominator(tmp_path,monkeypatch):
 c=cohort(tmp_path,[AL,ORDINARY]);ex=tmp_path/'exchange';ex.mkdir();(ex/'polymarket_mapping_reviewed.json').write_text('{}');out=tmp_path/'replay'
 monkeypatch.setattr(replay,'SourceFairs',lambda *a:SimpleNamespace(fair=lambda *a:pytest.fail('unsupported combo must not price')))
 monkeypatch.setattr(replay,'risk_buckets',lambda *a:pytest.fail('unsupported combo must not build risk'))
 monkeypatch.setattr(sys,'argv',['replay','--cohort',str(c),'--exchange',str(ex),'--out',str(out)])
 replay.main();coverage=json.loads((out/'coverage.json').read_text());data=json.loads((out/'opportunities.json').read_text())
 assert data['candidate_prints']==coverage['eligible_prints']==1 and data['opportunities']==[]
 assert coverage['scope_exclusions']['unsupported_exhibition_identity']==1
 assert all(v['unsupported_exhibition_identity']==1 for v in coverage['pricing_exclusions'].values())
 with gzip.open(out/'pricing_context.jsonl.gz','rt') as f:ctx=json.loads(next(f))
 assert ctx['evaluation_id']=='id' and len(ctx['legs'])==2 and ctx['context']==[]
