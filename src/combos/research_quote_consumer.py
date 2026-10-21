"""Composable shadow quote policy and capacity accounting; never submits quotes."""
from copy import deepcopy
import json,math
from .event_store import rfq_payload
from .research_rfq_quote import solve_quote
from .research_capacity import CapacityReplay
from .payoff_risk import canonical_leg_risk
from .dynamic_edge import charge as dynamic_edge_charge


class ResearchQuoteConsumer:
    def __init__(self, pricing, runtime, policy):
        if runtime.get('mode')!='shadow':raise ValueError('research quote policy requires shadow')
        self.pricing=pricing;self.runtime=deepcopy(runtime);self.policy=deepcopy(policy);self.creators={}
        for name in ('reserve_fraction','edge_per_combo','native_stake_usd_scale'):
            if not math.isfinite(policy[name]):raise ValueError('invalid quote policy')
        if not 0<=policy['reserve_fraction']<=1 or policy['edge_per_combo']<0 or policy['native_stake_usd_scale'] not in (.1,1,10):raise ValueError('unsupported policy value')
        if policy['capacity_mode'] not in ('unfilled_expiry_3s','all_admitted_fill_no_release'):raise ValueError('explicit capacity assumption required')
        if type(policy.get('apply_pricing_risk_multiplier',True)) is not bool:raise ValueError('explicit pricing risk policy required')
        self.risk=CapacityReplay(policy['capital_dollars'],policy['caps'],3 if policy['capacity_mode']=='unfilled_expiry_3s' else None)
        self.maps={m['market_key']:m for m in runtime['mappings']}

    def evaluate(self,event,pricing,at):
        msg=rfq_payload(event);creator=msg.get('creator_id');state=self.creators.get(creator,{'status':'clear','publication_seq':None})
        status=state['status']
        if status=='cooldown' and at>=state['expires_at']:status='watch'
        row={'creator_status':status,'creator_publication_seq':state['publication_seq'],'capacity_mode':self.policy['capacity_mode'],'status':'excluded'}
        try:
            if not creator:raise ValueError('creator_missing')
            if status in ('blocked','cooldown'):raise ValueError('creator_'+status)
            if pricing['status']!='scenario_priced':raise ValueError('pricing_unavailable')
            terms=next((v for k,v in sorted(self.runtime['combo_terms'].items(),key=lambda kv:-len(kv[0])) if msg['market_ticker'].startswith(k)),None)
            if not terms or not terms.get('fee_reference'):raise ValueError('missing_terms')
            if not terms['verified_at']<=at<terms['valid_until']:raise ValueError('terms_not_causal_or_expired')
            s=next(v for v in pricing['scenarios'] if v['assumed_usd_per_native_unit']==self.policy['native_stake_usd_scale'])
            multiplier=1.
            if self.policy.get('apply_pricing_risk_multiplier',True):
                guards=[l.get('pricing_guard') for l in s['legs']]
                if not guards or any(not isinstance(g,dict) for g in guards):raise ValueError('pricing_guard_missing')
                if any(g.get('quote_allowed') is not True for g in guards):raise ValueError('pricing_guard_halt')
                values=[g.get('risk_multiplier') for g in guards]
                if any(type(v) not in (float,int) or not math.isfinite(v) or not 0<v<=1 for v in values):raise ValueError('invalid_pricing_risk_multiplier')
                multiplier=min(values)
            row['pricing_risk_multiplier']=multiplier
            row['pricing_risk_multiplier_applied']=self.policy.get('apply_pricing_risk_multiplier',True)
            edge_charge=dynamic_edge_charge(s,self.policy['dynamic_edge']) if self.policy.get('dynamic_edge') else {'edge_per_combo':self.policy['edge_per_combo'],'model':'fixed_policy'}
            row['edge_charge']=edge_charge
            quote=solve_quote(s['independent_combo_point'],s['independent_marginal_upper'],self.policy['reserve_fraction'],edge_charge['edge_per_combo'],
                contracts=msg.get('contracts_fp'),target_cost=msg.get('target_cost_dollars'),rate=terms['maker_fee_rate'],ranges=terms['price_ranges'])
            legs=[canonical_leg_risk(self.maps[l['market_key']],l['side'],'sell',quote['quantity_bound']) for l in s['legs']]
            buckets={'contract':sorted({l['key'] for l in legs}),'combo':[msg['market_ticker']],'fixture':sorted({self.maps[l['market_key']]['fixture_key'] for l in s['legs']})}
            admission=self.risk.admit(msg['id'],at,quote['fragmentation_cash_bound'],buckets,risk_multiplier=multiplier)
            row.update(status='reserved_scenario' if admission['admitted'] else 'risk_rejected',quote=quote,admission=admission,buckets=buckets,leg_risks=legs,
                       maker_fee_rate=terms['maker_fee_rate'],fee_reference=terms['fee_reference'],grid_validation=terms.get('grid_validation'))
        except (ValueError,StopIteration) as exc:row['reason']=str(exc) or 'scenario_missing'
        return json.loads(json.dumps(row,default=str))

    def consume(self,event,evaluation_at=None,price_rfqs=True):
        if event['kind']=='creator_policy':
            p=event['payload'];self.creators[p['creator_id']]={**p['state'],'publication_seq':event['seq']}
        result=self.pricing.consume(event,evaluation_at=evaluation_at,price_rfqs=price_rfqs)
        if result is not None:
            result={**result,'research_policy':self.evaluate(event,result,event['received_at'] if evaluation_at is None else evaluation_at)}
        return result

    def restore_record(self,event,record):
        pricing=record['pricing'];prior=pricing.get('research_policy')
        if prior is not None:
            rebuilt=self.evaluate(event,pricing,record['evaluation_at'])
            if rebuilt!=prior:raise ValueError('research reservation reconstruction differs')
