#!/usr/bin/env python3
"""Write the current NFL launch blockers without starting collectors or trading."""
import argparse
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from combos.readiness import readiness
from combos.weighted_fair import WeightPolicy


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',default=str(ROOT/'config/runtime_nfl_week1.json'))
    p.add_argument('--weights',default=str(ROOT/'config/weighting.json'))
    p.add_argument('--polling',default=str(ROOT/'config/oddspapi_polling.json'))
    p.add_argument('--at',type=float,default=None);p.add_argument('--out',type=Path)
    args=p.parse_args()
    report=readiness(json.loads(Path(args.config).read_text()),WeightPolicy(**json.loads(Path(args.weights).read_text())),
        json.loads(Path(args.polling).read_text()),args.at if args.at is not None else time.time())
    text=json.dumps(report,indent=2)+'\n'
    if args.out:args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(text)
    print(text,end='')
    return 0 if report['shadow_configuration_ready'] else 2


if __name__=='__main__':sys.exit(main())
