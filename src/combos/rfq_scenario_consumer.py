"""Stateful three-source research scenarios; no live pricing authorization.

Payoff exceptions, tie probability, stake conversion and independence are explicit
sensitivity assumptions inherited from the audited research replay.
"""
from copy import deepcopy
import math
from .event_store import rfq_payload
from .verified_book_state import VerifiedBookState
from .rfq_scope import check_legs,check_mappings
from .pinnacle_matching import bind_selectors
from .pinnacle_feed import fixture_index,same_native_market_identity
from .payoff_enumeration import review
from .snapshot_age import delivery_observation_time
from .observations import Observation
from .pricing import Interval,pinnacle_fair
from .weighted_fair import WeightPolicy,weighted_fair


class RFQScenarioConsumer:
    def __init__(self, runtime, catalog, policy):
        if runtime.get('mode')!='shadow':raise ValueError('research consumer requires shadow mode')
        if type(runtime.get('record_venue_components',False)) is not bool:raise ValueError('explicit venue-component logging flag required')
        self.runtime=deepcopy(runtime);self.catalog=deepcopy(catalog);self.policy=policy
        self.mappings={m['kalshi_ticker']:m for m in self.runtime['mappings']}
        self.pm=VerifiedBookState();self.kalshi={};self.pin=None;self.reviews={}

    def consume(self, event, evaluation_at=None, price_rfqs=True):
        seq=event['seq'];at=event['received_at'];r=event['payload'];kind=event['kind'];self.pm.consume(event)
        if kind=='venue_reset' and event['source']=='kalshi':self.kalshi.clear()
        if kind=='venue_reset' and event['source']=='pinnacle':self.pin=None
        if kind=='observation' and r.get('venue')=='kalshi':self.kalshi[r['market_key']]=r
        if kind=='external_raw' and event['source']=='pinnacle':
            fixtures=fixture_index(r['payload']);candidate=deepcopy(self.runtime['mappings'])
            bind_selectors(candidate,list(fixtures.values()),self.catalog)
            self.mappings={m['kalshi_ticker']:m for m in candidate}
            observed,_=delivery_observation_time(r,r['retrieved_at'],30,self.runtime['pinnacle_freshness_policy'])
            self.pin={'fixtures':fixtures,'observed':observed,'available':max(at,r['retrieved_at']),'seq':seq}
        msg=rfq_payload(event)
        if msg is None or not price_rfqs:return None
        if evaluation_at is not None:
            if not math.isfinite(evaluation_at) or evaluation_at<at:raise ValueError('invalid decision time')
            at=evaluation_at
        return self.revalue(msg,at,seq)

    def revalue(self,msg,at,source_seq):
        """Price an existing RFQ against current state without consuming a new event."""
        if not math.isfinite(at):raise ValueError('invalid valuation time')
        seq=source_seq
        result={'source_seq':seq,'rfq_id':msg['id'],'at':at,'market_ticker':msg.get('market_ticker'),
            'requested_contracts':msg.get('contracts_fp'),'target_cost_dollars':msg.get('target_cost_dollars')}
        try:
            legs=msg.get('mve_selected_legs') or [];check_legs(legs,self.runtime)
            selected=[self.mappings.get(leg['market_ticker']) for leg in legs];check_mappings(legs,selected,self.runtime)
            if self.pin is None or self.pin['available']>at:raise ValueError('pinnacle_not_yet_available')
            inputs=[]
            for leg,mapping in zip(legs,selected):
                key=mapping['market_key'];self.policy.check_pregame(mapping['start_at'],at,'pregame')
                k=self.kalshi.get(key);pair=self.pm.pair(key,at);p=pair['candidate']
                if not k or not p:raise ValueError('exchange_candidate_coverage_missing')
                spec=mapping.get('pinnacle')
                if not spec:raise ValueError('exact_pinnacle_selector_missing')
                fixture=self.pin['fixtures'][spec['fixture_id']];book=fixture['bookmakerOdds']['pinnacle+30'];market=book['markets'][spec['market_id']]
                identity=(key,spec['selector_reference'])
                if identity not in self.reviews:self.reviews[identity]=review(mapping,fixture)
                if self.reviews[identity]['status'] not in ('completed_period_binary_verified','void_basis_required'):raise ValueError('conditional_payoff_unverified')
                if fixture['statusId']!=0 or book['bookmakerIsActive'] is not True or book['suspended'] is not False or market['marketActive'] is not True:raise ValueError('pinnacle_inactive')
                if not same_native_market_identity(spec['bookmaker_market_id'],market['bookmakerMarketId'],fixture,book,spec):raise ValueError('pinnacle_identity_changed')
                odds=[];limits=[]
                for side in ('yes','no'):
                    selector=spec[side];v=market['outcomes'][selector['outcome_id']]['players']['0']
                    if v['active'] is not True or v['bookmakerOutcomeId']!=selector['bookmaker_outcome_id']:raise ValueError('pinnacle_outcome_inactive_or_changed')
                    odds.append(float(v['price']));limits.append(float(v['limit']))
                inputs.append((leg,mapping,Observation.from_record(k),Observation.from_record(p),odds,limits,bool(pair['baseline'])))
            scenarios=[]
            for conversion in (.1,1.,10.):
                values=[];uppers=[];details=[]
                for leg,mapping,k,p,odds,limits,baseline in inputs:
                    interval=pinnacle_fair(*odds)
                    tie=(self.policy.full_game_tie_probability
                         if mapping['market_type']=='moneyline' and mapping.get('period','full_game')=='full_game'
                         else 0)
                    point=(1-tie)*interval.point+.5*tie
                    lower=.995*((1-tie)*interval.lower+.5*tie)
                    upper=.995*((1-tie)*interval.upper+.5*tie)+.005
                    observation=Observation(mapping['market_key'],'pinnacle',self.pin['observed'],self.pin['available'],True,
                        Interval(lower,point,upper),limits[1]*odds[1]*conversion,limits[0]*odds[0]*conversion,
                        'captured_event:'+str(self.pin['seq']),mapping['mapping_reference'],None)
                    fair=weighted_fair([k,p,observation],at,'pregame',self.policy)
                    if not fair['guard']['quote_allowed']:raise ValueError('scenario_interval_disagreement_halt')
                    f=fair['fair'];values.append(f['point'] if leg['side']=='yes' else 1-f['point'])
                    uppers.append(f['upper'] if leg['side']=='yes' else 1-f['lower'])
                    details.append({'market_key':mapping['market_key'],'side':leg['side'],'family':mapping.get('period','full_game')+':'+mapping['market_type'],
                        'selected_point':values[-1],'selected_upper':uppers[-1],
                        'pricing_guard':deepcopy(fair['guard']),
                        'weights':{v:d['weight'] for v,d in fair['venues'].items()},'baseline_pm_fresh':baseline,
                        'exchange_source_references':[k.source_reference,p.source_reference],'pinnacle_seq':self.pin['seq']})
                    if self.runtime.get('record_venue_components',False):
                        details[-1]['venue_components']={o.venue:{
                            'selected_point':o.interval.point if leg['side']=='yes' else 1-o.interval.point,
                            **deepcopy(fair['venues'][o.venue])} for o in (k,p,observation)}
                scenarios.append({'assumed_usd_per_native_unit':conversion,'independent_combo_point':math.prod(values),
                    'independent_marginal_upper':math.prod(uppers),'legs':details})
            result.update(status='scenario_priced',nlegs=len(legs),scenarios=scenarios)
        except (ValueError,KeyError,TypeError) as exc:result.update(status='excluded',reason=str(exc))
        return result
