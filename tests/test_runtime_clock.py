import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos import runtime_clock


def test_calendar_deadline_stops_after_sleep_even_if_monotonic_did_not_advance(monkeypatch):
    clocks={'wall':1000.,'mono':500.}
    monkeypatch.setattr(runtime_clock.time,'time',lambda:clocks['wall'])
    monkeypatch.setattr(runtime_clock.time,'monotonic',lambda:clocks['mono'])
    deadline=runtime_clock.Deadline(3600)
    clocks['wall']+=3601;clocks['mono']+=60
    assert deadline.expired()
    assert deadline.elapsed()=={'wall_seconds':3601,'monotonic_seconds':60}


def test_backward_calendar_jump_does_not_extend_monotonic_limit(monkeypatch):
    clocks={'wall':1000.,'mono':500.}
    monkeypatch.setattr(runtime_clock.time,'time',lambda:clocks['wall'])
    monkeypatch.setattr(runtime_clock.time,'monotonic',lambda:clocks['mono'])
    deadline=runtime_clock.Deadline(60)
    clocks.update(wall=900,mono=561)
    assert deadline.expired()


@pytest.mark.parametrize('seconds',[0,-1,float('inf'),float('nan')])
def test_invalid_duration_rejected(seconds):
    with pytest.raises(ValueError):runtime_clock.Deadline(seconds)
