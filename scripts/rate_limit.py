"""Shared read pacing across this study's Kalshi collectors."""
import fcntl,time
from pathlib import Path
PATH=Path(__file__).resolve().parents[1]/'data/kalshi_read_pacing.txt'

def pace():
    PATH.parent.mkdir(parents=True,exist_ok=True)
    with PATH.open('a+') as f:
        fcntl.flock(f,fcntl.LOCK_EX);f.seek(0)
        value=f.read().strip();now=time.time();slot=max(now,float(value) if value else now)
        f.seek(0);f.truncate();f.write(str(slot+.18));f.flush();fcntl.flock(f,fcntl.LOCK_UN)
    if slot>now:time.sleep(slot-now)
