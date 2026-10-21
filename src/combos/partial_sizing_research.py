"""Offline causal sizing adapter; never submits quotes or modifies production policy."""
from dataclasses import asdict
from collections import Counter
from decimal import Decimal, ROUND_FLOOR
import heapq
from .backtest import BacktestConfig, run_backtest, validate_opportunity
from .event_store import EventStore
from .risk import RiskLedger, units
from .fees import kalshi_fill_fee


def sized(row, hundredths):
    q = Decimal(hundredths) / 100
    p = Decimal(str(row['yes_price']))
    fee = kalshi_fill_fee(q, 1-p, str(row['source']['fee_basis']['rate']))['net_fee']
    return {**row, 'quantity': float(q), 'maker_fee': float(fee)}


def cost(row):
    # Match the existing ledger's float expression and conservative 1e-4 ceil.
    return units(row['quantity']*(1-row['yes_price'])+row['maker_fee'])


def room(ledger, row):
    available = ledger.available()
    for kind, keys in row['buckets'].items():
        cap = int(Decimal(str(ledger.policy['per_'+kind+'_dollars'])) * Decimal(str(row['risk_multiplier'])) * 10000)
        for key in set(keys):
            used = ledger.db.execute("SELECT COALESCE(SUM(e.cost),0) FROM exposure e JOIN reservations r ON r.id=e.reservation WHERE e.bucket=? AND r.status IN ('reserved','simulated_filled')", (kind+':'+key,)).fetchone()[0]
            available = min(available, cap-used)
    return max(0, available)


def run_partial(opportunities, start, end, config=None):
    config = config or BacktestConfig(entry_basis='point')
    if config.entry_basis != 'point' or config.entry_filter != 'minimum_edge' or config.minimum_net_edge_unit != 'combo_contract' or config.maximum_yes_premium_dollars is not None:
        raise ValueError('partial study requires point per-combo edge and no premium cap')
    selected, audit = [], []
    seen=set()
    for r in opportunities:
        validate_opportunity(r,start,end)
        key=r['model'],r['evaluation_id']
        if key in seen: raise ValueError('duplicate opportunity')
        seen.add(key)
        if Decimal(str(r['quantity']))*100 != (Decimal(str(r['quantity']))*100).to_integral_value():
            raise ValueError('quantity must use .01 grid')
        recalculated=sized(r,int(Decimal(str(r['quantity']))*100))
        if abs(recalculated['maker_fee']-r['maker_fee'])>1e-9: raise ValueError('input maker fee disagrees with exact fee scenario')
    for model in sorted({r['model'] for r in opportunities}):
        store=EventStore(':memory:'); ledger=RiskLedger(store,asdict(config)); pending=[]
        try:
            for row in sorted((r for r in opportunities if r['model']==model),key=lambda r:(r['at'],r['evaluation_id'])):
                at=row['at']; identifier=row['evaluation_id']
                while pending and pending[0][0]<=at:
                    when,old,payout=heapq.heappop(pending)
                    with store.transaction(): ledger.transition(old,'simulated_settled',when,0,payout)
                record={'model':model,'evaluation_id':identifier,'at':at,'observed_quantity':row['quantity'],'selected_quantity':0.,'reason':'quote_guard'}
                if row['quote_allowed']:
                    available=room(ledger,row); record['risk_room_dollars']=available/10000
                    hi=int(Decimal(str(row['quantity']))*100); lo=0
                    while lo<hi:
                        mid=(lo+hi+1)//2
                        if cost(sized(row,mid))<=available: lo=mid
                        else: hi=mid-1
                    record['largest_affordable_quantity']=lo/100
                    record['reason']='risk_capacity_below_minimum_quantity' if not lo else 'insufficient_edge'
                    # Rounding makes per-share edge nonmonotone; examine the exact
                    # remaining grid rather than assuming binary search is valid for edge.
                    if row['yes_price']-row['fair_point']-config.minimum_net_edge_per_share >= float(Decimal(str(row['source']['fee_basis']['rate']))*Decimal(str(row['yes_price']))*(1-Decimal(str(row['yes_price'])))):
                        while lo:
                            candidate=sized(row,lo); q=candidate['quantity']
                            if q*(row['yes_price']-row['fair_point'])-candidate['maker_fee'] >= q*config.minimum_net_edge_per_share:
                                with store.transaction():
                                    risk=ledger.reserve(identifier,'historical_creator_unknown',q*(1-row['yes_price'])+candidate['maker_fee'],row['buckets'],at+1,{'quantity':q},row['risk_multiplier'])
                                    if not risk['allowed']: raise AssertionError('sizing and canonical ledger disagree')
                                    ledger.transition(identifier,'simulated_filled',at,0)
                                selected.append(candidate); record.update(selected_quantity=q,reason='accepted_partial' if q<row['quantity'] else 'accepted_full')
                                if row.get('settled_at') is not None:
                                    heapq.heappush(pending,(row['settled_at']+config.settlement_delay_seconds,identifier,q*(1-row['yes_settlement'])))
                                break
                            lo-=1
                audit.append(record)
        finally: store.close()
    result=run_backtest(selected,start,end,config,True)
    if any(not d['accepted'] for d in result['decisions']): raise AssertionError('replay rejected preallocated sizing')
    for summary in result['summaries']:
        items=[a for a in audit if a['model']==summary['model']]
        summary['portfolio_replay_evaluations']=summary['evaluations']
        summary['evaluations']=len(items)
        summary['sizing_decisions']=dict(Counter(a['reason'] for a in items))
    result.update(sizing_audit=audit,execution_assumption='Hypothetical partial public-print participation; observed quantity is an upper bound, not evidence of RFQ partial acceptance.')
    return result
