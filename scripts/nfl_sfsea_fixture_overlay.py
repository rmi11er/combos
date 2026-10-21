#!/usr/bin/env python3
"""Retrospective, narrowly allowlisted SF–SEA fixture concentration overlay."""
import argparse,gzip,json
from collections import Counter,defaultdict
from decimal import Decimal
from pathlib import Path
from mlb_dated_universe_report import digest
from nfl_native_universe_report import RATES, MONEY, zero, add, finish, economics

OLD='26JAN18SFSEA'
CANONICAL='26JAN17SFSEA'
ALLOWED={OLD,CANONICAL}


def semantic_membership(tokens):
    return {CANONICAL if t==OLD else t for t in tokens}


def partition(tokens):
    hits=set(tokens)&ALLOWED
    return 'both' if len(hits)==2 else 'Jan17_only' if CANONICAL in hits else 'Jan18_only' if OLD in hits else None


def main():
    p=argparse.ArgumentParser();p.add_argument('--benchmark',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    summary=json.loads((a.benchmark/'summary.json').read_text())
    schedule=Path('config/nfl_playoffs_history_2026.json');review=Path('runs/nfl_playoffs_history_20260907/exchange_review.json')
    schedule_data=json.loads(schedule.read_text());fixture=[f for f in schedule_data['fixtures'] if f['away_code']=='SF' and f['home_code']=='SEA']
    assert len(fixture)==1 and fixture[0]['round']=='divisional'
    evidence={'schedule':{'path':str(schedule),'sha256':digest(schedule),'fixture':fixture[0]},'exchange_review':{'path':str(review),'sha256':digest(review)},'native_examples':[],'native_family_membership':{},'native_combo_counts':{}}
    families=defaultdict(set);counts=Counter();seen=set()
    # Only the completed Jan12 retained market dictionary is needed as identity evidence.
    metadata=Path(summary['provenance'][-1]['cohort'])/'combo_markets.json.gz'
    with gzip.open(metadata,'rt') as handle:markets=json.load(handle)
    evidence['native_metadata']={'path':str(metadata),'sha256':digest(metadata)}
    for ticker,market in markets.items():
        legs=market.get('mve_selected_legs',[]);tokens={l['market_ticker'].split('-')[1] for l in legs};hit=partition(tokens)
        if hit is None:continue
        counts[hit]+=1
        for leg in legs:
            parts=leg['market_ticker'].split('-')
            if parts[1] in ALLOWED:families[parts[1]].add(parts[0])
        single=str(market.get('mve_collection_ticker','')).startswith('KXMVENFLSINGLEGAME-')
        if hit=='both' and single:
            counts['both_inside_native_single_game_collection']+=1
            if len(evidence['native_examples'])<3:
                evidence['native_examples'].append({k:market.get(k) for k in ('ticker','created_time','updated_time','title','mve_collection_ticker','event_ticker','mve_selected_legs','close_time','settlement_ts')})
    assert counts['both_inside_native_single_game_collection']>0
    evidence['native_family_membership']={k:sorted(v) for k,v in families.items()};evidence['native_combo_counts']=dict(counts)
    evidence['claim_limit']='Retrospective fixture identity only. Retained metadata updated after the study does not certify knowledge or market mapping at trade time, and does not establish payoff equivalence between different leg contracts.'
    groups={key:{r:zero() for r in RATES} for key in ('Jan17_only','Jan18_only','both','union')};diagnostics=Counter();sources={};reclassified={r:zero() for r in RATES}
    for record in summary['provenance']:
        path=Path(record['cohort'])/'universe_trades.jsonl.gz';sources[str(path)]=digest(path);assert summary['input_hashes'][str(path)]==sources[str(path)]
        with gzip.open(path,'rt') as handle:
            for line in handle:
                row=json.loads(line)
                if row['trade']['taker_side']!='yes':continue
                tokens=row['classification']['fixture_tokens'];hit=partition(tokens)
                if hit is None:continue
                identifier=row['trade']['trade_id'];assert identifier not in seen;seen.add(identifier)
                diagnostics['affected_unique_prints']+=1
                if row['classification']['earliest_scheduled_start'] is None:diagnostics['baseline_unknown_schedule_preserved']+=1
                was_distinct=row['classification']['distinct_fixtures'];now_distinct=len(semantic_membership(tokens))==len(tokens)
                if was_distinct and not now_distinct:diagnostics['native_distinct_to_semantic_same_game']+=1
                for rate in RATES:
                    econ=economics(row,rate);add(groups[hit][rate],econ);add(groups['union'][rate],econ)
                    if was_distinct and not now_distinct:add(reclassified[rate],econ)
    semantic={f:dict(v) for f,v in summary['fixtures'].items() if f not in ALLOWED}
    semantic[CANONICAL]={r:{**finish(v),'known_pnl_after_excluding_fixture':float(Decimal(summary['totals'][r]['exact_decimal']['known_net_pnl'])-v['known_net_pnl'])} for r,v in groups['union'].items()}
    for rate in RATES:
        for key in groups['union'][rate]:assert groups['union'][rate][key]==sum((groups[g][rate][key] for g in ('Jan17_only','Jan18_only','both')),0)
        for token,first in ((CANONICAL,'Jan17_only'),(OLD,'Jan18_only')):
            assert groups[first][rate]['prints']+groups['both'][rate]['prints']==summary['fixtures'][token][rate]['prints']
            assert groups[first][rate]['known_net_pnl']+groups['both'][rate]['known_net_pnl']==Decimal(summary['fixtures'][token][rate]['exact_decimal']['known_net_pnl'])
    structures={}
    for label,rates in summary['cuts']['structure'].items():
        structures[label]={}
        for rate,base in rates.items():
            updated={**{k:base[k] for k in ('prints','known_prints','unknown_prints')},**{k:Decimal(base['exact_decimal'][k]) for k in MONEY}}
            sign=-1 if label=='Distinct fixtures' else 1
            for key in updated:updated[key]+=sign*reclassified[rate][key]
            structures[label][rate]=finish(updated)
    result={'schema_version':1,'semantic_structure_cuts':structures,'distinct_to_same_game_reclassified':{r:finish(v) for r,v in reclassified.items()},'baseline':str(a.benchmark),'baseline_summary_sha256':digest(a.benchmark/'summary.json'),'source_hashes':sources,'script_sha256':digest(Path(__file__)),'allowlist':{OLD:CANONICAL},'evidence':evidence,'diagnostics':dict(diagnostics),'mutually_exclusive_alias_partition':{k:{r:finish(v) for r,v in rates.items()} for k,rates in groups.items()},'semantic_fixture_contributions':semantic,'native_fixture_token_count':len(summary['fixtures']),'semantic_fixture_count':len(semantic),'baseline_total_pnl_unchanged':summary['totals'],'interpretation':['Alias partition Jan17-only/Jan18-only/both is additive and its union counts each affected trade once.','Semantic fixture contributions/exclusions remain any-leg membership and overlap across different games; never add them as portfolio PnL.','Baseline trades, fees, settlements, curves, pricing eligibility and unknown-schedule labels are unchanged.','Schedule cutoff repair or historical market mapping would require a separate as-of review; this is only retrospective concentration.']}
    (a.out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'diagnostics':result['diagnostics'],'union_base':finish(groups['union']['0.035']),'partition_counts':{g:groups[g]['0.035']['prints'] for g in groups},'evidence_counts':dict(counts)},indent=2))
if __name__=='__main__':main()
