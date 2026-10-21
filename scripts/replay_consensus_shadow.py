"""Causal pricing-only replay of retained quotes and markout snapshots."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from combos.pricing_service import PricingService
from combos.weighted_fair import WeightPolicy


class State:
    def __init__(self): self.data = {}
    def get(self, owner, key, default=None): return self.data.get((owner, key), default)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    quotes = [json.loads(s) for s in (a.source/'quotes.jsonl').read_text().splitlines()]
    marks = [json.loads(s) for s in (a.source/'markouts.jsonl').read_text().splitlines()]
    bykey = {q['quote_key']: q for q in quotes}
    targets = defaultdict(list)
    for q in quotes: targets[q['run']].append((q['source_seq'], 'quote', q))
    for m in marks:
        if m['status'] == 'observed':
            targets[bykey[m['quote_key']]['run']].append((m['source_seq'], 'mark', m))
    audits = []; errors = []; policies = {}; rejected = set()
    for run, tasks in targets.items():
        tasks.sort(key=lambda t: t[0]); index = 0
        c = sqlite3.connect(f'file:{ROOT}/runs/{run}/events.sqlite?mode=ro', uri=True)
        manifest = json.loads(c.execute("SELECT value FROM state WHERE owner='runtime' AND key='manifest'").fetchone()[0])
        state = State(); old = PricingService(state, manifest['config'], WeightPolicy(**manifest['weights']))
        policy = dict(manifest['weights'])
        current = json.loads((ROOT/'config/weighting.json').read_text())
        policy.update({k:v for k,v in current.items() if k.startswith('consensus_')})
        policies[run] = policy
        new = PricingService(state, manifest['config'], WeightPolicy(**policy))

        def evaluate(task):
            seq, kind, item = task; q = bykey[item['quote_key']]
            at = q['decision_at'] if kind == 'quote' else item['observed_at']
            expected = q['pricing']['joint']['point'] if kind == 'quote' else item['fair']
            try:
                baseline = old.price(q['request']['mve_selected_legs'], at)
                delta = baseline['joint']['point']-expected
                if abs(delta) > 1e-9:
                    raise ValueError(f'baseline_point_mismatch:{delta}')
                pricing = new.price(q['request']['mve_selected_legs'], at)
                if kind == 'quote':
                    audits.append(dict(quote_key=q['quote_key'], old_point=expected,
                        new_point=pricing['joint']['point'], quote_allowed=pricing['quote_allowed'],
                        legs=[leg['consensus_lean'] for leg in pricing['legs']]))
                    q['pricing'] = pricing
                    if not pricing['quote_allowed']: rejected.add(q['quote_key'])
                else:
                    item['fair'] = pricing['joint']['point']
                    item['adverse_move_cents'] = 100*(item['fair']-q['pricing']['joint']['point'])
            except (ValueError, KeyError, TypeError) as exc:
                errors.append(dict(quote_key=q['quote_key'], seq=seq, kind=kind, error=str(exc)))
                if kind == 'quote': rejected.add(q['quote_key'])
                else: item['status'] = 'replay_unavailable'

        for seq, kind, at, raw in c.execute("SELECT seq,kind,received_at,payload FROM events WHERE kind IN ('observation','fixture_status','venue_reset') ORDER BY seq"):
            while index < len(tasks) and tasks[index][0] < seq:
                evaluate(tasks[index]); index += 1
            if index == len(tasks): break
            d = json.loads(zlib.decompress(raw))
            if kind == 'observation': state.data[('observations', d['market_key']+':'+d['venue'])] = d
            elif kind == 'fixture_status':
                previous = state.get(kind, d['fixture_key'], {})
                state.data[(kind, d['fixture_key'])] = dict(d, started=previous.get('started', False) or d['phase'] in ('in_play', 'finished'))
            else:
                for (owner, key), value in state.data.items():
                    if owner == 'observations' and value['venue'] == d['venue']:
                        value.update(active=False, available_at=at, observed_at=at)
        while index < len(tasks): evaluate(tasks[index]); index += 1
        c.close()
        print(f'{run}: replayed {len(tasks)} snapshots', flush=True)
    for name, rows in [('quotes', [q for q in quotes if q['quote_key'] not in rejected]),
                       ('markouts', [m for m in marks if m['quote_key'] not in rejected])]:
        with (a.out/(name+'.jsonl')).open('w') as f:
            for row in rows: f.write(json.dumps(row)+'\n')
    for name, obj in [('replay_audit', audits), ('replay_errors', errors), ('replay_weights', policies),
                      ('replay_coverage', dict(input_quotes=len(quotes), excluded_quotes=len(rejected),
                         baseline_verified_snapshots=len(audits)+sum(m['status']=='observed' for m in marks),
                         errors=len(errors)))]:
        (a.out/(name+'.json')).write_text(json.dumps(obj, indent=2)+'\n')
    (a.out/'summary.json').write_text((a.source/'summary.json').read_text())
    link = a.out/'public_tape'
    if not link.exists(): link.symlink_to((a.source/'public_tape').resolve(), target_is_directory=True)
    print(json.dumps(dict(errors=len(errors), excluded_quotes=len(rejected))))


if __name__ == '__main__': main()
