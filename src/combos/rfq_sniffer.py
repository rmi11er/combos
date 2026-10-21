"""Offline behavioral blacklist; no pricing, inferred fills, or trading adapter."""
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
import csv
import fcntl
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import time
import zlib

from .journal import read_journal


@dataclass(frozen=True)
class Policy:
    schema_version: int = 2
    window_seconds: int = 60
    watch_rate_requests: int = 120
    rate_requests: int = 600
    repeated_requests: int = 30
    near_minimum_legs: int = 6
    near_maximum_edits: int = 2
    near_edit_fraction: float = .05
    near_edit_cap: int = 5
    near_overlap: float = .8
    huge_legs: int = 12
    concentrated_leg_fraction: float = .6
    minimum_legs_per_fixture: int = 3
    huge_repeated_requests: int = 10
    bursts_to_blacklist: int = 3
    burst_evidence_seconds: int = 86400
    blacklist_seconds: int = 7*86400
    provisional_blacklist_seconds: int = 86400
    recurrence_minimum_seconds: int = 1800
    trade_horizon_seconds: int = 60
    extended_trade_horizon_seconds: int = 300
    maximum_templates_per_creator: int = 64

    def __post_init__(self):
        for key, value in asdict(self).items():
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ValueError('positive finite policy fields required: '+key)
            if key not in ('near_edit_fraction', 'near_overlap', 'concentrated_leg_fraction') and type(value) is not int:
                raise ValueError('integer policy field required: '+key)
        if any(getattr(self, k) > 1 for k in ('near_edit_fraction','near_overlap','concentrated_leg_fraction')):
            raise ValueError('fractions must not exceed one')
        if self.schema_version != 2 or self.rate_requests <= self.watch_rate_requests:
            raise ValueError('schema v2 and a block-rate threshold above the watch rate are required')
        if self.near_edit_cap < self.near_maximum_edits or self.extended_trade_horizon_seconds <= self.trade_horizon_seconds:
            raise ValueError('invalid edit cap or extended trade horizon')


def packed(value):
    return zlib.compress(json.dumps(value, sort_keys=True, separators=(',', ':')).encode(), 1)


def structure(legs, mappings=None, policy=None):
    p = policy or Policy()
    mappings = mappings or {}
    exact, fixtures, heuristic = Counter(), Counter(), Counter()
    keys = []
    valid = bool(legs)
    for leg in legs:
        if not isinstance(leg, dict) or not isinstance(leg.get('market_ticker'), str) or leg.get('side') not in ('yes','no'):
            valid = False
            continue
        ticker = leg['market_ticker']
        keys.append((ticker, leg['side'], str(leg.get('yes_settlement_value_dollars', ''))))
        event = leg.get('event_ticker')
        if isinstance(event, str) and event:
            exact[event] += 1
        if ticker in mappings:
            fixtures[mappings[ticker]] += 1
        # Explicitly a sporting-event naming heuristic, never a calibrated correlation.
        elif isinstance(event, str) and '-' in event:
            family, suffix = event.split('-', 1)
            sport = re.match(r'^KX(NFL|MLB|NCAAF|NBA|WNBA|NHL)', family)
            if sport and re.match(r'^\d{2}[A-Z]{3}\d{2}', suffix):
                heuristic[sport[1]+':'+suffix] += 1
    n = len(legs)
    grouped = sum(v for v in fixtures.values() if v >= p.minimum_legs_per_fixture)
    suspected = sum(v for v in heuristic.values() if v >= p.minimum_legs_per_fixture)
    exact_grouped = sum(v for v in exact.values() if v >= p.minimum_legs_per_fixture)
    # These overlapping measures must not be added together.
    concentration = max(grouped+suspected, exact_grouped)/n if n else 0
    return frozenset(keys), {
        'leg_count': n, 'valid_legs': valid, 'unique_legs': len(set(keys)),
        'duplicate_legs': len(keys)-len(set(keys)),
        'maximum_legs_same_event': max(exact.values(), default=0),
        'maximum_legs_reviewed_fixture': max(fixtures.values(), default=0),
        'maximum_legs_inferred_fixture': max(heuristic.values(), default=0),
        'concentrated_fraction': concentration,
        'huge_concentrated': bool(valid and n >= p.huge_legs and concentration >= p.concentrated_leg_fraction),
        'correlation_basis': 'structural_overlap_only_not_estimated_joint_probability',
    }


def similar(a, b, policy):
    if a == b:
        return True
    if min(len(a), len(b)) < policy.near_minimum_legs:
        return False
    shared = len(a & b)
    allowed = min(policy.near_edit_cap,max(policy.near_maximum_edits,
                  math.ceil(min(len(a),len(b))*policy.near_edit_fraction)))
    return (max(len(a)-shared, len(b)-shared) <= allowed
            and shared/max(len(a),len(b)) >= policy.near_overlap)


class Sniffer:
    def __init__(self, path, policy=None, mappings=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = open(str(self.path)+'.lock', 'a')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.close()
            raise ValueError('sniffer database already in use') from None
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        if self.db.execute("SELECT 1 FROM sqlite_master WHERE name='metadata'").fetchone():
            previous = self.db.execute("SELECT value FROM metadata WHERE key='policy'").fetchone()
            if previous and json.loads(previous[0]).get('schema_version') != 2:
                self.close()
                raise ValueError('legacy sniffer database: replay saved journals into a new v2 database')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT);
            CREATE TABLE IF NOT EXISTS journals(identity TEXT PRIMARY KEY,path TEXT,rows INTEGER);
            CREATE TABLE IF NOT EXISTS requests(
                id TEXT PRIMARY KEY,creator TEXT,at REAL,ticker TEXT,legs BLOB,features TEXT,
                raw_ref TEXT,trade_context TEXT DEFAULT 'pending',extended_trade_context TEXT DEFAULT 'pending');
            CREATE INDEX IF NOT EXISTS requests_creator_time ON requests(creator,at);
            CREATE INDEX IF NOT EXISTS requests_time ON requests(at);
            CREATE TABLE IF NOT EXISTS trades(id TEXT PRIMARY KEY,ticker TEXT,at REAL,exchange_at REAL);
            CREATE INDEX IF NOT EXISTS trades_market_time ON trades(ticker,at);
            CREATE TABLE IF NOT EXISTS coverage(id TEXT PRIMARY KEY,start REAL,end REAL);
            CREATE TABLE IF NOT EXISTS bursts(
                id INTEGER PRIMARY KEY,creator TEXT,at REAL,reasons TEXT,evidence TEXT,
                block_eligible INTEGER NOT NULL,period_id TEXT NOT NULL,
                UNIQUE(creator,at));
            CREATE INDEX IF NOT EXISTS bursts_creator_time ON bursts(creator,at);
            CREATE TABLE IF NOT EXISTS blacklist(
                creator TEXT PRIMARY KEY,first_at REAL,last_at REAL,expires_at REAL,reasons TEXT,evidence_ids TEXT,
                confidence TEXT,qualifying_periods TEXT);
            CREATE TABLE IF NOT EXISTS diagnostics(kind TEXT,at REAL,reference TEXT);
        ''')
        old = self.db.execute("SELECT value FROM metadata WHERE key='policy'").fetchone()
        self.policy = policy or (Policy(**json.loads(old[0])) if old else Policy())
        config = json.dumps(asdict(self.policy), sort_keys=True)
        if old and old[0] != config:
            self.close()
            raise ValueError('policy changed; use a separate evidence database')
        self.db.execute("INSERT OR IGNORE INTO metadata VALUES('policy',?)", (config,))
        old_maps = self.db.execute("SELECT value FROM metadata WHERE key='mappings'").fetchone()
        self.mappings = mappings if mappings is not None else json.loads(old_maps[0]) if old_maps else {}
        mapping_json = json.dumps(self.mappings, sort_keys=True)
        if old_maps and old_maps[0] != mapping_json:
            self.close()
            raise ValueError('mappings changed; use a separate evidence database')
        self.db.execute("INSERT OR IGNORE INTO metadata VALUES('mappings',?)", (mapping_json,))
        self.version = hashlib.sha256((config+mapping_json).encode()).hexdigest()
        self.windows = defaultdict(deque)
        self.templates = defaultdict(list)
        self.last_at = float(self.get('last_at', '-1e30'))
        self.last_burst = {(r['creator'],r['block_eligible']):r['at'] for r in
            self.db.execute('SELECT creator,block_eligible,MAX(at) at FROM bursts GROUP BY creator,block_eligible')}
        # Restore only the active lookback. A request is still counted once across scans/restarts.
        for row in self.db.execute('SELECT * FROM requests WHERE at>? ORDER BY at,id', (self.last_at-self.policy.window_seconds,)):
            if row['creator']:
                self.remember(row['creator'],row['id'],row['at'],frozenset(tuple(x) for x in json.loads(zlib.decompress(row['legs']))),json.loads(row['features']))
        self.db.commit()

    def get(self, key, default=None):
        row = self.db.execute('SELECT value FROM metadata WHERE key=?',(key,)).fetchone()
        return row[0] if row else default

    def close(self):
        self.db.close()
        self.lock.close()

    def remember(self, creator, rid, at, keys, features):
        p = self.policy
        window = self.windows[creator]
        while window and window[0]['at'] <= at-p.window_seconds:
            window.popleft()
        templates = [t for t in self.templates[creator] if t['last'] > at-p.window_seconds]
        template = None
        if features['valid_legs']:
            template = next((t for t in templates if similar(keys,t['keys'],p)), None)
            if template is None:
                template = {'keys':keys,'id':hashlib.sha256(packed(sorted(keys))).hexdigest(),'last':at}
                templates.append(template)
            template['last'] = at
        self.templates[creator] = sorted(templates,key=lambda t:t['last'])[-p.maximum_templates_per_creator:]
        item = {'id':rid,'at':at,'template':template['id'] if template else None,
                'exact':hashlib.sha256(packed(sorted(keys))).hexdigest() if features['valid_legs'] else None,
                'features':features}
        window.append(item)
        return window, item

    def request(self, msg, at, reference, period_id='manual'):
        rid, creator = msg.get('id'), msg.get('creator_id')
        if not isinstance(rid,str) or not rid:
            self.db.execute('INSERT INTO diagnostics VALUES(?,?,?)',('missing_rfq_id',at,reference))
            return
        if not isinstance(creator,str) or not creator:
            creator = None
        legs = msg.get('mve_selected_legs') or []
        if not isinstance(legs,list):
            legs = []
        keys, features = structure(legs,self.mappings,self.policy)
        added = self.db.execute('INSERT OR IGNORE INTO requests(id,creator,at,ticker,legs,features,raw_ref) VALUES(?,?,?,?,?,?,?)',
            (rid,creator,at,msg.get('market_ticker'),packed(sorted(keys)),json.dumps(features),reference)).rowcount
        if not added:
            return
        if at < self.last_at:
            self.db.execute('INSERT INTO diagnostics VALUES(?,?,?)',('late_request_excluded_from_bursts',at,reference))
            return
        self.last_at = at
        self.db.execute("INSERT OR REPLACE INTO metadata VALUES('last_at',?)",(str(at),))
        if not creator:
            return
        window, current = self.remember(creator,rid,at,keys,features)
        p = self.policy
        if all(at-self.last_burst.get((creator,level),-1e30) < p.window_seconds for level in (0,1)):
            return
        total = len(window)
        exact = [w for w in window if current['exact'] and w['exact']==current['exact']]
        near = [w for w in window if current['template'] and w['template']==current['template']]
        huge = [w for w in near if w['features']['huge_concentrated']]
        reasons = []
        if total >= p.rate_requests:
            reasons.append('high_request_rate')
        if len(exact) >= p.repeated_requests:
            reasons.append('identical_parlay_spam')
        if len(near) >= p.repeated_requests and len(near)>len(exact):
            reasons.append('minor_edit_parlay_spam')
        if len(huge) >= p.huge_repeated_requests:
            reasons.append('large_concentrated_parlay_spam')
        eligible = bool(reasons)
        if eligible and at-self.last_burst.get((creator,1),-1e30) < p.window_seconds:
            reasons = []
            eligible = False
        if not eligible and total >= p.watch_rate_requests and at-self.last_burst.get((creator,0),-1e30) >= p.window_seconds:
            reasons = ['high_request_rate_watch']
        if not reasons:
            return
        evidence = {'trigger_rfq_id':rid,'raw_ref':reference,'window_start_exclusive':at-p.window_seconds,
                    'window_end_inclusive':at,'requests':total,'identical':len(exact),'similar':len(near),
                    'large_concentrated_similar':len(huge),'trigger_structure':features,
                    'template_anchor_legs': next((sorted(t['keys']) for t in self.templates[creator] if t['id']==current['template']),None),
                    'sample_rfq_ids':[w['id'] for w in (near or list(window))[-10:]],'policy_version':self.version,
                    'block_eligible':eligible,'period_id':period_id}
        self.db.execute('INSERT INTO bursts(creator,at,reasons,evidence,block_eligible,period_id) VALUES(?,?,?,?,?,?)',
                        (creator,at,json.dumps(reasons),json.dumps(evidence),int(eligible),period_id))
        self.last_burst[(creator,int(eligible))] = at
        if not eligible:
            return
        recent = self.db.execute('SELECT id,at,reasons,period_id FROM bursts WHERE creator=? AND block_eligible=1 AND at>? ORDER BY at',
                                 (creator,at-p.burst_evidence_seconds)).fetchall()
        if len(recent) >= p.bursts_to_blacklist:
            reasons = sorted({reason for r in recent for reason in json.loads(r['reasons'])})
            periods = defaultdict(list)
            for r in recent: periods[r['period_id']].append(r['at'])
            qualified = {k:v[p.bursts_to_blacklist-1] for k,v in periods.items() if len(v)>=p.bursts_to_blacklist}
            recurrent = period_id in qualified and any(k!=period_id and at-t>=p.recurrence_minimum_seconds for k,t in qualified.items())
            previous = self.db.execute('SELECT confidence,expires_at,qualifying_periods FROM blacklist WHERE creator=?',(creator,)).fetchone()
            if previous and previous['confidence']=='recurrent' and previous['expires_at']>at:
                recurrent = True
                qualified = {**json.loads(previous['qualifying_periods']),**qualified}
            confidence = 'recurrent' if recurrent else 'provisional'
            ttl = p.blacklist_seconds if recurrent else p.provisional_blacklist_seconds
            self.db.execute('''INSERT INTO blacklist VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(creator) DO UPDATE SET
                last_at=excluded.last_at,expires_at=excluded.expires_at,reasons=excluded.reasons,evidence_ids=excluded.evidence_ids,
                confidence=excluded.confidence,qualifying_periods=excluded.qualifying_periods''',
                (creator,at,at,at+ttl,json.dumps(reasons),json.dumps([r['id'] for r in recent]),confidence,json.dumps(qualified)))

    def label_trade_context(self):
        # A trade anywhere on the same ticker is context, not a creator/RFQ fill link.
        for column,h in (('trade_context',self.policy.trade_horizon_seconds),
                         ('extended_trade_context',self.policy.extended_trade_horizon_seconds)):
            self.db.execute(f'''UPDATE requests SET {column}=CASE
            WHEN EXISTS(SELECT 1 FROM trades t WHERE t.ticker=requests.ticker
                AND t.at>=requests.at AND t.at<=requests.at+?
                AND t.exchange_at>=requests.at AND t.exchange_at<=requests.at+?)
                THEN 'later_public_trade_same_market'
            WHEN EXISTS(SELECT 1 FROM coverage c WHERE c.start<=requests.at AND c.end>=requests.at+?)
                THEN 'no_public_trade_observed_in_covered_window'
            ELSE 'censored_or_trade_coverage_unknown' END''',(h,h,h))

    def prune_memory(self):
        cutoff = self.last_at-self.policy.window_seconds
        for creator in list(self.windows):
            if not self.windows[creator] or self.windows[creator][-1]['at'] <= cutoff:
                del self.windows[creator]
                self.templates.pop(creator,None)

    def export(self, directory, now=None):
        out = Path(directory)
        out.mkdir(parents=True, exist_ok=True)
        now = time.time() if now is None else now
        self.label_trade_context()
        self.db.commit()
        entries = []
        for row in self.db.execute('SELECT * FROM blacklist ORDER BY creator'):
            entry = dict(row)
            entry['creator_id'] = entry.pop('creator')
            entry['reason_codes'] = json.loads(entry.pop('reasons'))
            entry['evidence_ids'] = json.loads(entry['evidence_ids'])
            entry['qualifying_periods'] = json.loads(entry['qualifying_periods'])
            entry['active'] = row['expires_at'] > now
            entry['status'] = 'blocked' if entry['active'] else 'expired'
            entry['trade_context'] = dict(self.db.execute('SELECT trade_context,COUNT(*) FROM requests WHERE creator=? GROUP BY trade_context',(row['creator'],)).fetchall())
            entry['extended_trade_context'] = dict(self.db.execute('SELECT extended_trade_context,COUNT(*) FROM requests WHERE creator=? GROUP BY extended_trade_context',(row['creator'],)).fetchall())
            entries.append(entry)
        active = [e for e in entries if e['active']]
        summary = {'generated_at':now,'policy':asdict(self.policy),'policy_version':self.version,
                   'unique_requests':self.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],
                   'unique_creators':self.db.execute('SELECT COUNT(DISTINCT creator) FROM requests').fetchone()[0],
                   'missing_creator_requests':self.db.execute('SELECT COUNT(*) FROM requests WHERE creator IS NULL').fetchone()[0],
                   'observed_bursts':self.db.execute('SELECT COUNT(*) FROM bursts').fetchone()[0],
                   'active_blacklist_ids':len(active),
                   'active_confidence_counts':dict(Counter(e['confidence'] for e in active)),
                   'block_eligible_bursts':self.db.execute('SELECT COUNT(*) FROM bursts WHERE block_eligible=1').fetchone()[0],
                   'trade_context':dict(self.db.execute('SELECT trade_context,COUNT(*) FROM requests GROUP BY trade_context').fetchall()),
                   'extended_trade_context':dict(self.db.execute('SELECT extended_trade_context,COUNT(*) FROM requests GROUP BY extended_trade_context').fetchall()),
                   'diagnostics':dict(self.db.execute('SELECT kind,COUNT(*) FROM diagnostics GROUP BY kind').fetchall()),
                   'last_rfq_received_at':self.last_at,
                   'basis':'Request behavior only. No public trade is not proof of no fill. No live trading integration.'}
        atomic_json(out/'blacklist.json',{'schema_version':2,'generated_at':now,'policy_version':self.version,
                                        'creator_ids':[e['creator_id'] for e in active],'entries':entries})
        atomic_json(out/'summary.json',summary)
        with (out/'evidence.jsonl.tmp').open('w') as f:
            for row in self.db.execute('SELECT * FROM bursts ORDER BY at,id'):
                f.write(json.dumps(dict(row,reasons=json.loads(row['reasons']),evidence=json.loads(row['evidence'])))+'\n')
        (out/'evidence.jsonl.tmp').replace(out/'evidence.jsonl')
        with (out/'watchlist.jsonl.tmp').open('w') as f:
            for row in self.db.execute('''SELECT b.creator,COUNT(*) bursts,MAX(b.at) last_at
                FROM bursts b GROUP BY b.creator ORDER BY bursts DESC,b.creator'''):
                f.write(json.dumps(dict(row))+'\n')
        (out/'watchlist.jsonl.tmp').replace(out/'watchlist.jsonl')
        flagged = {r['creator']:dict(r) for r in self.db.execute('SELECT creator,COUNT(*) bursts,SUM(block_eligible) block_eligible_bursts FROM bursts GROUP BY creator')}
        reasons = defaultdict(set)
        for row in self.db.execute('SELECT creator,reasons FROM bursts'):
            reasons[row['creator']].update(json.loads(row['reasons']))
        active_ids = {e['creator_id'] for e in active}
        confidence = {e['creator_id']:e['confidence'] for e in active}
        review = []
        for row in self.db.execute('''SELECT creator,COUNT(*) requests,MAX(json_extract(features,'$.leg_count')) max_legs,
            SUM(json_extract(features,'$.huge_concentrated')) large_concentrated_requests,
            SUM(trade_context='no_public_trade_observed_in_covered_window') no_later_public_trade,
            SUM(trade_context='later_public_trade_same_market') later_public_trade,
            SUM(trade_context='censored_or_trade_coverage_unknown') unknown_trade_context,
            SUM(extended_trade_context='no_public_trade_observed_in_covered_window') no_later_public_trade_extended,
            SUM(extended_trade_context='later_public_trade_same_market') later_public_trade_extended,
            SUM(extended_trade_context='censored_or_trade_coverage_unknown') unknown_trade_context_extended
            FROM requests WHERE creator IS NOT NULL GROUP BY creator'''):
            if row['creator'] in flagged:
                review.append(dict(row,bursts=flagged[row['creator']]['bursts'],
                    block_eligible_bursts=flagged[row['creator']]['block_eligible_bursts'],confidence=confidence.get(row['creator'],'watch'),
                    status='blocked' if row['creator'] in active_ids else 'watch',
                    reasons=';'.join(sorted(reasons[row['creator']]))))
        review.sort(key=lambda r:(r['status']=='blocked',r['bursts'],r['requests']),reverse=True)
        fields = ['creator','status','confidence','bursts','block_eligible_bursts','requests','max_legs','large_concentrated_requests',
                  'no_later_public_trade','later_public_trade','unknown_trade_context',
                  'no_later_public_trade_extended','later_public_trade_extended','unknown_trade_context_extended','reasons']
        with (out/'creators.csv.tmp').open('w',newline='') as f:
            writer = csv.DictWriter(f,fieldnames=fields)
            writer.writeheader();writer.writerows(review)
        (out/'creators.csv.tmp').replace(out/'creators.csv')
        return summary


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    temporary.replace(path)


def scan_journals(journals, database, output, policy=None, mapping_paths=()):
    maps = None
    if mapping_paths:
        maps = {}
        for path in mapping_paths:
            for m in json.loads(Path(path).read_text())['mappings']:
                old = maps.get(m['kalshi_ticker'])
                if old and old != m['fixture_key']:
                    raise ValueError('conflicting fixture mapping')
                maps[m['kalshi_ticker']] = m['fixture_key']
    sniffer = Sniffer(database,Policy(**policy) if policy else None,maps)
    try:
        for directory in journals:
            path = Path(directory).resolve()
            manifest = json.loads((path/'manifest.json').read_text())
            identity = hashlib.sha256(packed(manifest['chunks'])).hexdigest()
            if sniffer.db.execute('SELECT 1 FROM journals WHERE identity=?',(identity,)).fetchone():
                continue
            channels = set()
            coverage_start = None
            last_at = previous_at = None
            segment = 0
            number = 0
            def seal(end):
                nonlocal coverage_start,segment
                if coverage_start is not None and end is not None and end >= coverage_start:
                    sniffer.db.execute('INSERT OR REPLACE INTO coverage VALUES(?,?,?)',
                                       (f'{identity}:{segment}',coverage_start,end))
                    segment += 1
                coverage_start = None
            for number,row in enumerate(read_journal(path),1):
                at = row['received_at']
                kind = row['kind']
                reference = f'{path}#row={number}'
                if kind in ('connect_attempt','disconnected','sequence_discontinuity','stop'):
                    seal(previous_at if kind=='sequence_discontinuity' else last_at)
                    if kind=='sequence_discontinuity' and {'communications','trade'} <= channels:
                        coverage_start = at
                    else:
                        channels.clear()
                    if kind not in ('stop','connect_attempt'):
                        sniffer.db.execute('INSERT INTO diagnostics VALUES(?,?,?)',(kind,at,reference))
                if last_at is not None and (at < last_at or at-last_at > 5):
                    seal(last_at)
                    if {'communications','trade'} <= channels:
                        coverage_start = at
                    sniffer.db.execute('INSERT INTO diagnostics VALUES(?,?,?)',('clock_or_receive_gap',at,reference))
                if kind=='message':
                    payload = row['payload']
                    typ, msg = payload.get('type'), payload.get('msg',{})
                    if typ=='subscribed':
                        channels.add(msg.get('channel'))
                        if {'communications','trade'} <= channels and coverage_start is None:
                            coverage_start = at
                    elif typ=='rfq_created':
                        sniffer.request(msg,at,reference,identity)
                    elif typ=='trade' and msg.get('trade_id'):
                        exchange_at = msg.get('ts_ms')
                        exchange_at = float(exchange_at)/1000 if exchange_at is not None else float(msg.get('ts',at))
                        sniffer.db.execute('INSERT OR IGNORE INTO trades VALUES(?,?,?,?)',
                            (msg['trade_id'],msg.get('market_ticker'),at,exchange_at))
                previous_at,last_at = last_at,at
                if number % 5000 == 0:
                    sniffer.prune_memory()
                    sniffer.db.commit()
            seal(last_at)
            sniffer.db.execute('INSERT INTO journals VALUES(?,?,?)',(identity,str(path),number))
            sniffer.db.commit()
        return sniffer.export(output)
    finally:
        sniffer.close()


def export_database(database, output):
    if not Path(database).is_file():
        raise ValueError('evidence database does not exist')
    sniffer = Sniffer(database)
    try:
        return sniffer.export(output)
    finally:
        sniffer.close()
