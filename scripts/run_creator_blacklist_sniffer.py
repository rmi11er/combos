"""Bounded polling supervisor for the separate creator review process."""
import argparse
import json
import time
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from creator_blacklist_sniffer import run


def main(a):
    if not 1<=a.interval<=3600 or not 1<=a.seconds<=86400:
        raise ValueError('bounded interval and duration required')
    started=time.monotonic();runs=[];a.out.parent.mkdir(parents=True,exist_ok=True)
    while time.monotonic()-started<a.seconds:
        asof=time.time();result=run(a.evidence_db,a.blacklist_db,asof)
        runs.append(result)
        a.out.write_text(json.dumps({'status':'running','started_at':time.time()-time.monotonic()+started,
            'runs':runs},indent=2)+'\n')
        remaining=a.seconds-(time.monotonic()-started)
        if remaining<=0:break
        time.sleep(min(a.interval,remaining))
    a.out.write_text(json.dumps({'status':'completed','runs':runs},indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--evidence-db',type=Path,required=True);p.add_argument('--blacklist-db',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--seconds',type=float,default=60);p.add_argument('--interval',type=float,default=30);main(p.parse_args())
