from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from research_storage_watch import checkpoint


def test_only_certified_replay_and_validation_trigger_maintenance():
    good={'status':'complete','exit_code':0,'output_sha256':{'file':'hash'}}
    state={'stages':{'2026-07-01/replay':good,'validation/abc':good,
                     '2026-07-02/replay':{**good,'status':'running'},
                     '2026-07-03/replay':{**good,'exit_code':1},
                     '2026-07-01/cohort':good}}
    assert checkpoint(state)=={'2026-07-01/replay':{'file':'hash'},'validation/abc':{'file':'hash'}}
