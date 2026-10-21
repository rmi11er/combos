import copy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import july15_mapping_overlay as module
import pytest

def fake(monkeypatch):
 native={t:{'ticker':t,'rules_primary':'Jul 16, 2026 at 7:10 PM EDT'} for t in module.ALLOWED}
 baseline={t:{'status':'unmatched'} for t in module.ALLOWED};baseline['KXMLBGAME-26JUL171335TBBOSG1-TB']={'status':'unmatched'}
 event={'id':module.EVENT_ID,'slug':module.SLUG,'gameId':module.GAME_ID,'startTime':'2026-07-16T22:10:00Z','description':'July 16 at 7:10PM ET','markets':[{'id':'2870228','sportsMarketType':'moneyline','gameStartTime':'2026-07-16 22:10:00+00'}]}
 monkeypatch.setattr(module,'pm_match',lambda n,e:{'status':'matched','token':n['ticker']})
 return event,native,baseline

def test_only_allowlisted_game_changed_original_revised_clocks_separate(monkeypatch):
 e,n,b=fake(monkeypatch);out=module.reviewed_candidates([e],n,b)
 assert b['KXMLBGAME-26JUL171335TBBOSG1-TB']==out['KXMLBGAME-26JUL171335TBBOSG1-TB']
 assert all(b[t]['status']=='unmatched' for t in module.ALLOWED)
 m=out[next(iter(module.ALLOWED))];assert m['original_scheduled_start_at']-m['revised_scheduled_start_at']==3600
 assert m['schedule_change_available_at'] is None

def test_wrong_game_or_duplicate_or_child_clock_rejected(monkeypatch):
 e,n,b=fake(monkeypatch)
 with pytest.raises(ValueError,match='unique'):module.reviewed_candidates([e,e],n,b)
 changed=copy.deepcopy(e);changed['gameId']+=1
 with pytest.raises(ValueError,match='evidence'):module.reviewed_candidates([changed],n,b)
 changed=copy.deepcopy(e);changed['markets'][0]['gameStartTime']='2026-07-16 23:10:00+00'
 with pytest.raises(ValueError,match='clock'):module.reviewed_candidates([changed],n,b)

def test_no_original_schedule_or_payoff_bypass(monkeypatch):
 e,n,b=fake(monkeypatch);t=next(iter(module.ALLOWED));n[t]['rules_primary']='another game'
 with pytest.raises(ValueError,match='native'):module.reviewed_candidates([e],n,b)
 e,n,b=fake(monkeypatch);monkeypatch.setattr(module,'pm_match',lambda n,e:{'status':'unmatched'})
 with pytest.raises(ValueError,match='payoff'):module.reviewed_candidates([e],n,b)

def test_earlier_cutoff_never_uses_original_ticker_clock():
 legs=[{'market_ticker':next(iter(module.ALLOWED))}]
 module.enforce_cutoff(module.REVISED-60-.001,legs)
 with pytest.raises(ValueError,match='cutoff'):module.enforce_cutoff(module.REVISED-60,legs)
 with pytest.raises(ValueError,match='cutoff'):module.enforce_cutoff(module.ORIGINAL-100,legs)
