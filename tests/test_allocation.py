import pytest

from app.errors import SurveyProblem
from app.modules.allocation.remainders import largest_remainders
from app.modules.allocation.service import expand
from app.pipeline import run
from app.source import sources


def test_tie_is_stable(dirty):  # TRAP-24：层内并列由全市对账定向，结果确定
    layer=dirty['allocation']['layers']['城北']
    assert layer['integers']=={'direct':33,'transfer':33,'other':34} and layer['winners']==['other']


def test_unequal_remainders(dirty):
    layer=dirty['allocation']['layers']['枢纽']
    assert layer['remainders']=={'direct':'2/3','transfer':'0','other':'1/3'}
    assert layer['integers']=={'direct':67,'transfer':50,'other':33}


def test_dirty_integer_report(dirty):
    assert dirty['allocation']['totals']=={'direct':100,'transfer':83,'other':67}


def test_city_within_one_of_quota(dirty):
    city=dirty['allocation']['city']
    assert city['integers']=={'direct':100,'transfer':83,'other':67} and city['winners']==['other']
    assert city['quotas']=={'direct':'100','transfer':'250/3','other':'200/3'}


def test_clean_includes_last_service():
    output=run(sources({'sample':'clean'}))['allocation']
    assert (output['estimated'],output['unknown'])==(290,0)
    assert output['layers']['末班']['integers']=={'direct':20,'transfer':20,'other':0}


def test_zero_kept_unknown(dirty):
    row=dirty['allocation']['layers']['末班']
    assert row['unobserved']==40 and sum(row['integers'].values())==0


def test_bad_quota_rejected():
    with pytest.raises(SurveyProblem) as exc:
        largest_remainders({'direct':'1/3','transfer':'1/3','other':'1/3'},2)
    assert exc.value.code=='BAD_QUOTA'


def competing_layers():
    # 三层精确配额同为 3/2、3/2、0：各自独立进位都会把直达推到 6 人，偏离全市配额 9/2 超过一人
    quota={'direct':'3/2','transfer':'3/2','other':'0'}
    return {'layers':{name:dict(population=3,usable=3,status='calibrated',quotas=dict(quota))
                      for name in ('A','B','C')}}


def test_city_reconciles_competing_layers():
    output=expand(competing_layers())
    assert output['totals']=={'direct':5,'transfer':4,'other':0}
    assert output['city']['integers']==output['totals']
    for row in output['layers'].values():
        assert sum(row['integers'].values())==3
        assert all(row['floors'][key]<=row['integers'][key]<=row['floors'][key]+1 for key in row['integers'])
    assert sum(row['winners'].count('transfer') for row in output['layers'].values())==1


def test_same_input_reallocates_identically():
    first, second=expand(competing_layers()),expand(competing_layers())
    assert first==second


def test_city_columns_fallback_stays_within_one(monkeypatch):
    # 人为让全市最大余数给出不可行的列合计，兜底仍须保证两级偏差不足一人
    import app.modules.allocation.citywide as citywide
    monkeypatch.setattr(citywide,'largest_remainders',
                        lambda values,total:{'integers':{key:0 for key in values},'floors':{},'winners':[],'remainders':{}})
    output=expand(competing_layers())
    assert output['totals']=={'direct':5,'transfer':4,'other':0}
    for row in output['layers'].values():
        assert sum(row['integers'].values())==3
        assert all(row['floors'][key]<=row['integers'][key]<=row['floors'][key]+1 for key in row['integers'])
