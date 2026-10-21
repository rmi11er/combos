"""Independent integer audit of funded decisions with a fixed deployment cap."""
import argparse
from collections import defaultdict, Counter
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import heapq
import json
from pathlib import Path
from mlb_disk_index import file_digest
from replay_artifact_io import text_reader


def audit_decisions(rows, config):
    def units(v):
        return int((Decimal(str(v))*10000).to_integral_value(rounding=ROUND_CEILING))
    ceiling = int((Decimal(str(config['maximum_committed_dollars']))*10000).to_integral_value(rounding=ROUND_FLOOR))
    capital = units(config['capital_dollars'])
    committed = pnl = peak = fills = count = 0
    pending, used, rejected = [], defaultdict(int), Counter()
    previous = None
    for row in rows:
        count += 1
        key = (row['at'], row['evaluation_id'])
        assert previous is None or previous < key, 'duplicate_or_nonchronological'
        previous = key
        while pending and pending[0][0] <= row['at']:
            _, _, cost, payout, buckets = heapq.heappop(pending)
            committed -= cost
            pnl += payout-cost
            for bucket in buckets:
                used[bucket] -= cost
        if 'risk' not in row:
            assert not row['accepted']
            continue
        cost = units(row['quantity']*(1-row['yes_price'])+row['maker_fee'])
        buckets = [(kind, k) for kind, keys in row['buckets'].items() for k in set(keys)]
        assert set(row['buckets']) == {'contract', 'fixture', 'combo'}
        binding = []
        if cost > capital+pnl-committed:
            binding.append('settled_cash')
        if cost+committed > ceiling:
            binding.append('deployment_ceiling')
        for kind, k in buckets:
            cap = int(Decimal(str(config['per_'+kind+'_dollars']))*Decimal(str(row['risk_multiplier']))*10000)
            if used[kind, k]+cost > cap:
                binding.append(kind)
        assert row['accepted'] == (not binding), ('admission_mismatch', row['evaluation_id'], binding)
        if binding:
            rejected.update(set(binding))
            continue
        committed += cost
        peak = max(peak, committed)
        fills += 1
        for bucket in buckets:
            used[bucket] += cost
        assert committed <= ceiling and committed <= capital+pnl
        if row['settled_at'] is not None:
            heapq.heappush(pending, (row['settled_at']+config['settlement_delay_seconds'], row['evaluation_id'],
                                    cost, units(row['quantity']*(1-row['yes_settlement'])), buckets))
    return {'passed': True, 'decisions': count, 'fills': fills, 'peak_integer_cash': peak/10000,
            'binding_limits_nonexclusive': dict(rejected)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--study', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    complete = json.loads((a.study/'complete.json').read_text())
    assert file_digest(a.study/'summary.json') == complete['summary_sha256']
    summary = json.loads((a.study/'summary.json').read_text())
    records = []
    for r in summary['records']:
        path = a.study/(r['model']+'__'+r['variant']+'.decisions.jsonl.zst')
        before = file_digest(path)
        with text_reader(path) as handle:
            result = audit_decisions((json.loads(line) for line in handle), r['configuration'])
        assert result['decisions'] == r['portfolio']['evaluations']
        assert result['fills'] == r['portfolio']['fills']
        assert file_digest(path) == before
        records.append({'model': r['model'], 'variant': r['variant'], 'audit': result, 'decisions_sha256': before})
        print('verified', r['model'], r['variant'], flush=True)
    a.out.write_text(json.dumps({'passed': True, 'records': records, 'summary_sha256': complete['summary_sha256'],
                                'audit_source_sha256': file_digest(Path(__file__))}, indent=2)+'\n')


if __name__ == '__main__':
    main()
