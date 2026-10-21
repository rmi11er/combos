"""Independent, resumable creator monitor publishing causal blacklist transitions."""
import json
import hashlib
from .event_store import encode, rfq_payload

DEFAULT_POLICY = {'window_seconds': 60, 'minimum_requests': 30, 'duplicate_fraction': .8,
                  'bursts_before_cooldown': 3, 'cooldown_seconds': 3600, 'long_legs': 20}


def creator_policy_gate(policy_state, mode):
    """Cheap creator gate applied before expensive source pricing.

    Shadow runs price blocked creators as counterfactuals for research. A
    future live path must return before pricing for blocked/cooldown creators.
    """
    blocked = policy_state.get('status') in ('blocked', 'cooldown')
    if mode == 'shadow':
        return {'eligible': not blocked, 'counterfactual': blocked, 'price': True}
    return {'eligible': not blocked, 'counterfactual': False, 'price': not blocked}


class CreatorService:
    name = 'creators'

    def __init__(self, store, policy=None):
        self.store = store; self.db = store.db; self.policy = dict(DEFAULT_POLICY, **(policy or {}))
        if any(v <= 0 for v in self.policy.values()) or self.policy['duplicate_fraction'] > 1:
            raise ValueError('invalid creator policy')
        self.version = hashlib.sha256(encode(self.policy).encode()).hexdigest()
        store.register(self.name, self.policy)
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS creator_requests (
                rfq_id TEXT PRIMARY KEY, creator TEXT NOT NULL, at REAL NOT NULL, signature TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS creator_request_window ON creator_requests(creator,at);
            CREATE INDEX IF NOT EXISTS creator_request_signature ON creator_requests(creator,signature,at);
            CREATE TABLE IF NOT EXISTS creator_history (
                creator TEXT NOT NULL, source_seq INTEGER NOT NULL, state TEXT NOT NULL,
                PRIMARY KEY(creator,source_seq));
            CREATE TABLE IF NOT EXISTS creator_active (
                creator TEXT PRIMARY KEY,status TEXT NOT NULL,expires_at REAL);
            CREATE INDEX IF NOT EXISTS creator_expiry ON creator_active(status,expires_at);
            CREATE TABLE IF NOT EXISTS creator_markout_groups (
                creator TEXT,fixture_group TEXT,horizon REAL,decision_seq INTEGER,adverse_move_cents REAL,
                PRIMARY KEY(creator,fixture_group,horizon));
        ''')

    def publish(self, creator, source, state, reason, evidence):
        previous=creator_state(self.store,creator,source['seq'],source['received_at'])
        state = dict(state, policy_version=self.version, evidence_source_seq=source['seq'], reason=reason)
        self.db.execute('INSERT INTO creator_history VALUES(?,?,?)', (creator,source['seq'],encode(state)))
        self.db.execute('INSERT INTO creator_active VALUES(?,?,?) ON CONFLICT(creator) DO UPDATE SET status=excluded.status,expires_at=excluded.expires_at',
                        (creator,state['status'],state.get('expires_at')))
        self.store.append('creator_policy',self.name, {'creator_id':creator,'previous_state':previous,'state':state,'evidence':evidence},
                          f'creator:{creator}:{source["seq"]}',source['received_at'])

    def apply(self, event):
        p = self.policy; at = event['received_at']; msg = rfq_payload(event)
        if event['kind']=='heartbeat':
            for row in self.db.execute("SELECT creator FROM creator_active WHERE status='cooldown' AND expires_at<=?",(at,)).fetchall():
                self.publish(row['creator'],event,{'status':'watch','expires_at':None},'cooldown_expired',{'heartbeat_seq':event['seq']})
            return
        if event['kind']=='markout' and event['payload'].get('status')=='observed':
            label=event['payload'];creator=label['creator_id']
            fixtures=sorted(leg['mapping']['fixture_key'] for leg in label['pricing']['legs'])
            self.db.execute('INSERT OR IGNORE INTO creator_markout_groups VALUES(?,?,?,?,?)',
                (creator,encode(fixtures),label['horizon_seconds'],label['decision_seq'],label['adverse_move_cents']))
            # Retain grouped evidence without automatically banning on our own fair.
            return
        if event['kind'] == 'creator_override':
            data = event['payload']; creator = data['creator_id']
            if not creator or data['status'] not in ('clear','watch','cooldown','blocked') or not data.get('reason') or not data.get('evidence'):
                raise ValueError('override requires creator, valid status, reason and evidence')
            if data['status'] == 'cooldown' and float(data.get('expires_at',0)) <= at:
                raise ValueError('cooldown requires future expiry')
            self.publish(creator,event,{'status':data['status'],'expires_at':data.get('expires_at')},data['reason'],data['evidence'])
            return
        if not msg or not msg.get('creator_id') or not msg.get('id'): return
        creator = msg['creator_id']; legs = msg.get('mve_selected_legs') or []
        valid = bool(legs) and all(l.get('market_ticker') and l.get('side') in ('yes','no') for l in legs)
        signature = hashlib.sha256(encode(sorted((l['market_ticker'],l['side']) for l in legs)).encode()).hexdigest() if valid else 'unusable'
        added = self.db.execute('INSERT OR IGNORE INTO creator_requests VALUES(?,?,?,?)', (msg['id'],creator,at,signature)).rowcount
        if not added: return
        counts = self.store.get(self.name,creator,{'requests':0,'bursts':0,'bursts_since_cooldown':0,'last_burst':-1e30,'last_at':-1e30,'long_leg_requests':0})
        counts['requests'] += 1; counts['long_leg_requests'] += int(len(legs)>=p['long_legs'])
        if at < counts['last_at']:
            self.store.append('creator_diagnostic',self.name,{'creator_id':creator,'reason':'clock_regression','source_seq':event['seq']},f'creator_clock:{event["seq"]}',at)
            self.store.put(self.name,creator,counts); return
        counts['last_at'] = at
        previous = creator_state(self.store,creator,event['seq'],at)
        publish = None; reason = None; window_evidence = None
        if previous.get('expired'):
            publish = {'status':'watch','expires_at':None}; reason = 'cooldown_expired'
        if valid:
            total = self.db.execute('SELECT COUNT(*) FROM creator_requests WHERE creator=? AND at>? AND at<=?', (creator,at-p['window_seconds'],at)).fetchone()[0]
            repeated = self.db.execute('SELECT COUNT(*) FROM creator_requests WHERE creator=? AND signature=? AND at>? AND at<=?', (creator,signature,at-p['window_seconds'],at)).fetchone()[0]
            if total >= p['minimum_requests'] and repeated/total >= p['duplicate_fraction'] and at-counts['last_burst'] >= p['window_seconds']:
                window_evidence = {'start_exclusive':at-p['window_seconds'],'end_inclusive':at,
                    'distinct_requests':total,'same_leg_set_requests':repeated,
                    'duplicate_fraction':repeated/total,'minimum_requests':p['minimum_requests'],
                    'required_duplicate_fraction':p['duplicate_fraction']}
                counts['bursts'] += 1; counts['bursts_since_cooldown'] += 1; counts['last_burst'] = at
                if previous['status'] not in ('blocked','cooldown'):
                    publish = {'status':'watch','expires_at':None}; reason='duplicate_request_burst'
                    if counts['bursts_since_cooldown'] >= p['bursts_before_cooldown']:
                        publish = {'status':'cooldown','expires_at':at+p['cooldown_seconds']}
                        reason='repeated_duplicate_bursts'; counts['bursts_since_cooldown']=0
        if publish:
            self.publish(creator,event,dict(publish,counts=counts.copy()),reason,{'rfq_id':msg['id'],
                'signature':signature,'counts':counts.copy(),'window':window_evidence})
        self.store.put(self.name,creator,counts)

    def step(self, limit=250):
        processed=0
        with self.store.transaction():
            for event in self.store.read(self.store.cursor(self.name),limit,
                    payload_kinds={'kalshi','rfq','heartbeat','markout','creator_override'}):
                try: self.apply(event)
                except (KeyError,ValueError,TypeError) as exc:
                    self.store.append('consumer_error',self.name,{'source_seq':event['seq'],'reason':str(exc)},f'creator_error:{event["seq"]}',event['received_at'])
                processed+=1
            if processed:self.store.checkpoint(self.name,event['seq'])
        return processed


def creator_state(store, creator, before_seq, at):
    row = store.db.execute('SELECT state FROM creator_history WHERE creator=? AND source_seq<? ORDER BY source_seq DESC LIMIT 1', (creator,before_seq)).fetchone()
    state = json.loads(row['state']) if row else {'status':'clear','policy_version':None,'evidence_source_seq':None}
    if state['status']=='cooldown' and at >= state['expires_at']:
        state = dict(state,status='watch',expired=True)
    return state
