import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from nfl_sfsea_fixture_overlay import semantic_membership, partition

def test_allowlisted_union_counts_alias_once_without_broad_date_matching():
    tokens=['26JAN17SFSEA','26JAN18SFSEA','26JAN11SFPHI','26JAN19SFSEA']
    assert semantic_membership(tokens)=={'26JAN17SFSEA','26JAN11SFPHI','26JAN19SFSEA'}
    assert partition(tokens)=='both'
    assert partition(['26JAN18SFSEA','26JAN18SFSEA'])=='Jan18_only'
    assert partition(['26JAN19SFSEA']) is None
