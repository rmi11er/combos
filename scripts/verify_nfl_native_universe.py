#!/usr/bin/env python3
"""Independently reconcile native rows, seller cash identities and full curves."""
import argparse,hashlib,itertools,json
from decimal import Decimal
from pathlib import Path
from replay_artifact_io import text_reader
from mlb_dated_universe_report import digest
from nfl_native_universe_report import RATES, MONEY, zero
from combos.fees import kalshi_fill_fee


def canonical(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    s=json.loads((a.out/'summary.json').read_text());complete=json.loads((a.out/'complete.json').read_text())
    for name,entry in complete['artifacts'].items():assert digest(a.out/name)==entry['sha256']
    for path,h in s['input_hashes'].items():assert digest(path)==h
    originals={}
    for record in s['provenance']:
        with text_reader(Path(record['cohort'])/'universe_trades.jsonl.gz') as source:
            for line in source:
                row=json.loads(line)
                if row['trade']['taker_side']!='yes':continue
                identifier=row['trade']['trade_id'];assert identifier not in originals
                originals[identifier]=canonical(row)
    totals={rate:zero() for rate in RATES};n=curve_count=fractional=unknown_schedule=0;last=None
    extra={'trade_at','date','categories','benchmark_basis','base_maker_rate','economics_by_maker_rate'}
    with text_reader(a.out/'seller_ledger.jsonl.zst') as ledger,text_reader(a.out/'full_resolution_curves.jsonl.zst') as curves:
        source=(json.loads(line) for line in ledger)
        for at,group in itertools.groupby(source,key=lambda row:row['trade_at']):
            for row in group:
                identifier=row['trade']['trade_id'];key=(at,identifier)
                assert last is None or key>last;last=key
                assert originals.pop(identifier)==canonical({k:v for k,v in row.items() if k not in extra})
                q=Decimal(row['trade']['count_fp']);price=Decimal(row['trade']['yes_price_dollars']);settlement=Decimal(row['settlement_value_dollars'])
                fractional+=settlement not in (0,1);unknown_schedule+=row['classification']['earliest_scheduled_start'] is None
                if row['classification']['earliest_scheduled_start'] is None:assert row['categories']['phase']=='Unknown schedule'
                for rate in RATES:
                    values=row['economics_by_maker_rate'][rate];exact={k:Decimal(v) for k,v in values['exact_decimal'].items()}
                    fee=kalshi_fill_fee(q,1-price,rate)['net_fee']
                    assert exact['known_net_pnl']==q*price-q*settlement-fee
                    assert exact['maker_fees']==fee
                    assert exact['yes_premium']==q*price and exact['payout_notional']==q
                    assert exact['cumulative_no_cash']==q-q*price+fee
                    assert values['known_prints']==1 and values['unknown_prints']==0
                    for k in MONEY:totals[rate][k]+=exact[k]
                    totals[rate]['prints']+=1;totals[rate]['known_prints']+=1
                n+=1
            curve=json.loads(next(curves));assert curve['at']==at;curve_count+=1
            for rate in RATES:
                observed=curve if rate=='0.035' else curve['fee_sensitivity'][rate]
                for k in MONEY:assert Decimal(observed['exact_decimal'][k])==totals[rate][k]
                assert observed['prints']==totals[rate]['prints']
        assert curves.read()==''
    assert not originals
    for rate in RATES:
        for k in MONEY:assert Decimal(s['totals'][rate]['exact_decimal'][k])==totals[rate][k]
    assert n==457147 and curve_count==396085 and fractional==27 and unknown_schedule==2140
    result={'status':'passed','exact_native_rows':n,'full_resolution_curve_rows':curve_count,'fee_scenarios':list(RATES),'fractional_settlements_preserved':fractional,'unknown_schedules_separate':unknown_schedule,'input_hashes_verified':len(s['input_hashes']),'compressed_artifacts_verified':len(complete['artifacts']),'checks':['Every retained YES-taker row matches its original native cohort exactly.','Unique ordered trade IDs; no dropped source rows.','Independent Decimal premium, settlement, fee and NO-cash identities for every row and rate.','Every full-resolution cumulative curve point reconciles with ordered ledger.','Final exact sums match summary; native scalar values preserved.']}
    (a.out/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
