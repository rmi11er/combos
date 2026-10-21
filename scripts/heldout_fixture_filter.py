"""Streaming, model-independent fixture purge for a frozen validation cohort."""
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo
from build_development_fixture_exclusions import canonical_fixture


class HeldoutFixtureFilter:
    def __init__(self, manifest_path, expected_sha256, validation_dates, timezone='America/Chicago'):
        raw = Path(manifest_path).read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if actual != expected_sha256:
            raise ValueError('development exclusion manifest hash mismatch')
        manifest = json.loads(raw)
        fixtures = manifest['fixtures']
        if fixtures != sorted(set(fixtures)) or manifest['fixture_count'] != len(fixtures):
            raise ValueError('invalid exclusion fixture census')
        if any(canonical_fixture(f) != f for f in fixtures):
            raise ValueError('noncanonical exclusion fixture')
        self.excluded = frozenset(fixtures)
        self.dates = frozenset(validation_dates)
        if not self.dates or self.dates.intersection(manifest['observed_development_dates']):
            raise ValueError('validation dates overlap development or are empty')
        self.timezone = ZoneInfo(timezone)
        self.manifest_hash = actual
        self.counts = Counter()
        self.complete = False
        self.started = False

    def rows(self, source):
        if self.started:
            raise ValueError('use a fresh fixture filter for each model replay')
        self.started = True
        for row in source:
            date = datetime.fromtimestamp(row['at'], self.timezone).date().isoformat()
            if date not in self.dates:
                raise ValueError('row outside frozen validation dates')
            fixtures = row['buckets']['fixture']
            if not fixtures or any(canonical_fixture(f) != f for f in fixtures):
                raise ValueError('missing or noncanonical validation fixtures')
            self.counts[(date, 'input')] += 1
            if self.excluded.intersection(fixtures):
                self.counts[(date, 'excluded')] += 1
                continue
            self.counts[(date, 'retained')] += 1
            yield row
        self.complete = True

    def receipt(self):
        if not self.complete:
            raise ValueError('validation reader not fully consumed')
        dates = {date: {k: self.counts[(date, k)] for k in ('input', 'excluded', 'retained')}
                 for date in sorted(self.dates)}
        assert all(v['input'] == v['excluded']+v['retained'] for v in dates.values())
        return {'complete': True, 'exclusion_manifest_sha256': self.manifest_hash,
                'dates': dates, 'policy': 'fixture_purge_before_selection_and_risk',
                'coverage_note': 'Zero input is reported, not certified as a complete empty calendar date.'}
