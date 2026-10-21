"""Diagnose snapshot delivery separately from quote changes; no trading permission."""
from collections import Counter
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
import hashlib
import json
import math
from .pinnacle_feed import fixture_index, timestamp


def outcomes(envelope, bookmaker):
    result={}
    for fid,f in fixture_index(envelope['payload']).items():
        book=f.get('bookmakerOdds',{}).get(bookmaker)
        if book is None:continue
        for mid,m in book.get('markets',{}).items():
            for oid,o in m.get('outcomes',{}).items():
                for pid,v in o.get('players',{}).items():
                    key=(fid,str(mid),str(oid),str(pid))
                    result[key]={**v,'market_active':m.get('marketActive'),
                        'book_active':book.get('bookmakerIsActive'),'suspended':book.get('suspended'),
                        'status_id':f.get('statusId'),'bookmaker_market_id':m.get('bookmakerMarketId')}
    return result


@dataclass
class FreshnessAudit:
    bookmaker: str='pinnacle+30'
    previous: dict=field(default_factory=dict)
    samples: list=field(default_factory=list)
    latest_change_received_at: float | None=None
    latest_membership_change_received_at: float | None=None

    def add(self,envelope):
        at=envelope['retrieved_at']; started=envelope.get('request_started_at',at)
        if not all(math.isfinite(t) for t in (at,started)) or started>at:
            raise ValueError('invalid_snapshot_chronology')
        if self.samples and at<=self.samples[-1]['received_at']:
            raise ValueError('snapshot_receipt_did_not_advance')
        current=outcomes(envelope,self.bookmaker);counts=Counter();change_ages=[];lags=[]
        examples=[];issues=[]
        for key,v in current.items():
            counts['outcomes']+=1
            counts['active_outcomes']+=bool(v.get('active') and v['market_active'] and v['book_active'] and not v['suspended'])
            old=self.previous.get(key)
            economic=('price','limit','active','market_active','book_active','suspended','status_id','bookmaker_market_id','bookmakerOutcomeId')
            changes=[k for k in economic if old and old.get(k)!=v.get(k)]
            if changes:
                counts['changed_outcomes']+=1
                for k in changes:counts[k+'_changes']+=1
                if len(examples)<10:examples.append({'key':list(key),'changes':{k:[old.get(k),v.get(k)] for k in changes}})
            elif old:counts['unchanged_outcomes']+=1
            native=v.get('bookmakerChangedAt');published=v.get('changedAt')
            try:
                if native:
                    n=timestamp(native);change_ages.append(at-n)
                    if n>at+.25:issues.append('future_bookmaker_change')
                    if old and old.get('bookmakerChangedAt') and n<timestamp(old['bookmakerChangedAt']):
                        counts['native_timestamp_regressions']+=1
                if published:
                    p=timestamp(published)
                    if p>at+.25:issues.append('future_vendor_change')
                    if native:lags.append(p-n)
                    if old and old.get('changedAt') and p<timestamp(old['changedAt']):counts['vendor_timestamp_regressions']+=1
                if old and (native!=old.get('bookmakerChangedAt') or published!=old.get('changedAt')):
                    counts['timestamp_changes']+=1
                    if not changes:counts['timestamp_only_changes']+=1
            except (ValueError,TypeError):issues.append('invalid_change_timestamp')
        if self.previous:
            counts['added_outcomes']=len(current.keys()-self.previous.keys())
            counts['removed_outcomes']=len(self.previous.keys()-current.keys())
            counts['removed_active_outcomes']=sum(bool(self.previous[k].get('active') and self.previous[k]['market_active']
                and self.previous[k]['book_active'] and not self.previous[k]['suspended']) for k in self.previous.keys()-current.keys())
        if counts['added_outcomes'] or counts['removed_outcomes']:
            self.latest_membership_change_received_at=at
        if counts['changed_outcomes']:
            self.latest_change_received_at=at
        headers={k.lower():v for k,v in envelope.get('response_headers',{}).items()}
        cache_age=None;server_offset=None
        try:
            if 'age' in headers:
                cache_age=float(headers['age'])
                if not math.isfinite(cache_age) or cache_age<0:raise ValueError()
            if 'date' in headers:server_offset=at-parsedate_to_datetime(headers['date']).timestamp()
        except (TypeError,ValueError,OverflowError):issues.append('invalid_http_cache_or_date_header')
        if not current:issues.append('no_requested_bookmaker_outcomes')
        record={'received_at':at,'request_started_at':started,'request_elapsed_seconds':at-started,
            'seconds_since_previous_poll':at-self.samples[-1]['received_at'] if self.samples else None,
            'fixtures':len(fixture_index(envelope['payload'])),'counts':dict(counts),
            'payload_sha256':hashlib.sha256(json.dumps(envelope['payload'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            'quote_change_age_seconds':distribution(change_ages),'reported_change_publication_lag_seconds':distribution(lags),
            'http_cache_age_seconds':cache_age,'receipt_minus_http_date_seconds':server_offset,
            'response_headers':envelope.get('response_headers',{}),'issues':sorted(set(issues)),
            'changed_examples':examples}
        self.previous=current;self.samples.append(record)
        return record

    def report(self):
        total=Counter()
        for row in self.samples:
            for key,value in row['counts'].items():
                if key.endswith('_changes') or key in ('changed_outcomes','added_outcomes','removed_outcomes',
                                                        'removed_active_outcomes','native_timestamp_regressions','vendor_timestamp_regressions'):
                    total[key]+=value
        changing=self.latest_change_received_at is not None
        return {'samples':len(self.samples),'duration_seconds':self.samples[-1]['received_at']-self.samples[0]['received_at'] if self.samples else 0,
            'changes_across_samples':dict(total),'latest_economic_change_received_at':self.latest_change_received_at,
            'latest_membership_change_received_at':self.latest_membership_change_received_at,
            'verdict':'evolving_response_observed_upstream_freshness_unproven' if changing else
                'inconclusive_membership_changes_only' if self.latest_membership_change_received_at is not None else 'inconclusive_no_economic_changes_observed',
            'upstream_freshness_validated':False,
            'interpretation':'Successful polling establishes endpoint reachability. Old price-change timestamps and identical snapshots alone establish neither stale nor healthy upstream collection. Changes are evidence of response evolution, not a guaranteed source-to-client delay.',
            'polls':self.samples}


def distribution(values):
    if not values:return None
    v=sorted(values);n=len(v)
    return {'n':n,'minimum':v[0],'median':(v[(n-1)//2]+v[n//2])/2,'p95':v[int((n-1)*.95)],'maximum':v[-1]}
