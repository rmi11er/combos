"""Atomic quote intents and persistent capital holds, awaiting live reconciliation.

Uses supplied canonical risk buckets and an explicitly initialized cash balance.
No local timer or transport acknowledgment releases a dispatched hold.
"""
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import json
import time
from .execution_journal import encoded


def units(value, rounding=ROUND_CEILING):
    d = Decimal(str(value))
    if not d.is_finite() or d < 0:
        raise ValueError('invalid nonnegative risk amount')
    return int((d*10000).to_integral_value(rounding=rounding))


class ExecutionRiskHolds:
    def __init__(self, journal, config):
        self.journal=journal;self.db=journal.db
        names=('capital_dollars','maximum_committed_dollars','per_contract_dollars','per_combo_dollars','per_fixture_dollars')
        self.limits={k:units(config[k],ROUND_FLOOR) for k in names}
        if any(v<=0 for v in self.limits.values()):
            raise ValueError('positive execution risk limits required')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS execution_risk_config (id INTEGER PRIMARY KEY CHECK(id=1),value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS execution_holds (
                reservation_id TEXT PRIMARY KEY, operation_key TEXT UNIQUE NOT NULL,
                rfq_id TEXT NOT NULL, units INTEGER NOT NULL, buckets TEXT NOT NULL,
                multiplier TEXT NOT NULL, state TEXT NOT NULL, created_at REAL NOT NULL);
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_hold_per_rfq ON execution_holds(rfq_id) WHERE state='held';
        ''')
        with journal.transaction():
            prior=self.db.execute('SELECT value FROM execution_risk_config WHERE id=1').fetchone()
            value=encoded(self.limits)
            if prior and prior[0]!=value:
                raise ValueError('execution risk configuration changed')
            if not prior:self.db.execute('INSERT INTO execution_risk_config VALUES(1,?)',(value,))

    def available_units(self):
        committed=self.db.execute("SELECT COALESCE(SUM(units),0) FROM execution_holds WHERE state='held'").fetchone()[0]
        return max(0,min(self.limits['capital_dollars'],self.limits['maximum_committed_dollars'])-committed)

    def reserve_create(self, operation_key, reservation_id, body, maximum_loss_dollars, buckets, risk_multiplier=1):
        rfq_id=body.get('rfq_id')
        if not isinstance(rfq_id,str) or not rfq_id:
            raise ValueError('RFQ identity required')
        if set(buckets)!={'contract','combo','fixture'} or any(not ks or any(not isinstance(k,str) or not k for k in ks) for ks in buckets.values()):
            raise ValueError('complete canonical risk buckets required')
        buckets={kind:sorted(set(keys)) for kind,keys in buckets.items()}
        multiplier=Decimal(str(risk_multiplier))
        if not multiplier.is_finite() or not 0<multiplier<=1:
            raise ValueError('invalid risk multiplier')
        cost=units(maximum_loss_dollars)
        if cost<=0:raise ValueError('positive quote liability required')
        identity=(operation_key,rfq_id,cost,encoded(buckets),str(multiplier.normalize()))
        with self.journal.transaction():
            prior=self.db.execute('SELECT operation_key,rfq_id,units,buckets,multiplier,state FROM execution_holds WHERE reservation_id=?',(reservation_id,)).fetchone()
            if prior:
                if tuple(prior)[:5]!=identity or prior['state']!='held':
                    raise ValueError('conflicting or closed risk reservation')
            else:
                if self.db.execute("SELECT 1 FROM execution_holds WHERE rfq_id=? AND state='held'",(rfq_id,)).fetchone():
                    raise ValueError('RFQ already has a held quote')
                if cost>self.available_units():raise ValueError('execution_cash_limit')
                used={kind:{key:0 for key in keys} for kind,keys in buckets.items()}
                for old in self.db.execute("SELECT units,buckets FROM execution_holds WHERE state='held'"):
                    old_buckets=json.loads(old['buckets'])
                    for kind,keys in used.items():
                        for key in keys:
                            if key in old_buckets[kind]:keys[key]+=old['units']
                for kind,keys in used.items():
                    cap=int((Decimal(self.limits['per_'+kind+'_dollars'])*multiplier).to_integral_value(rounding=ROUND_FLOOR))
                    if any(value+cost>cap for value in keys.values()):
                        raise ValueError('execution_'+kind+'_risk_limit')
                self.db.execute('INSERT INTO execution_holds VALUES(?,?,?,?,?,?,?,?)',
                    (reservation_id,operation_key,rfq_id,cost,identity[3],identity[4],'held',time.time()))
            # Nested savepoint ensures hold and exact request commit together.
            return self.journal.prepare(operation_key,reservation_id,'POST',
                '/trade-api/v2/communications/quotes',body)

    def abandon_unsent(self, reservation_id):
        """Local release is allowed only when no associated request was sent."""
        with self.journal.transaction():
            hold=self.db.execute('SELECT state FROM execution_holds WHERE reservation_id=?',(reservation_id,)).fetchone()
            if hold is None:raise KeyError(reservation_id)
            if hold['state']=='abandoned':return
            sent=self.db.execute("SELECT 1 FROM execution_intents WHERE reservation_id=? AND state NOT IN ('prepared','abandoned')",(reservation_id,)).fetchone()
            if sent:raise ValueError('dispatched_hold_requires_exchange_reconciliation')
            now=time.time()
            keys=[r[0] for r in self.db.execute("SELECT operation_key FROM execution_intents WHERE reservation_id=? AND state='prepared'",(reservation_id,))]
            if not keys:raise ValueError('hold_has_no_unsent_intent')
            self.db.execute("UPDATE execution_intents SET state='abandoned',updated_at=? WHERE reservation_id=? AND state='prepared'",(now,reservation_id))
            self.db.execute("UPDATE execution_holds SET state='abandoned' WHERE reservation_id=?",(reservation_id,))
            for key in keys:self.journal.event(key,now,'abandoned',{'reason':'never_dispatched'})
