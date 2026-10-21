import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('mlb_native_cohort',ROOT/'scripts/mlb_native_cohort.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def market(*tickers):return {'mve_selected_legs':[{'market_ticker':t,'side':'yes'} for t in tickers]}

def test_doubleheader_times_are_distinct_fixtures():
 c=m.classify(market('KXMLBGAME-26JUL011305NYYBOS-NYY','KXMLBGAME-26JUL011905NYYBOS-BOS'))
 assert c['pure_mlb'] and c['distinct_fixtures'] and c['fullgame_core']
 assert c['scheduled_start_times'][1]-c['scheduled_start_times'][0]==6*3600
 assert c['earliest_scheduled_start']==m.stamp('2026-07-01T17:05:00Z')

def test_same_game_spread_total_not_claimed_independent():
 c=m.classify(market('KXMLBSPREAD-26SEP051805ATLPHI-PHI1','KXMLBTOTAL-26SEP051805ATLPHI-8'))
 assert c['fullgame_core'] and not c['distinct_fixtures']

def test_unknown_family_not_silently_nonplayer_or_core():
 c=m.classify(market('KXMLBUNKNOWN-26SEP051805ATLPHI-FOO','KXMLBGAME-26SEP051805ATLPHI-PHI'))
 assert c['unknown_family']==['KXMLBUNKNOWN'] and not c['fullgame_core']

def test_missing_schedule_fails_pregame_proxy():
 c=m.classify(market('KXMLBGAME-26SEP05ATLPHI-ATL','KXMLBGAME-26SEP05DETCLE-DET'))
 assert c['earliest_scheduled_start'] is None

def test_mixed_sport_not_in_pure_universe():
 c=m.classify(market('KXMLBGAME-26SEP051805ATLPHI-ATL','KXNFLGAME-26SEP051800CINDET-CIN'))
 assert not c['pure_mlb']
