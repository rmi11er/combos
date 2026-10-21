from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from prepare_development_snapshot import select


def test_projection_excludes_heldout_and_preserves_gap():
    plan={'dates':{'2026-07-01':'development','2026-07-13':'development','2026-08-02':'validation'}}
    state={'days':{'2026-07-01':{'status':'complete'},'2026-07-13':{'status':'collected_unpriced_identity'},'2026-08-02':{'status':'complete'}},
           'stages':{'2026-07-01/replay':{},'2026-08-02/replay':{},'validation/abc':{}}}
    p,s,pending=select(plan,state)
    assert not pending
    assert set(p['dates'])==set(s['days'])=={'2026-07-01','2026-07-13'}
    assert set(s['stages'])=={'2026-07-01/replay'}
    assert s['days']['2026-07-13']['status']=='collected_unpriced_identity'


def test_running_or_absent_date_prevents_publication():
    p,s,pending=select({'dates':{'a':'development','b':'development'}},{'days':{'a':{'status':'running'}}})
    assert pending=={'a':'running','b':'missing'}
