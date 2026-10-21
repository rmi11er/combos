"""Atomic maximum-loss reservations. Simulated fills are always explicitly labeled."""
from decimal import Decimal, ROUND_CEILING
import json
import math
from .event_store import encode


def units(dollars):
    value = Decimal(str(dollars))
    if not value.is_finite() or value < 0: raise ValueError('invalid risk dollars')
    return int((value*10000).to_integral_value(rounding=ROUND_CEILING))


class RiskLedger:
    def __init__(self, store, policy):
        self.store = store; self.db = store.db; self.policy = policy
        units(policy['capital_dollars'])
        for key in ('per_contract_dollars', 'per_combo_dollars', 'per_fixture_dollars'):
            if policy.get(key) is not None and units(policy[key]) <= 0: raise ValueError('risk caps must be positive')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS reservations (
                id TEXT PRIMARY KEY, creator TEXT, status TEXT NOT NULL,
                cost INTEGER NOT NULL, expires_at REAL NOT NULL, pnl INTEGER NOT NULL DEFAULT 0,
                context TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS exposure (
                reservation TEXT NOT NULL, bucket TEXT NOT NULL, cost INTEGER NOT NULL,
                PRIMARY KEY(reservation,bucket));
            CREATE INDEX IF NOT EXISTS exposure_bucket ON exposure(bucket);
            CREATE TABLE IF NOT EXISTS signed_exposure (
                reservation TEXT NOT NULL, bucket TEXT NOT NULL, side INTEGER NOT NULL, cost INTEGER NOT NULL,
                PRIMARY KEY(reservation,bucket,side));
            CREATE INDEX IF NOT EXISTS signed_exposure_bucket ON signed_exposure(bucket,side);
            CREATE INDEX IF NOT EXISTS reservations_active_cost ON reservations(status,cost);
            CREATE INDEX IF NOT EXISTS reservations_realized_pnl ON reservations(pnl) WHERE pnl<>0;
        ''')

    def available(self):
        committed = self.db.execute("SELECT COALESCE(SUM(cost),0) FROM reservations WHERE status IN ('reserved','simulated_filled')").fetchone()[0]
        pnl = self.db.execute('SELECT COALESCE(SUM(pnl),0) FROM reservations WHERE pnl<>0').fetchone()[0]
        return units(self.policy['capital_dollars']) + pnl - committed

    def bucket_state(self, bucket, held_only=False):
        statuses="('simulated_filled')" if held_only else "('reserved','simulated_filled')"
        gross=self.db.execute(f'SELECT COALESCE(SUM(e.cost),0) FROM exposure e JOIN reservations r ON r.id=e.reservation WHERE e.bucket=? AND r.status IN {statuses}',(bucket,)).fetchone()[0]
        sides={-1:0,1:0};credits={-1:0,1:0}
        for row in self.db.execute(f'SELECT e.side,e.cost,r.status,r.context FROM signed_exposure e JOIN reservations r ON r.id=e.reservation WHERE e.bucket=? AND r.status IN {statuses}',(bucket,)):
            sides[row['side']]+=row['cost']
            if row['status']=='simulated_filled' and self.policy.get('inventory_fitting',{}).get('enabled'):
                c=json.loads(row['context'])
                if c.get('moneyline_offset',{}).get('eligible'):
                    credits[row['side']]+=max(0,int(Decimal(str(c['quantity']))*10000)-row['cost'])
        return {'gross':gross,'sides':sides,'credits':credits,
                'risk_dollars':(gross+max(0,*(sides[d]-credits[-d] for d in (-1,1))))/10000}

    def fill(self, identifier, quantity, price, at, source_seq):
        """Atomic partial paper allocation; no pending hedge earns credit."""
        from .pricing import short_yes_economics
        if not self.db.in_transaction:raise RuntimeError('fill requires atomic transaction')
        row=self.db.execute('SELECT * FROM reservations WHERE id=?',(identifier,)).fetchone()
        if row is None or row['status']!='reserved':raise ValueError('paper_fill_not_reserved')
        c=json.loads(row['context']);q=Decimal(str(quantity));original=Decimal(str(c['quantity']))
        if not q.is_finite() or q<=0 or q>original or q%Decimal('.01'):raise ValueError('invalid_fill_quantity')
        if not math.isfinite(price) or not c['yes_ask']<=price<1:raise ValueError('invalid_fill_price')
        actual=units(short_yes_economics(float(q),price,0,c['maker_fee_rate'])['maximum_loss'])
        remainder=original-q
        remaining_cost=0 if not remainder else row['cost']-actual
        if actual>row['cost'] or remaining_cost<0:raise ValueError('fill_exceeds_reserved_cash')
        if remainder and remaining_cost<units(short_yes_economics(float(remainder),c['yes_ask'],0,c['maker_fee_rate'])['maximum_loss']):
            raise ValueError('partial_fill_fee_rounding_exceeds_reservation')
        if not remainder:
            c.update(quantity=float(q),yes_ask=price)
            self.db.execute('UPDATE reservations SET cost=?,context=? WHERE id=?',(actual,encode(c),identifier))
            for table in ('exposure','signed_exposure'):self.db.execute(f'UPDATE {table} SET cost=? WHERE reservation=?',(actual,identifier))
            self.transition(identifier,'simulated_filled',at,source_seq)
            return identifier
        child=identifier+':fill:'+str(source_seq)
        filled=dict(c,quantity=float(q),yes_ask=price,parent_reservation=identifier)
        c['quantity']=float(remainder)
        self.db.execute('UPDATE reservations SET cost=?,context=? WHERE id=?',(remaining_cost,encode(c),identifier))
        self.db.execute('INSERT INTO reservations(id,creator,status,cost,expires_at,context) VALUES(?,?,?,?,?,?)',(child,row['creator'],'simulated_filled',actual,row['expires_at'],encode(filled)))
        for table,columns in (('exposure','bucket'),('signed_exposure','bucket,side')):
            self.db.execute(f'INSERT INTO {table} SELECT ?,{columns},? FROM {table} WHERE reservation=?',(child,actual,identifier))
            self.db.execute(f'UPDATE {table} SET cost=? WHERE reservation=?',(remaining_cost,identifier))
        self.store.append('risk_transition','shadow',{'reservation_id':child,'parent_reservation':identifier,'new_status':'simulated_filled','quantity':float(q),'source_seq':source_seq},f'risk:{child}:simulated_filled',at)
        return child

    def reserve(self, identifier, creator, cost_dollars, buckets, expires_at, context,
                limit_multiplier=1., signed_buckets=None):
        if not self.db.in_transaction: raise RuntimeError('reservation requires atomic transaction')
        if not math.isfinite(limit_multiplier) or not 0 < limit_multiplier <= 1:
            raise ValueError('invalid risk limit multiplier')
        if not math.isfinite(expires_at): raise ValueError('invalid reservation expiry')
        cost = units(cost_dollars)
        if cost <= 0: raise ValueError('reservation cost must be positive')
        raw = encode(context)
        existing = self.db.execute('SELECT * FROM reservations WHERE id=?', (identifier,)).fetchone()
        if existing:
            if existing['context'] != raw or existing['cost'] != cost: raise ValueError('conflicting reservation')
            return {'allowed': existing['status'] == 'reserved', 'reason': 'already_processed', 'available_dollars': self.available()/10000}
        before = self.available()
        if any(self.policy.get(k) is None for k in ('per_contract_dollars','per_combo_dollars','per_fixture_dollars')):
            return {'allowed': False, 'reason': 'risk_limits_unconfigured', 'available_dollars': before/10000}
        if cost > before: return {'allowed': False, 'reason': 'capital_exhausted', 'available_dollars': before/10000}
        signed_buckets = signed_buckets or {}
        if set(signed_buckets) - {'contract', 'fixture'}:
            raise ValueError('invalid signed risk bucket family')
        for kind, rows in signed_buckets.items():
            if not isinstance(rows, list) or not rows:
                raise ValueError('signed risk rows required')
            for row in rows:
                if not isinstance(row, dict) or not row.get('key') or row.get('side') not in (-1, 1):
                    raise ValueError('invalid signed risk row')
        checks = []
        for kind, keys in buckets.items():
            # Floor reduced caps; never round a risk allowance upward.
            cap = int(Decimal(str(self.policy[f'per_{kind}_dollars']))*Decimal(str(limit_multiplier))*10000)
            for key in sorted(set(keys)):
                bucket = kind+':'+key
                signed_rows = [r for r in signed_buckets.get(kind, []) if r['key'] == key]
                snapshot=self.bucket_state(bucket)
                gross=snapshot['gross'];sides=snapshot['sides'];credits=snapshot['credits']
                used=gross+max(0,*(sides[d]-credits[-d] for d in (-1,1)))
                added={d:sum(cost for r in signed_rows if r['side']==d) for d in (-1,1)}
                stressed=gross+(0 if signed_rows else cost)+max(0,*(sides[d]+added[d]-credits[-d] for d in (-1,1)))
                checks.append({'bucket':bucket,'used_dollars':used/10000,'added_dollars':cost/10000,
                    'limit_dollars':cap/10000,'limit_multiplier':limit_multiplier,
                    'netted':bool(signed_rows),'side_used_dollars':{str(k):v/10000 for k,v in sides.items()},
                    'gross_dollars':gross/10000,'filled_opposing_credit_dollars':{str(k):v/10000 for k,v in credits.items()},
                    'stressed_dollars':stressed/10000})
                if stressed>cap:
                    return {'allowed':False,'reason':f'{kind}_risk_limit','checks':checks,'available_dollars':before/10000}
        if set(buckets) != {'contract','combo','fixture'} or any(not v for v in buckets.values()):
            raise ValueError('all risk bucket families required')
        self.db.execute('INSERT INTO reservations(id,creator,status,cost,expires_at,context) VALUES(?,?,?,?,?,?)',
                        (identifier,creator,'reserved',cost,expires_at,raw))
        signed_keys = {(kind, row['key']) for kind, rows in signed_buckets.items() for row in rows}
        for check in checks:
            kind, key = check['bucket'].split(':', 1)
            if (kind, key) not in signed_keys:
                self.db.execute('INSERT INTO exposure VALUES(?,?,?)', (identifier,check['bucket'],cost))
        for kind, rows in signed_buckets.items():
            for row in rows:
                self.db.execute('INSERT INTO signed_exposure VALUES(?,?,?,?)',
                                (identifier, kind+':'+row['key'], row['side'], cost))
        return {'allowed': True, 'checks': checks, 'available_before_dollars': before/10000,
                'available_after_dollars': self.available()/10000}

    def transition(self, identifier, status, at, source_seq, payout_dollars=None):
        if not self.db.in_transaction: raise RuntimeError('transition requires atomic transaction')
        row = self.db.execute('SELECT * FROM reservations WHERE id=?', (identifier,)).fetchone()
        if row is None: raise ValueError('unknown reservation')
        if row['status'] == status: return
        allowed = {'reserved': {'expired','cancelled','simulated_filled'}, 'simulated_filled': {'simulated_settled'}}
        if status not in allowed.get(row['status'], set()): raise ValueError('invalid reservation transition')
        pnl = 0
        payout_record = None
        if status == 'simulated_settled':
            if payout_dollars is None: raise ValueError('settlement payout required')
            context = json.loads(row['context'])
            if payout_dollars > context['quantity']: raise ValueError('payout exceeds maximum contract payout')
            pnl = units(payout_dollars)-row['cost']
            payout_record = float(payout_dollars)
        self.db.execute('UPDATE reservations SET status=?,pnl=? WHERE id=?', (status,pnl,identifier))
        transition_payload = {'reservation_id': identifier,'old_status': row['status'],
            'new_status': status,'source_seq': source_seq,'pnl_dollars': pnl/10000}
        if payout_record is not None:
            transition_payload['payout_dollars'] = payout_record
        self.store.append('risk_transition','shadow', transition_payload,
            f'risk:{identifier}:{status}', at)

    def expire(self, at, source_seq):
        ids = self.db.execute("SELECT id FROM reservations WHERE status='reserved' AND expires_at<=?", (at,)).fetchall()
        for row in ids: self.transition(row['id'],'expired',at,source_seq)
