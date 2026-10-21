"""Chronological pre-risk census / public-tape inventory sensitivity.

Research only. Gross cash is retained. Signed-cap accounting combines unsigned
exposure with both signed sides. Low-charge trades require a filled-inventory
hedge and a nonpositive bound on incremental model variance at quote and match.
No live acceptance or fill-time source reconstruction is implied.
"""
import json, gzip, math, heapq, sqlite3
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path
from decimal import Decimal, ROUND_CEILING
from combos.shadow_engine import quote_price

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runs/offsession_review_20260910'
CENSUS=OUT/'candidate_census'
TAPE=ROOT/'runs/shadow_exchange_fallback_20260909/public_session'

def probability(legs,probs):
    return math.prod(probs[k] if s==1 else 1-probs[k] for f,k,s,t in legs)

def second(legs,probs):
    return math.prod((probs[k] if s==1 else 1-probs[k])-(min(.01,2*probs[k],2*(1-probs[k]))/4 if t else 0) for f,k,s,t in legs)

def intersection(a,b,probs,robust=False):
    """Upper E[AB]: exact complements; other same-fixture payoffs use Frechet.

    Nominal: independent fixtures. Robust: no cross-fixture independence,
    intersecting payout bounded by weakest fixture constraint and combo means.
    """
    byfixture=defaultdict(list)
    for l in a:byfixture[l[0]].append(l)
    for l in b:byfixture[l[0]].append(l)
    bounds=[]
    for ls in byfixture.values():
        ps=[probs[k] if s==1 else 1-probs[k] for f,k,s,t in ls]
        if len(ls)==1:value=ps[0]
        elif ls[0][1]==ls[1][1]:
            tie=min(.01,2*probs[ls[0][1]],2*(1-probs[ls[0][1]]))/4 if ls[0][3] else 0
            value=tie if ls[0][2]!=ls[1][2] else ps[0]-tie
        else:value=min(ps)
        bounds.append(value)
    if robust:return min(probability(a,probs),probability(b,probs),*bounds)
    return math.prod(bounds)

def variance_delta(legs,qty,positions,probs,robust=False):
    p=probability(legs,probs)
    # Binary variance bounds fractional tie payouts in robust mode.
    own=p*(1-p) if robust else second(legs,probs)-p*p
    covariance=0.;fs={l[0] for l in legs}
    for old,n in positions.values():
        if not robust and not fs.intersection(l[0] for l in old):continue
        covariance+=n*(intersection(legs,old,probs,robust)-p*probability(old,probs))
    return qty*qty*own+2*qty*covariance

def load():
    qs=[];probs={}
    for raw in (CENSUS/'quotes.jsonl').open():
        q=json.loads(raw);legs=[];ps={};ml=True
        for l in q['pricing']['legs']:
            r=l['risk'];p=l['fair']['point'];selected=p if l['side']=='yes' else 1-p
            ps[r['key']]=selected if r['selected_sign']==1 else 1-selected
            isml=l['market_type']=='moneyline' and l['period']=='full_game'
            ml &= isml
            legs.append((l['fixture'],r['key'],r['selected_sign'],isml))
        assert abs(q['economics']['maker_fee'])<1e-12,'nonzero fee needs exact scenario repricing'
        qs.append({'key':q['quote_key'],'run':q['run'],'at':q['decision_completed_at'],'expiry':q['valid_until'],
            'ticker':q['market_ticker'],'fair':q['pricing']['joint']['point'],'legs':legs,'probs':ps,
            'ml':ml,'mult':q['pricing']['risk_multiplier'],'ask':q['yes_ask'],
            'fixed':q['request'].get('contracts_fp'),'target':q['request'].get('target_cost_dollars')})
    assert len(qs)==227469
    tickers={q['ticker'] for q in qs};trades={}
    manifest=json.loads((TAPE/'manifest.json').read_text());assert all(b['complete'] for b in manifest)
    for bucket in manifest:
        for page in range(bucket['pages']):
            with gzip.open(TAPE/f"{bucket['lo']}_{page:04d}.json.gz",'rt') as stream:raw=json.load(stream)
            for t in raw['payload']['trades']:
                if t['ticker'] not in tickers or (t.get('taker_outcome_side') or t.get('taker_side'))!='yes' or t.get('is_block_trade'):continue
                trades[t['trade_id']]={'id':t['trade_id'],'ticker':t['ticker'],
                    'at':datetime.fromisoformat(t['created_time'].replace('Z','+00:00')).timestamp(),
                    'price':float(t['yes_price_dollars']),'qty':float(t['count_fp'])}
    terms={}
    for run in {q['run'] for q in qs}:
        db=sqlite3.connect((ROOT/'runs'/run/'events.sqlite').as_uri()+'?mode=ro',uri=True)
        terms[run]=json.loads(db.execute("SELECT value FROM state WHERE owner='runtime' AND key='manifest'").fetchone()[0])['config']['combo_terms'];db.close()
    for q in qs:q['grids']=next(v['price_ranges'] for k,v in terms[q['run']].items() if q['ticker'].startswith(k))
    print('loaded',len(qs),'candidates',len(trades),'YES prints',flush=True)
    return qs,list(trades.values())

class Scenario:
    def __init__(self,name,signed,discount,robust=False,payoff_credit=False,fill_checks=None,discount_edge=.0005,trigger=.9,delay=0.):
        self.name=name;self.signed=signed;self.discount=discount;self.robust=robust
        self.payoff_credit=payoff_credit;self.held_premium=defaultdict(float)
        self.fill_checks=fill_checks
        self.discount_edge=discount_edge;self.trigger=trigger;self.delay=delay
        self.used=defaultdict(float);self.held=defaultdict(float);self.pending={};self.by_market=defaultdict(dict);self.expiry=[]
        self.positions={};self.probs={};self.counts=Counter();self.fills=[];self.peak=0.;self.maxrisk=defaultdict(float)
    def buckets(self,q):
        result=[('total',0),('combo:'+q['ticker'],0)]
        for f,k,s,t in q['legs']:
            side=-s if q['ml'] and self.signed else 0
            result.extend([('fixture:'+f,side),('contract:'+k,side)])
        return list(set(result))
    def risk(self,b,pool):
        return pool[b,0]+max(0.,*(pool[b,s]-(self.held_premium[b,-s] if self.payoff_credit else 0.) for s in (-1,1)))
    def fits(self,q,cost,bs):
        for b,s in bs:
            cap=10000 if b=='total' else (1000 if b.startswith('fixture:') else 500)*q['mult']
            new=self.used[b,0]+(cost if s==0 else 0)+max(0.,*(self.used[b,d]+(cost if s==d else 0)-(self.held_premium[b,-d] if self.payoff_credit else 0.) for d in (-1,1)))
            if new>cap+1e-8:return False
        return True
    def hedge(self,q,qty,robust=False,ask=None):
        if not q['ml'] or not self.positions:return False,None
        focus=[f for f,k,s,t in q['legs'] if self.risk('fixture:'+f,self.held)>=1000*self.trigger*q['mult']]
        if not focus:return False,None
        offsets=False
        for f in focus:
            olddelta=0.
            for old,n in self.positions.values():
                for ff,k,s,t in old:
                    if ff==f:
                        olddelta-=n*s*probability([l for l in old if l[0]!=f],self.probs)
            leg=next(l for l in q['legs'] if l[0]==f)
            change=-qty*leg[2]*probability([l for l in q['legs'] if l[0]!=f],self.probs)
            if olddelta*change<0 and abs(olddelta+change)<abs(olddelta)-1e-8:offsets=True
        if not offsets:return False,None
        if self.payoff_credit:
            if ask is None:raise ValueError('hedge price required for payoff credit')
            released=False
            for f in focus:
                b='fixture:'+f;side=-next(l[2] for l in q['legs'] if l[0]==f)
                new=self.held[b,0]+max(0.,*(self.held[b,d]+(qty*(1-ask) if d==side else 0)-self.held_premium[b,-d]-(qty*ask if -d==side else 0) for d in (-1,1)))
                if new<self.risk(b,self.held)-1e-8:released=True
            if not released:return False,None
        delta=variance_delta(q['legs'],qty,self.positions,self.probs,robust)
        return delta<=1e-8,delta
    def expire(self,at):
        while self.expiry and self.expiry[0][0]<=at:
            _,key=heapq.heappop(self.expiry)
            if key not in self.pending:continue
            p=self.pending.pop(key);self.by_market[p['q']['ticker']].pop(key,None)
            for b in p['buckets']:self.used[b]-=p['remaining']*(1-p['ask'])
    def quote(self,q):
        self.probs.update(q['probs']);self.expire(q['at'])
        def terms(edge):
            ask=q['ask'] if edge==.003 else quote_price(q['fair'],edge,0,q['grids'])
            fixed=q['fixed'];qty=float(fixed) if fixed and float(fixed)>0 else float((Decimal(str(q['target']))/Decimal(str(ask))).to_integral_value(rounding=ROUND_CEILING))
            return ask,qty
        ask,qty=terms(.003);discounted=False;delta=None
        if self.discount:
            lo,n=terms(self.discount_edge)
            okay,delta=self.hedge(q,n,self.robust,lo)
            if okay:ask,qty,discounted=lo,n,True;self.counts['discount_candidates']+=1
        if qty*(1-ask)>250+1e-8:self.counts['full_size_ticket_rejected']+=1;return
        bs=self.buckets(q);cost=qty*(1-ask)
        if q['at']+self.delay>=q['expiry']:self.counts['expired_before_transport']+=1;return
        if not self.fits(q,cost,bs):self.counts['risk_rejected']+=1;return
        for b in bs:self.used[b]+=cost
        self.peak=max(self.peak,self.used['total',0]);self.counts['admitted']+=1
        if discounted:self.counts['discount_admitted']+=1
        row={'q':q,'ask':ask,'remaining':qty,'buckets':bs,'discounted':discounted}
        self.pending[q['key']]=row;self.by_market[q['ticker']][q['key']]=row;heapq.heappush(self.expiry,(q['expiry'],q['key']))
        for b,s in bs:self.maxrisk[b]=max(self.maxrisk[b],self.risk(b,self.used))
    def trade(self,t):
        self.expire(t['at']);available=t['qty']
        for key,p in list(self.by_market[t['ticker']].items()):
            if p['ask']>t['price']+1e-9 or p['remaining']<=0:continue
            q=p['q'];n=min(available,p['remaining']);delta=None
            if t['at']<q['at']+self.delay:continue
            if self.fill_checks is not None:
                check=self.fill_checks[q['key'],t['id']]
                hurdle=self.discount_edge if p['discounted'] else .003
                if not check['available'] or not check['allowed'] or p['ask']-check['point']+1e-12<hurdle or abs(check['point']-q['fair'])>.01+1e-12 or check['risk_multiplier']<q['mult']:
                    self.counts['fill_time_pricing_rejected']+=1;continue
                self.probs.update(check['probs'])
            if p['discounted']:
                okay,delta=self.hedge(q,n,self.robust,p['ask'])
                if not okay:self.counts['discount_match_risk_rejected']+=1;continue
            # Allocation of each tape contract is once per independent scenario.
            before={f:self.risk('fixture:'+f,self.held) for f,k,s,tie in q['legs']}
            p['remaining']-=n;available-=n;cost=n*(1-p['ask'])
            for b in p['buckets']:
                self.held[b]+=cost
                if b[1]!=0:self.held_premium[b]+=n*p['ask']
            old=self.positions.get(q['ticker'],(q['legs'],0))
            self.positions[q['ticker']]=(old[0],old[1]+n)
            self.fills.append({'quote_key':key,'ticker':q['ticker'],'trade_id':t['id'],'at':t['at'],
                'quantity':n,'ask':p['ask'],'fair':q['fair'],'collateral':cost,
                'model_edge':n*(p['ask']-q['fair']),'discounted':p['discounted'],'incremental_variance_upper':delta,
                'fixture_risk_before':before,'fixture_risk_after':{f:self.risk('fixture:'+f,self.held) for f in before}})
            if available<=1e-9:break
    def summary(self):
        self.expire(float('inf'))
        var=0.;ps=list(self.positions.values())
        for i,(legs,n) in enumerate(ps):
            p=probability(legs,self.probs);var+=n*n*(second(legs,self.probs)-p*p)
            for other,m in ps[:i]:var+=2*n*m*(intersection(legs,other,self.probs)-p*probability(other,self.probs))
        assert abs(self.used['total',0]-sum(f['collateral'] for f in self.fills))<1e-6
        assert self.peak<=10000+1e-6
        assert all(v<=1000+1e-6 for k,v in self.maxrisk.items() if k.startswith('fixture:'))
        assert all(v<=500+1e-6 for k,v in self.maxrisk.items() if k.startswith(('contract:','combo:')))
        assert all(f['incremental_variance_upper']<=1e-8 for f in self.fills if f['discounted'])
        return {'name':self.name,'discount_edge_cents':self.discount_edge*100,'trigger':self.trigger,'delay_seconds':self.delay,'counts':dict(self.counts),'filled_quotes':len({f['quote_key'] for f in self.fills}),
            'trades':len({f['trade_id'] for f in self.fills}),'markets':len(self.positions),
            'contracts':sum(f['quantity'] for f in self.fills),'collateral':sum(f['collateral'] for f in self.fills),
            'model_edge':sum(f['model_edge'] for f in self.fills),'peak_pending_held':self.peak,
            'discount_fills':sum(f['discounted'] for f in self.fills),
            'discount_model_edge':sum(f['model_edge'] for f in self.fills if f['discounted']),
            'ending_variance_upper_independent_fixtures':var,'ending_sd_upper_independent_fixtures':math.sqrt(max(0,var)),
            'ending_fixture_usage':{k:self.risk(k,self.held) for k in self.maxrisk if k.startswith('fixture:')}}

def run():
    qs,trades=load()
    checks={(r['quote_key'],r['trade_id']):r for r in json.loads((OUT/'inventory_fill_checks.json').read_text())}
    scenarios=[Scenario('gross_0.30c',False,False),Scenario('combined_signed_0.30c',True,False),
        Scenario('inventory_0.05c_independent_fixture_gate',True,True),Scenario('inventory_0.05c_frechet_gate',True,True,True),
        Scenario('payoff_bound_0.30c',True,False,payoff_credit=True),
        Scenario('payoff_bound_inventory_0.05c',True,True,payoff_credit=True),
        Scenario('payoff_bound_inventory_0.10c',True,True,payoff_credit=True,discount_edge=.001),
        Scenario('payoff_bound_inventory_0.20c',True,True,payoff_credit=True,discount_edge=.002),
        Scenario('payoff_bound_inventory_0.05c_trigger75',True,True,payoff_credit=True,trigger=.75),
        Scenario('payoff_bound_inventory_0.05c_delay250ms',True,True,payoff_credit=True,delay=.25),
        Scenario('payoff_bound_inventory_0.05c_delay1s',True,True,payoff_credit=True,delay=1.)]
    for s in scenarios:s.fill_checks=checks
    events=sorted([(q['at'],0,i) for i,q in enumerate(qs)]+[(t['at'],1,i) for i,t in enumerate(trades)])
    for i,(at,kind,index) in enumerate(events):
        for s in scenarios:
            if kind==0:s.quote(qs[index])
            else:s.trade(trades[index])
        if i%25000==0:print('events',i,'of',len(events),flush=True)
    summaries=[]
    for s in scenarios:
        summaries.append(s.summary());(OUT/(s.name+'_fills.json')).write_text(json.dumps(s.fills)+'\n')
    result={'scenarios':summaries,'candidate_count':len(qs),'public_yes_prints':len(trades),
        'limitations':['PUBLIC-PRINT SCENARIOS, NOT RFQ ACCEPTANCE OR SETTLEMENT PNL.',
            'Re-admits original pending-risk rejects and reallocates tape volume causally; retains original creator eligibility and quote-time gates.',
            'All matched pairs require causal fill-time source eligibility, tail/guard, charge hurdle, <=1c fair move and no tighter risk regime. No intermediate cancellation or changed creator-state replay.',
            'Full requested shadow size must fit ticket cap; target-cost ceiling excludes customer fees and is not exchange sizing verification.',
            'Variance uses latest candidate-observed canonical leg probabilities; not fitted realized covariance. Same-fixture different contracts use pairwise Frechet upper intersections.',
            'Nominal variance assumes independent fixtures; robust gate keeps nominal means but applies Frechet intersection bounds without cross-fixture independence.',
            'Discounts only exact full-game moneyline combinations, against filled inventory; other families remain included at standard charge and gross risk.',
            'Gross cash never nets. Signed fixture/contract cap equals unsigned pool plus max(opposing signed pools).',
            'Payoff-bound variants additionally subtract ONLY FILLED opposing premium from each moneyline conditional loss side; unfilled hedges grant no credit.',
            'Trigger is held fixture risk >=90% of cap; require reduced absolute conditional exposure and nonpositive variance-delta bound at quote AND public match.',
            'No new live configuration or pricing change.']}
    (OUT/'inventory_summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':run()
