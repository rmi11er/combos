from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from mlb_collection_queue import complete_day


def test_queue_waits_for_contiguous_complete_day(tmp_path):
    day = '2026-07-01'; start = datetime.fromisoformat(day).replace(tzinfo=ZoneInfo('America/Chicago'))
    assert not complete_day(tmp_path, day)
    for hour in range(24):
        folder = tmp_path/day/str(hour); folder.mkdir(parents=True)
        row = {'start_at': (start+timedelta(hours=hour)).timestamp(),
               'end_at': (start+timedelta(hours=hour+1)).timestamp(), 'complete': True}
        (folder/'manifest.json').write_text(json.dumps(row))
    assert complete_day(tmp_path, day)
    p = tmp_path/day/'12'/'manifest.json'; row = json.loads(p.read_text())
    row['complete'] = False; p.write_text(json.dumps(row))
    assert not complete_day(tmp_path, day)
    row['complete'] = True; row['start_at'] += 1; p.write_text(json.dumps(row))
    assert not complete_day(tmp_path, day)
