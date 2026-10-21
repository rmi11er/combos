from datetime import datetime, timezone
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('nightly', Path(__file__).resolve().parents[1] / 'scripts/rfq_sniffer_nightly.py')
nightly = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nightly)


def test_central_window_tracks_daylight_saving():
    assert nightly.due(datetime(2026, 9, 8, 23, 0, tzinfo=timezone.utc))
    assert nightly.due(datetime(2026, 12, 9, 0, 0, tzinfo=timezone.utc))
    assert not nightly.due(datetime(2026, 12, 8, 23, 0, tzinfo=timezone.utc))
    assert not nightly.due(datetime(2026, 9, 8, 23, 5, tzinfo=timezone.utc))


def test_dispatcher_does_not_repeat_existing_day(tmp_path, monkeypatch):
    monkeypatch.setattr(nightly, 'STATE', tmp_path)
    monkeypatch.setattr(nightly, 'due', lambda now: True)
    (tmp_path / nightly.datetime.now(nightly.CENTRAL).date().isoformat()).mkdir()
    monkeypatch.setattr(nightly.subprocess, 'run', lambda *a, **kw: (_ for _ in ()).throw(AssertionError('Duplicate run')))
    assert nightly.main() == 0
