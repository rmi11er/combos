from copy import deepcopy
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.feed_freshness import FreshnessAudit
from test_pinnacle_feed import sample


def envelope(at=100):
    _,fixture=sample()
    return {'payload':[fixture],'retrieved_at':at,'request_started_at':at-.2,
            'response_headers':{'Age':'0','Date':'Thu, 01 Jan 1970 00:01:40 GMT'}}


def test_identical_old_quotes_do_not_imply_stale_or_healthy_upstream():
    audit=FreshnessAudit('pinnacle')
    first=audit.add(envelope());second=audit.add(envelope(130))
    assert first['quote_change_age_seconds']['median']==30
    assert second['quote_change_age_seconds']['median']==60
    assert second['request_elapsed_seconds']==pytest.approx(.2)
    assert second['counts']['unchanged_outcomes']==2
    report=audit.report()
    assert report['verdict']=='inconclusive_no_economic_changes_observed'
    assert not report['upstream_freshness_validated']


def test_changes_detected_with_separate_source_publication_and_poll_clocks():
    audit=FreshnessAudit('pinnacle');audit.add(envelope())
    later=envelope(130)
    v=later['payload'][0]['bookmakerOdds']['pinnacle']['markets']['m']['outcomes']['over']['players']['0']
    v.update(price=2.02,bookmakerChangedAt='1970-01-01T00:01:39Z',changedAt='1970-01-01T00:02:09Z')
    row=audit.add(later)
    assert row['counts']['price_changes']==1
    assert row['counts']['timestamp_changes']==1
    assert row['reported_change_publication_lag_seconds']['median']==30
    assert audit.report()['verdict']=='evolving_response_observed_upstream_freshness_unproven'
    assert not audit.report()['upstream_freshness_validated']


def test_missing_markets_and_regressing_timestamps_are_recorded():
    audit=FreshnessAudit('pinnacle');audit.add(envelope())
    later=envelope(130);out=later['payload'][0]['bookmakerOdds']['pinnacle']['markets']['m']['outcomes']
    del out['under'];out['over']['players']['0']['bookmakerChangedAt']='1970-01-01T00:01:00Z'
    row=audit.add(later)
    assert row['counts']['removed_outcomes']==1
    assert row['counts']['native_timestamp_regressions']==1
    with pytest.raises(ValueError,match='did_not_advance'):audit.add(later)


def test_http_date_and_cache_age_are_not_bookmaker_health_signals():
    audit=FreshnessAudit('pinnacle');e=envelope()
    e['response_headers']['Age']='120';row=audit.add(e)
    assert row['http_cache_age_seconds']==120
    assert row['receipt_minus_http_date_seconds']==0
    assert not audit.report()['upstream_freshness_validated']


def test_missing_inactive_selection_is_not_evidence_of_a_price_change():
    audit=FreshnessAudit('pinnacle');e=envelope()
    e['payload'][0]['bookmakerOdds']['pinnacle']['markets']['m']['outcomes']['under']['players']['0']['active']=False
    audit.add(e);later=deepcopy(e);later.update(retrieved_at=130,request_started_at=129.8)
    del later['payload'][0]['bookmakerOdds']['pinnacle']['markets']['m']['outcomes']['under']
    row=audit.add(later)
    assert row['counts']['removed_active_outcomes']==0
    assert audit.report()['latest_economic_change_received_at'] is None
    assert audit.report()['verdict']=='inconclusive_membership_changes_only'
