"""Continuous, replayable NO-side shadow quotes; no exchange mutation path."""
from dataclasses import asdict
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import hashlib
import json
import math
import time
from .creator_service import creator_state, creator_policy_gate
from .event_store import encode, rfq_payload
from .observations import Observation, VENUES
from .pricing import short_yes_economics, fee_per_share
from .rfq_scope import validate_scope, check_legs
from .risk import RiskLedger
from .deployment_risk import DeploymentCappedRiskLedger
from .weighted_fair import WeightPolicy
from .pricing_service import PricingService
from .payoff_risk import canonical_leg_risk
from .quote_reference import reference_from_config
from . import inventory_fitting


def quote_price(upper, edge, rate, ranges):
    """Lowest valid YES ask meeting the per-share reserve before fee rounding."""
    candidates=[]
    for grid in ranges:
        start,end,step = (Decimal(str(grid[k])) for k in ('start','end','step'))
        if not all(x.is_finite() for x in (start,end,step)) or not 0 <= start < end <= 1 or step <= 0:
            raise ValueError('invalid price grid')
        if start % Decimal('.0001') or step % Decimal('.0001'):
            raise ValueError('price grid exceeds four-decimal quote precision')
        low=max(0,int(((Decimal(str(upper+edge))-start)/step).to_integral_value(rounding=ROUND_CEILING)))
        high=int(((end-start)/step).to_integral_value(rounding=ROUND_CEILING))-1
        found=None
        while low<=high:
            mid=(low+high)//2; price=float(start+mid*step)
            if 0 < price < 1 and price-upper-fee_per_share(price,rate)>=edge:
                found=price;high=mid-1
            else:low=mid+1
        if found is not None:candidates.append(found)
    if not candidates:raise ValueError('no_price_with_required_edge')
    return min(candidates)


class ShadowEngine:
    name='shadow'

    def __init__(self, store, config, weight_policy=None, replay=False, pricing_service=None, quote_policy_audit=None):
        if config.get('mode')!='shadow':raise ValueError('only shadow mode is implemented')
        self.store=store;self.db=store.db;self.config=config;self.replay=replay
        inventory_fitting.validate(config)
        # Last-look is deliberately optional for legacy research manifests;
        # the locked shadow configuration supplies this explicitly.  The
        # guard is measured in fair-value cents in the selected YES direction.
        last_look = config.get('last_look') or {}
        self.last_look_max_fair_move_cents = float(last_look.get(
            'max_fair_move_cents', config.get('last_look_max_fair_move_cents', 1.0)))
        if not math.isfinite(self.last_look_max_fair_move_cents) or self.last_look_max_fair_move_cents <= 0:
            raise ValueError('invalid last_look_max_fair_move_cents')
        self.weights=weight_policy or WeightPolicy()
        validate_scope(config)
        for k in ('minimum_net_edge_per_share','quote_lifetime_seconds','maximum_processing_lag_seconds','maximum_combo_book_age_seconds','markout_grace_seconds'):
            if not math.isfinite(config[k]) or config[k]<=0:raise ValueError(f'invalid {k}')
        if not 0<=config['correlation_rho']<=1:raise ValueError('invalid correlation stress')
        if not config['markout_horizons_seconds'] or any(not math.isfinite(h) or h<=0 for h in config['markout_horizons_seconds']):
            raise ValueError('invalid markout horizons')
        if len(set(config['markout_horizons_seconds']))!=len(config['markout_horizons_seconds']):raise ValueError('duplicate markout horizons')
        self.pricer=pricing_service or PricingService(store,config,self.weights)
        if self.pricer.repository is not store or self.pricer.config is not config or self.pricer.weights!=self.weights:
            raise ValueError('pricing service repository/config/weights mismatch')
        self.quote_reference=reference_from_config(config)
        self.maps=self.pricer.registry.by_ticker
        self.quote_policy_audit=quote_policy_audit
        self.shadow_policy_study=None
        if config.get('shadow_policy_study') is not None:
            from .shadow_policy_study import ShadowPolicyStudy
            self.shadow_policy_study=ShadowPolicyStudy(config['shadow_policy_study'],config,store)
        identity={'runtime':config,'weights':asdict(self.weights),'replay':replay,'pricing_components':self.pricer.manifest(),'quote_reference':self.quote_reference.manifest()}
        if quote_policy_audit is not None:
            identity['quote_policy_audit']=quote_policy_audit.manifest()
        if self.shadow_policy_study is not None:
            identity['shadow_policy_study']=self.shadow_policy_study.manifest()
        self.version=hashlib.sha256(encode(identity).encode()).hexdigest()
        store.register(self.name,identity)
        ledger_type = DeploymentCappedRiskLedger if 'maximum_committed_dollars' in config else RiskLedger
        self.risk=ledger_type(store,config)
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS decisions (source_seq INTEGER PRIMARY KEY, rfq_id TEXT, result TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS shadow_seen (rfq_id TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS markouts (decision_seq INTEGER,horizon REAL,due REAL,context TEXT,status TEXT,
                PRIMARY KEY(decision_seq,horizon));
            CREATE INDEX IF NOT EXISTS due_markouts ON markouts(status,due);
            CREATE TABLE IF NOT EXISTS shadow_paper_trades (trade_id TEXT PRIMARY KEY, source_seq INTEGER NOT NULL);
        ''')

    def fair(self, legs, at):
        return self.pricer.price(legs,at)

    def decide(self,event,at):
        compute_started=time.monotonic()
        msg=rfq_payload(event)
        result={'source_seq':event['seq'],'rfq_id':msg.get('id'),'creator_id':msg.get('creator_id'),
                'market_ticker':msg.get('market_ticker'),'received_at':event['received_at'],'decision_at':at,
                'evaluated_at':time.time(),'processing_lag_seconds':max(0,time.time()-event['received_at']),
                'status':'skipped','mode':'shadow','config_version':self.version,'request':msg,
                'capital_available_dollars':self.risk.available()/10000}
        try:
            if not msg.get('id'):raise ValueError('missing_rfq_id')
            if not self.db.execute('INSERT OR IGNORE INTO shadow_seen VALUES(?)',(msg['id'],)).rowcount:
                raise ValueError('duplicate_rfq')
            if not self.replay and result['processing_lag_seconds']>self.config['maximum_processing_lag_seconds']:
                raise ValueError('processing_backlog')
            if not msg.get('creator_id'):raise ValueError('creator_id_missing')
            policy=creator_state(self.store,msg['creator_id'],event['seq'],at)
            result['creator_policy']=policy
            creator_gate=creator_policy_gate(policy, self.config.get('mode','shadow'))
            creator_blocked=not creator_gate['eligible']
            # Shadow mode prices the opportunity even when production policy
            # would blacklist the creator.  This is a counterfactual only:
            # it must never reserve risk or be counted as an eligible quote.
            result['creator_policy_eligible']=not creator_blocked
            result['shadow_counterfactual']=creator_gate['counterfactual']
            legs=msg.get('mve_selected_legs') or []
            result['leg_count'] = len(legs)
            check_legs(legs, self.config)
            f=self.fair(legs,at);result['pricing']=f
            if not f['quote_allowed']:raise ValueError(f.get('block_reason','venue_disagreement_hard'))
            book=self.store.get('combo_books',msg['market_ticker'])
            result['combo_book']=book
            if book and book.get('valid') and 0<=at-book['observed_at']<=self.config['maximum_combo_book_age_seconds']:
                result['combo_midpoint']=(book['yes_bid']+book['yes_ask'])/2
                result['midpoint_minus_fair_cents']=100*(result['combo_midpoint']-f['joint']['point'])
            terms=next((v for prefix,v in sorted(self.config['combo_terms'].items(),key=lambda kv:-len(kv[0])) if msg['market_ticker'].startswith(prefix)),None)
            if not terms or not terms.get('fee_reference'):raise ValueError('combo_fee_or_grid_unconfigured')
            if terms.get('valid_until') is not None and at>=terms['valid_until']:raise ValueError('combo_fee_metadata_expired')
            rate=float(terms['maker_fee_rate'])
            if not math.isfinite(rate) or not 0<=rate<1:raise ValueError('invalid maker fee rate')
            required_edge=self.config['minimum_net_edge_per_share']+f.get('extra_edge_per_share',0.)
            result['required_net_edge_per_share']=required_edge
            reference=self.quote_reference.evaluate(f)
            result['quote_reference']=reference
            price=quote_price(reference['value'],required_edge,rate,terms['price_ranges'])
            fixed=msg.get('contracts_fp');target=msg.get('target_cost_dollars')
            inventory_policy=self.config.get('inventory_fitting') or {}
            if inventory_policy.get('enabled'):
                hedge_edge=inventory_policy['minimum_net_edge_per_share']+f.get('extra_edge_per_share',0.)
                hedge_price=quote_price(reference['value'],hedge_edge,rate,terms['price_ranges'])
                hedge_quantity=float(fixed) if fixed and float(fixed)>0 else (
                    float((Decimal(str(target))/Decimal(str(hedge_price))).to_integral_value(rounding=ROUND_CEILING))
                    if target and math.isfinite(float(target)) and float(target)>0 else 0.)
                if not math.isfinite(hedge_quantity) or hedge_quantity<=0:raise ValueError('invalid_quantity')
                selection=inventory_fitting.evaluate(self,f,hedge_quantity,hedge_price,rate,at)
                result['inventory_fitting']=selection
                if selection['eligible']:
                    price=hedge_price;required_edge=hedge_edge
                    result['required_net_edge_per_share']=required_edge
            if fixed and float(fixed)>0:
                quantity=float(fixed);size_model='rfq_contract_count'
            elif target and math.isfinite(float(target)) and float(target)>0:
                quantity=float((Decimal(str(target))/Decimal(str(price))).to_integral_value(rounding=ROUND_CEILING))
                size_model='shadow_upper_bound_ceiling_target_cost_over_yes_ask_excluding_customer_fee'
            else:raise ValueError('rfq_size_missing')
            if not math.isfinite(quantity) or quantity<=0:raise ValueError('invalid_quantity')
            if inventory_policy.get('enabled') and Decimal(str(quantity))%Decimal('.01'):
                raise ValueError('invalid_quantity_precision')
            requested_quantity = quantity
            ticket_cap = self.config.get('maximum_ticket_gross_liability_dollars')
            if ticket_cap is not None:
                ticket_cap = float(ticket_cap)
                if not math.isfinite(ticket_cap) or ticket_cap <= 0:
                    raise ValueError('invalid_ticket_liability_cap')
                if inventory_policy.get('enabled') and short_yes_economics(quantity,price,reference['value'],rate)['maximum_loss']>ticket_cap:
                    raise ValueError('full_request_exceeds_ticket_liability_cap')
                unit_liability = short_yes_economics(1., price, reference['value'], rate)['maximum_loss']
                if not math.isfinite(unit_liability) or unit_liability <= 0:
                    raise ValueError('invalid_ticket_unit_liability')
                # Kalshi quantities are hundredths of a contract in this
                # shadow path. Round down so the gross liability never
                # exceeds the locked research cap.
                if not inventory_policy.get('enabled'):
                    quantity = math.floor(min(quantity, ticket_cap / unit_liability) * 100 + 1e-9) / 100
                if quantity <= 0:
                    raise ValueError('ticket_liability_cap_below_one_contract')
                result['requested_quantity'] = requested_quantity
                result['ticket_liability_cap_dollars'] = ticket_cap
                result['ticket_size_capped'] = quantity + 1e-12 < requested_quantity
            economics=short_yes_economics(quantity,price,reference['value'],rate)
            result['point_economics']=short_yes_economics(quantity,price,f['joint']['point'],rate)
            result['stressed_economics']=short_yes_economics(quantity,price,f['stressed_upper'],rate)
            result.update(yes_ask=price,no_bid=round(1-price,10),quantity=quantity,size_model=size_model,
                          economics=economics,combo_terms=terms)
            if self.quote_policy_audit is not None:
                try:
                    if size_model!='rfq_contract_count':
                        raise ValueError('target_cost_requires_candidate_dependent_quantity')
                    result['quote_policy_audit']=self.quote_policy_audit.evaluate(
                        decision_id=str(event['seq']),decision_at=at,quantity=quantity,
                        pricing=f,terms=terms,
                        minimum_profit_per_contract=self.config['minimum_net_edge_per_share'])
                except Exception as exc:
                    # A research sidecar cannot change the selected quote,
                    # reservation or cancellation path on an audit failure.
                    result['quote_policy_audit']={'mode':'research_shadow_only','status':'unavailable','reason':str(exc)}
            if economics['expected_edge']/quantity+1e-12<required_edge:
                raise ValueError('rounded_fee_edge_below_floor')
            leg_risks=[canonical_leg_risk(d['mapping'],d['selected_side'],'sell',quantity) for d in f['legs']]
            result['canonical_leg_risk']=leg_risks
            combo_key=hashlib.sha256(encode(sorted((r['key'],r['selected_sign']) for r in leg_risks)).encode()).hexdigest()
            identifier='shadow:'+msg['id']
            context={'quantity':quantity,'yes_ask':price,'legs':legs,'source_seq':event['seq'],'size_model':size_model,
                     'market_ticker':msg['market_ticker'],'published_at':at,
                     'required_net_edge_per_share':required_edge,
                     'inventory_fitting':result.get('inventory_fitting',{'eligible':False}),
                     'quote_reference':reference, 'maker_fee_rate': rate, 'risk_multiplier': f['risk_multiplier'],
                     'canonical_leg_risk':leg_risks,
                     'initial_fair_point': f['joint']['point'],
                     'initial_fair_lower': f['joint']['lower'],
                     'initial_fair_upper': f['joint']['upper'],
                     # Preserve the complete source/fair snapshot once at
                     # quote time. This is the denominator for later
                     # fill-edge and "too tight" attribution.
                     'initial_pricing': f,
                     'last_look_max_fair_move_cents': self.last_look_max_fair_move_cents}
            # Moneyline offsets are deliberately narrow: only exact reviewed
            # full-game binary mappings on distinct fixtures can share the
            # contract/fixture cap. Combo liability and cash remain gross.
            offset_policy = self.config.get('moneyline_offset') or {}
            offset_eligible = bool(offset_policy.get('enabled')) and \
                offset_policy.get('eligible_scope') == 'exact_full_game_moneyline_distinct_fixture_team_match' and \
                all(d['mapping'].get('market_type') == 'moneyline' and
                    d['mapping'].get('period', 'full_game') == 'full_game' for d in f['legs']) and \
                len({d['mapping'].get('fixture_key') for d in f['legs']}) == len(f['legs'])
            signed_buckets = {}
            if offset_eligible and offset_policy.get('net_contract_and_fixture_risk_buckets', False):
                signed_buckets = {
                    'contract': [{'key': r['key'], 'side': 1 if r.get('position_sign', r['selected_sign']) > 0 else -1} for r in leg_risks],
                    'fixture': [{'key': d['mapping']['fixture_key'],
                                 'side': 1 if r.get('position_sign', r['selected_sign']) > 0 else -1}
                                for d, r in zip(f['legs'], leg_risks)],
                }
                context['moneyline_offset'] = {'eligible': True, 'signed_buckets': signed_buckets,
                                               'cash_collateral_credit': False}
            else:
                context['moneyline_offset'] = {'eligible': False, 'signed_buckets': {},
                                               'cash_collateral_credit': False}
            result['moneyline_offset_eligible'] = offset_eligible
            expires_at = at+self.config['quote_lifetime_seconds']
            cutoff = max(self.config.get('pregame_cutoff_seconds', 60.),
                         self.weights.pregame_cutoff_seconds if self.weights.delayed_pinnacle else 0.)
            expires_at = min(expires_at, *(d['mapping']['start_at']-cutoff for d in f['legs']))
            if creator_blocked:
                result['risk']={'allowed':False,'reason':'creator_'+policy['status'],
                                'shadow_counterfactual':True}
            else:
                result['risk']=self.risk.reserve(identifier,msg['creator_id'],economics['maximum_loss'],
                    {'contract':f['contracts'],'combo':[combo_key],'fixture':f['fixtures']},
                    expires_at,context,limit_multiplier=f['risk_multiplier'],signed_buckets=signed_buckets)
                if not result['risk']['allowed']:raise ValueError(result['risk']['reason'])
            # Markouts are fill-eligible research obligations, so create them
            # only after the reservation has been accepted.  Previously a
            # risk-rejected candidate left pending rows and advanced the
            # scheduler, contaminating fill-conditional denominators.
            markout={'creator_id':msg['creator_id'],'legs':legs,'initial_fair':f['joint']['point'],
                     'yes_ask':price,'quantity':quantity,'maker_fee_rate':rate,
                     'decision_at':at,'source_seq':event['seq']}
            for horizon in self.config['markout_horizons_seconds']:
                self.db.execute('INSERT INTO markouts VALUES(?,?,?,?,?)',(event['seq'],horizon,at+horizon,encode(markout),'pending'))
            # New work becomes due later in this same transaction.
            due=at+min(self.config['markout_horizons_seconds'])
            old_due=getattr(self,'_next_markout',None)
            self._next_markout=due if old_due is None else min(old_due,due)
            old_expiry=getattr(self,'_next_expiry',None)
            if not creator_blocked:
                self._next_expiry=expires_at if old_expiry is None else min(old_expiry,expires_at)
            result.update(status='shadow_quote_blocked' if creator_blocked else 'shadow_quote',
                          reason='creator_'+policy['status'] if creator_blocked else None,
                          reservation_id=None if creator_blocked else identifier,expires_at=expires_at,
                          quote={'yes_bid':'0.0000','no_bid':f'{1-price:.4f}'},fills_assumed=False,
                          would_quote=not creator_blocked)
        except (KeyError,TypeError,ValueError) as exc:
            result['reason']=str(exc)
        if self.shadow_policy_study is not None:
            try:
                # Research runs even if the existing stressed floor has no
                # feasible price. The study cannot mutate baseline decisions.
                result['shadow_policy_study']=self.shadow_policy_study.evaluate_decision(result)
            except Exception as exc:
                result['shadow_policy_study']={'mode':'shadow_research_only','orders_enabled':False,
                    'fills_assumed':False,'selected':None,'status':'unavailable','reason':str(exc)}
        result['decision_compute_seconds']=time.monotonic()-compute_started
        result['decision_completed_at']=time.time()
        if result.get('reservation_id'):
            row=self.db.execute('SELECT context FROM reservations WHERE id=?',(result['reservation_id'],)).fetchone()
            context=json.loads(row['context'])
            context['published_at']=at if self.replay else result['decision_completed_at']
            self.db.execute('UPDATE reservations SET context=? WHERE id=?',(encode(context),result['reservation_id']))
        result['completed_processing_lag_seconds']=max(0., result['decision_completed_at']-event['received_at'])
        output_seq=self.store.append('decision',self.name,result,f'decision:{event["seq"]}',at)
        # Keep the full context once in the compressed event log, not again as
        # uncompressed JSON for every long, out-of-scope RFQ.
        self.db.execute('INSERT INTO decisions VALUES(?,?,?)',(event['seq'],msg.get('id'),encode({
            'status':result['status'],'reason':result.get('reason'),'decision_event_seq':output_seq})))

    def markouts(self,at,source_seq):
        for row in self.db.execute("SELECT * FROM markouts WHERE status='pending' AND due<=? ORDER BY due LIMIT 500",(at,)).fetchall():
            context=json.loads(row['context']);label={'decision_seq':row['decision_seq'],'horizon_seconds':row['horizon'],
                'due_at':row['due'],'observed_at':at,'source_seq':source_seq,'creator_id':context['creator_id'],'kind':'hypothetical_quote_markout'}
            try:
                if at>row['due']+self.config['markout_grace_seconds']:raise ValueError('markout_window_missed')
                f=self.fair(context['legs'],at)
                reference=self.quote_reference.evaluate(f)
                markout_fee=fee_per_share(context['yes_ask'],context['maker_fee_rate'])
                markout_net_edge=context['yes_ask']-reference['value']-markout_fee
                label.update(status='observed',fair=f['joint']['point'],
                    adverse_move_cents=100*(f['joint']['point']-context['initial_fair']),
                    remaining_gross_edge_cents=100*(context['yes_ask']-f['joint']['point']),
                    reference=reference,
                    markout_net_edge_per_share=markout_net_edge,
                    markout_net_edge_dollars=context['quantity']*markout_net_edge,
                    benchmark='same_three_venue_model_not_independent',pricing=f)
            except (KeyError,TypeError,ValueError) as exc:
                if at<row['due']+self.config['markout_grace_seconds']:continue
                label.update(status='unavailable',reason=str(exc))
            self.db.execute('UPDATE markouts SET status=? WHERE decision_seq=? AND horizon=?',(label['status'],row['decision_seq'],row['horizon']))
            self.store.append('markout',self.name,label,f'markout:{row["decision_seq"]}:{row["horizon"]}',at)

    def apply(self,event,at):
        kind=event['kind'];payload=event['payload']
        if kind=='observation':
            o=Observation.from_record(payload)
            key=o.market_key+':'+o.venue
            old=self.store.get('observations',key)
            if old and old['available_at']>o.available_at:raise ValueError('out_of_order_observation')
            self.store.put('observations',key,payload)
        elif kind=='venue_reset':
            for row in self.db.execute("SELECT key,value FROM state WHERE owner='observations'").fetchall():
                value=json.loads(row['value'])
                if value['venue']==payload['venue']:
                    value.update(active=False,available_at=event['received_at'],observed_at=event['received_at'],source_reference=f'event:{event["seq"]}')
                    self.store.put('observations',row['key'],value)
            if payload['venue']=='kalshi':self.db.execute("DELETE FROM state WHERE owner='combo_books'")
        elif kind=='combo_book':self.store.put('combo_books',payload['market_ticker'],payload)
        elif kind=='fixture_status':
            if not payload.get('fixture_key') or payload.get('phase') not in ('pregame','in_play','finished','suspended','unknown'):
                raise ValueError('invalid_fixture_status')
            old = self.store.get('fixture_status', payload['fixture_key'], {})
            # Started is latched: a later delayed pregame message cannot reopen quoting.
            self.store.put('fixture_status', payload['fixture_key'], {**payload,
                'started': old.get('started', False) or payload['phase'] in ('in_play','finished')})
        elif kind=='paper_trade':
            self.match_paper_trade(payload,at,event['seq'])
        elif kind=='simulation_fill' and (self.config.get('inventory_fitting') or {}).get('enabled'):
            self.confirm_paper_fill(payload['reservation_id'],payload.get('quantity'),payload.get('fill_price'),at,event['seq'])
        elif kind=='simulation_fill':
            self.revalidate_quotes(at,event['seq'])
            row=self.db.execute('SELECT * FROM reservations WHERE id=?',(payload['reservation_id'],)).fetchone()
            if row and row['status'] in ('cancelled','expired'):
                self.store.append('simulation_fill_rejected',self.name,{'reservation_id':payload['reservation_id'],
                    'reason':row['status'],'source_seq':event['seq']},f'fill_rejected:{event["seq"]}',at)
                return
            if row and row['status']=='reserved':
                context=json.loads(row['context'])
                # Last-look has just passed. Capture the economics at the
                # confirmation boundary, including the full three-venue
                # components, so a shadow fill can be labeled as too tight or
                # sufficiently compensated without reconstructing history.
                pricing=self.fair(context['legs'],at)
                fill_price=float(payload.get('fill_price',context['yes_ask']))
                fill_quantity=float(payload.get('quantity',context['quantity']))
                reference=self.quote_reference.evaluate(pricing)
                maker_fee=fee_per_share(fill_price,context['maker_fee_rate'])
                fair_move=100*(pricing['joint']['point']-context['initial_fair_point'])
                gross_edge=fill_price-pricing['joint']['point']
                net_edge=fill_price-reference['value']-maker_fee
                self.store.append('simulation_fill_confirmed',self.name,{
                    'reservation_id':payload['reservation_id'],'source_seq':event['seq'],
                    'decision_source_seq':context.get('source_seq'),'confirmed_at':at,
                    'creator_id':row['creator'],'quantity':fill_quantity,'fill_price':fill_price,
                    'initial_fair_point':context['initial_fair_point'],
                    'confirmation_fair_point':pricing['joint']['point'],
                    'fair_move_cents':fair_move,
                    'quote_gross_edge_cents':100*(context['yes_ask']-context['initial_fair_point']),
                    'fill_gross_edge_cents':100*gross_edge,
                    'fill_net_edge_cents':100*net_edge,
                    'fill_net_edge_dollars':fill_quantity*net_edge,
                    'maker_fee_per_share':maker_fee,
                    'reference_kind':reference.get('kind', reference.get('assumption')),
                    'confirmation_reference':reference,
                    'required_net_edge_per_share':self.config['minimum_net_edge_per_share'],
                    'initial_pricing':context.get('initial_pricing'),
                    'confirmation_pricing':pricing,
                    'too_tight_at_confirmation':net_edge+1e-12 < self.config['minimum_net_edge_per_share']
                },f'fill_confirmed:{event["seq"]}',at)
            self.risk.transition(payload['reservation_id'],'simulated_filled',at,event['seq'])
        elif kind=='simulation_settlement':
            self.risk.transition(payload['reservation_id'],'simulated_settled',at,event['seq'],payload['payout_dollars'])
            self.revalidate_quotes(at,event['seq'])
        elif kind=='kalshi' and payload.get('type')=='rfq_deleted':
            identifier='shadow:'+payload['msg']['id']
            row=self.db.execute('SELECT status FROM reservations WHERE id=?',(identifier,)).fetchone()
            if row and row['status']=='reserved':self.risk.transition(identifier,'cancelled',at,event['seq'])
        elif kind=='creator_policy' and payload['state']['status'] in ('blocked','cooldown'):
            for row in self.db.execute("SELECT id FROM reservations WHERE creator=? AND status='reserved'",(payload['creator_id'],)).fetchall():
                self.risk.transition(row['id'],'cancelled',at,event['seq'])
        if kind in ('observation','venue_reset','fixture_status','heartbeat'):
            self.revalidate_quotes(at,event['seq'])
        if rfq_payload(event) is not None:self.decide(event,at)

    def confirm_paper_fill(self, identifier, quantity, price, at, source_seq, trade_id=None):
        """Receipt-time last look; public prints are opportunities, not executions."""
        self.revalidate_quotes(at,source_seq)
        row=self.db.execute('SELECT * FROM reservations WHERE id=?',(identifier,)).fetchone()
        if row is None or row['status']!='reserved' or at>=row['expires_at']:
            raise ValueError('paper_fill_not_active')
        c=json.loads(row['context'])
        quantity=float(c['quantity'] if quantity is None else quantity)
        price=float(c['yes_ask'] if price is None else price)
        if not math.isfinite(quantity) or not 0<quantity<=c['quantity'] or Decimal(str(quantity))%Decimal('.01'):
            raise ValueError('invalid_fill_quantity')
        if not math.isfinite(price) or not c['yes_ask']<=price<1:raise ValueError('invalid_fill_price')
        pricing=self.fair(c['legs'],at);reference=self.quote_reference.evaluate(pricing)
        economics=short_yes_economics(quantity,price,reference['value'],c['maker_fee_rate'])
        discounted=c.get('inventory_fitting',{}).get('eligible',False)
        floor=self.config['inventory_fitting']['minimum_net_edge_per_share'] if discounted else self.config['minimum_net_edge_per_share']
        required=floor+pricing.get('extra_edge_per_share',0.)
        if economics['expected_edge']/quantity+1e-12<required:raise ValueError('paper_fill_edge_below_floor')
        hedge=inventory_fitting.evaluate(self,pricing,quantity,price,c['maker_fee_rate'],at) if discounted else None
        if discounted and not hedge['eligible']:raise ValueError('paper_fill_not_inventory_hedge')
        filled_id=self.risk.fill(identifier,quantity,price,at,source_seq)
        self.store.append('simulation_fill_confirmed',self.name,{
            'reservation_id':filled_id,'parent_reservation':identifier,'source_seq':source_seq,
            'decision_source_seq':c['source_seq'],'confirmed_at':at,'creator_id':row['creator'],
            'quantity':quantity,'fill_price':price,'public_trade_id':trade_id,
            'fill_assumption':'public_tape_price_cross_FIFO_at_our_ask_receipt_time_last_look' if trade_id else 'explicit_simulation',
            'actual_exchange_fill':False,'initial_pricing':c.get('initial_pricing'),
            'confirmation_pricing':pricing,'confirmation_reference':reference,
            'initial_fair_point':c['initial_fair_point'],'confirmation_fair_point':pricing['joint']['point'],
            'fair_move_cents':100*(pricing['joint']['point']-c['initial_fair_point']),
            'quote_gross_edge_cents':100*(c['yes_ask']-c['initial_fair_point']),
            'fill_gross_edge_cents':100*(price-pricing['joint']['point']),
            'maker_fee_rate':c['maker_fee_rate'],'maker_fee_per_share':economics['maker_fee']/quantity,
            'fill_net_edge_cents':100*economics['expected_edge']/quantity,
            'fill_net_edge_dollars':economics['expected_edge'],
            'required_net_edge_per_share':required,'too_tight_at_confirmation':False,
            'inventory_fitting':hedge,'economics':economics,
        },f'fill_confirmed:{source_seq}:{identifier}',at)
        return filled_id

    def match_paper_trade(self, payload, at, source_seq):
        policy=self.config.get('inventory_fitting') or {}
        if not policy.get('enabled') or not policy.get('paper_trade_matching'):return
        trade_id=payload.get('trade_id')
        if not isinstance(trade_id,str) or not trade_id:raise ValueError('paper_trade_id_missing')
        if not self.db.execute('INSERT OR IGNORE INTO shadow_paper_trades VALUES(?,?)',(trade_id,source_seq)).rowcount:return
        result={'trade_id':trade_id,'source_seq':source_seq,'actual_exchange_fill':False,'allocations':[]}
        try:
            side=payload.get('taker_outcome_side') or payload.get('taker_side')
            book_side=payload.get('taker_book_side')
            if side is None:side={'bid':'yes','ask':'no'}.get(book_side)
            if book_side is not None and book_side!={'yes':'bid','no':'ask'}.get(side):
                raise ValueError('paper_trade_direction_conflict')
            if side!='yes' or payload.get('is_block_trade'):raise ValueError('paper_trade_side_or_block_ineligible')
            timestamp=float(payload['ts_ms'])/1000 if payload.get('ts_ms') is not None else float(payload['ts'])
            price=float(payload['yes_price_dollars']);remaining=Decimal(str(payload['count_fp']))
            if not math.isfinite(timestamp) or not 0<=at-timestamp<=self.config['maximum_processing_lag_seconds']:
                raise ValueError('paper_trade_timestamp_ineligible')
            if not math.isfinite(price) or not 0<price<1 or not remaining.is_finite() or remaining<=0 or remaining%Decimal('.01'):
                raise ValueError('paper_trade_price_or_quantity_invalid')
            for row in self.db.execute("SELECT id,context,expires_at FROM reservations WHERE status='reserved' ORDER BY rowid").fetchall():
                c=json.loads(row['context'])
                if c.get('market_ticker')!=payload.get('market_ticker'):continue
                # Seconds-only timestamps use the start of that second, which
                # deliberately rejects ambiguous same-second prepublication prints.
                if not c.get('published_at',math.inf)<=timestamp<row['expires_at'] or price<c['yes_ask']:continue
                quantity=min(remaining,Decimal(str(c['quantity'])))
                try:
                    filled_id=self.confirm_paper_fill(row['id'],float(quantity),c['yes_ask'],at,source_seq,trade_id)
                except (KeyError,TypeError,ValueError) as exc:
                    result.setdefault('rejections',[]).append({'reservation_id':row['id'],'reason':str(exc)})
                    continue
                remaining-=quantity
                result['allocations'].append({'reservation_id':filled_id,'quantity':float(quantity),'yes_ask':c['yes_ask']})
                if remaining==0:break
            result.update(reason='processed',unallocated_quantity=float(remaining),native_trade_at=timestamp,
                          public_yes_price=price,public_quantity=float(payload['count_fp']))
        except (KeyError,TypeError,ValueError) as exc:result['reason']=str(exc)
        self.store.append('paper_trade_match',self.name,result,f'paper_trade_match:{trade_id}',at)

    def revalidate_quotes(self, at, source_seq):
        """Cancel offers on stale data, fair moves, or scope changes.

        This is also called immediately before a simulated fill.  It models
        exchange last-look: the same three-source fair is recomputed at the
        confirmation boundary, and a quote is rejected if fair moved too far
        in either direction since publication.  The signed move is retained
        for post-run analysis even though the guard is symmetric.
        """
        for row in self.db.execute("SELECT id,context FROM reservations WHERE status='reserved'").fetchall():
            context=json.loads(row['context']);pricing=None;reason=None
            try:
                pricing=self.fair(context['legs'],at)
                if not pricing['quote_allowed']:raise ValueError(pricing.get('block_reason','venue_disagreement_hard'))
                if pricing['risk_multiplier']<context.get('risk_multiplier',1.):
                    raise ValueError('risk_regime_tightened')
                initial = context.get('initial_fair_point')
                if initial is None or not math.isfinite(float(initial)):
                    raise ValueError('last_look_initial_fair_missing')
                move_cents = 100*(pricing['joint']['point']-float(initial))
                limit = float(context.get('last_look_max_fair_move_cents', self.last_look_max_fair_move_cents))
                if abs(move_cents) > limit + 1e-12:
                    raise ValueError('last_look_fair_move_exceeded')
                reference=self.quote_reference.evaluate(pricing)
                economics=short_yes_economics(context['quantity'],context['yes_ask'],reference['value'],context['maker_fee_rate'])
                floor=(self.config.get('inventory_fitting') or {}).get('minimum_net_edge_per_share') if context.get('inventory_fitting',{}).get('eligible') else self.config['minimum_net_edge_per_share']
                if economics['expected_edge']/context['quantity']+1e-12<floor+pricing.get('extra_edge_per_share',0.):
                    raise ValueError('reference_move_requires_reprice')
                if context.get('inventory_fitting',{}).get('eligible') and not inventory_fitting.evaluate(
                        self,pricing,context['quantity'],context['yes_ask'],context['maker_fee_rate'],at)['eligible']:
                    raise ValueError('inventory_hedge_no_longer_eligible')
                for bucket in self.db.execute('SELECT bucket FROM exposure WHERE reservation=? UNION SELECT bucket FROM signed_exposure WHERE reservation=?',(row['id'],row['id'])):
                    family=bucket['bucket'].split(':',1)[0]
                    if self.risk.bucket_state(bucket['bucket'])['risk_dollars']>self.config['per_'+family+'_dollars']*pricing['risk_multiplier']+1e-9:
                        raise ValueError('inventory_bucket_limit_exceeded')
            except (KeyError,TypeError,ValueError) as exc:reason=str(exc)
            if reason:
                self.risk.transition(row['id'],'cancelled',at,source_seq)
                context=json.loads(row['context'])
                evidence={'reservation_id':row['id'],'reason':reason,'source_seq':source_seq,'pricing':pricing,
                          'initial_fair_point':context.get('initial_fair_point'),
                          'last_look_max_fair_move_cents':context.get('last_look_max_fair_move_cents',self.last_look_max_fair_move_cents)}
                if pricing is not None and context.get('initial_fair_point') is not None:
                    evidence['fair_move_cents']=100*(pricing['joint']['point']-context['initial_fair_point'])
                self.store.append('quote_invalidated',self.name,evidence,
                    f'quote_invalidated:{row["id"]}',at)

    def step(self,limit=250):
        processed=0
        with self.store.transaction():
            # This snapshot cannot advance while our writer transaction holds
            # SQLite's lock; every RFQ still waits for prior creator evidence.
            creator_cursor=self.store.cursor('creators')
            clock=self.store.get(self.name,'clock',0)
            self._next_expiry=self.db.execute("SELECT MIN(expires_at) FROM reservations WHERE status='reserved'").fetchone()[0]
            self._next_markout=self.db.execute("SELECT MIN(due) FROM markouts WHERE status='pending'").fetchone()[0]
            for event in self.store.read(self.store.cursor(self.name),limit, payload_kinds={
                    'observation','venue_reset','combo_book','fixture_status','simulation_fill','paper_trade',
                    'simulation_settlement','kalshi','creator_policy','rfq','heartbeat'}):
                if rfq_payload(event) is not None and creator_cursor<event['seq']:
                    break  # Await prior evidence; no synchronous per-request RPC.
                at=max(event['received_at'],clock) if self.replay else time.time()
                try:
                    # Every envelope still advances maintenance. These caches
                    # suppress only scans known to have no due rows.
                    if self._next_expiry is not None and at>=self._next_expiry:
                        self.risk.expire(at,event['seq'])
                        self._next_expiry=self.db.execute("SELECT MIN(expires_at) FROM reservations WHERE status='reserved'").fetchone()[0]
                    self.apply(event,at)
                    if event['kind'] in ('observation','heartbeat','rfq','kalshi') and self._next_markout is not None and at>=self._next_markout:
                        self.markouts(at,event['seq'])
                        self._next_markout=self.db.execute("SELECT MIN(due) FROM markouts WHERE status='pending'").fetchone()[0]
                except (KeyError,ValueError,TypeError) as exc:
                    self.store.append('consumer_error',self.name,{'source_seq':event['seq'],'reason':str(exc)},f'shadow_error:{event["seq"]}',at)
                clock=at;last_seq=event['seq'];processed+=1
            if processed:
                self.store.put(self.name,'clock',clock)
                self.store.checkpoint(self.name,last_seq)
        return processed
