"""Price geometry only: does not activate the gated consensus pricing model."""
from combos.weighted_fair import capped_weights
import math


def screen_leg(leg, policy):
    sources = leg['venue_components']
    k, pm, pin = (sources[v]['selected_point'] for v in ('kalshi','polymarket','pinnacle'))
    weights = capped_weights({v:sources[v]['score'] for v in ('polymarket','pinnacle')},
                             policy['maximum_anchor_venue_weight'])
    anchor = sum(weights[v]*sources[v]['selected_point'] for v in weights)
    gap = 100*abs(pm-pin)
    displacement = 100*(k-anchor)
    agrees = gap < policy['anchor_agreement_cents']
    same_side = (k-pm)*(k-pin)>0
    in_range = policy['minimum_kalshi_disagreement_cents'] <= abs(displacement) <= policy['maximum_kalshi_disagreement_cents']
    return {'market_key':leg['market_key'],'side':leg['side'],
            'baseline_selected_point':leg['selected_point'],'anchor_selected_point':anchor,
            'anchor_gap_cents':gap,'kalshi_minus_anchor_cents':displacement,
            'anchor_weights':weights,'anchor_agrees':agrees,
            'kalshi_same_side_of_both':same_side,'displacement_in_range':in_range,
            'price_screen_passes':agrees and same_side and in_range,
            'consensus_model_activated':False}


def combo_lean_sensitivity(legs, fraction):
    """Fixed-fraction sensitivity, not the gated candidate's activation strength."""
    if not math.isfinite(fraction) or not 0<=fraction<=1:
        raise ValueError('invalid lean fraction')
    base=math.prod(l['baseline_selected_point'] for l in legs)
    alternative=math.prod(l['baseline_selected_point']+fraction*(l['anchor_selected_point']-l['baseline_selected_point'])
                          if l['price_screen_passes'] else l['baseline_selected_point'] for l in legs)
    return {'lean_fraction':fraction,'baseline_combo_point':base,
            'alternative_combo_point':alternative,'fair_change_cents':100*(alternative-base),
            'quotes_or_fills_simulated':False}
