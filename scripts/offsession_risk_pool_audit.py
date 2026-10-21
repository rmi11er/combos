"""Reproduce mixed signed/gross risk accounting in isolated disposable ledgers."""
import json
import tempfile
from pathlib import Path
from combos.event_store import EventStore
from combos.risk import RiskLedger

def run():
    rows=[]
    for signed_first in (True,False):
        with tempfile.TemporaryDirectory(prefix='combos-risk-audit-') as directory:
            store=EventStore(Path(directory)/'events.sqlite')
            policy={'capital_dollars':1000,'per_contract_dollars':100,'per_combo_dollars':1000,'per_fixture_dollars':100}
            ledger=RiskLedger(store,policy)
            outcomes=[]
            for i,signed in enumerate((signed_first,not signed_first)):
                buckets={'contract':['A'],'combo':['combo:'+str(i)],'fixture':['fixture:A']}
                sides={'contract':[{'key':'A','side':1}],'fixture':[{'key':'fixture:A','side':1}]} if signed else None
                with store.transaction():
                    outcomes.append(ledger.reserve(str(i),'audit',80,buckets,200,{'quantity':100},signed_buckets=sides))
            rows.append({'signed_first':signed_first,'admitted':[r['allowed'] for r in outcomes],
                'combined_same_direction_fixture_liability':160,'fixture_cap':100,'cash_committed':1000-ledger.available()/10000})
            store.close()
    assert all(r['admitted']==[True,True] for r in rows)
    p=Path(__file__).resolve().parents[1]/'runs/offsession_review_20260910/risk_pool_audit.json'
    p.write_text(json.dumps(rows,indent=2)+'\n');print(p.read_text())

if __name__=='__main__':run()
