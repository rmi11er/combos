"""Compare native-age and verified-state coverage at captured heartbeat times."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.event_store import EventStore
from combos.verified_book_state import VerifiedBookState


def run(capture,out):
    state=VerifiedBookState();store=EventStore(capture/'events.sqlite');seq=0;rows=[]
    try:
        while True:
            events=store.read(seq,500)
            if not events:break
            for event in events:
                seq=event['seq'];state.consume(event)
                if event['kind']=='heartbeat' and event['source']=='polymarket':
                    pairs=[state.pair(key,event['received_at']) for key in state.books]
                    baseline=sum(p['baseline'] is not None for p in pairs)
                    candidate=sum(p['candidate'] is not None for p in pairs)
                    if candidate<baseline:raise ValueError('candidate lost baseline coverage')
                    rows.append({'event_seq':seq,'at':event['received_at'],'baseline_keys':baseline,
                        'candidate_keys':candidate,'additional_keys':candidate-baseline})
    finally:store.close()
    out.mkdir(parents=True,exist_ok=False)
    summary={'checkpoints':len(rows), 'mean_baseline_keys':statistics.mean(r['baseline_keys'] for r in rows),
        'mean_candidate_keys':statistics.mean(r['candidate_keys'] for r in rows),
        'maximum_additional_keys':max(r['additional_keys'] for r in rows),
        'last_checkpoint':rows[-1], 'remaining_books_after_stop':len(state.books),
        'basis':'equal-weighted captured heartbeat checkpoints; single-venue coverage, not RFQ fill opportunity',
        'hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            (capture/'verification.json',capture/'runtime.json',Path(__file__),Path(__file__).resolve().parents[1]/'src/combos/verified_book_state.py')}}
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    (out/'checkpoints.json').write_text(json.dumps(rows,indent=2))
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
    a=p.parse_args();print(json.dumps(run(a.capture,a.out)))
