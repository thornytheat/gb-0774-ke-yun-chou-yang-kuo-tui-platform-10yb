from app.main import create_app
from app.modules.ledger.storage import Archive

from tests.test_archive import seed_legacy


def test_module_pages(client):
    for tab,text in {'balance':'分层有效矩阵','returns':'回收裁决','frame':'班次出票沿革','weights':'分层校准证据',
                     'allocation':'尾差分配证据','archive':'近期扩推批次','release':'归档并校验'}.items():
        result=client.get('/survey/'+tab)
        assert result.status_code==200 and text in result.get_data(as_text=True)


def test_select_layer(client):
    answer=client.get('/survey/allocation?layer=枢纽').get_data(as_text=True)
    assert '200/3' in answer and '67' in answer


def test_failed_archival_does_not_write(client,tables):
    tables['frame']='broken,header\n'
    assert client.post('/api/runs',json={'tables':tables}).json['code']=='BAD_HEADER'
    assert client.get('/api/runs').json['runs']==[]


def test_allocation_page_shows_city_alignment(client):
    answer=client.get('/survey/allocation').get_data(as_text=True)
    assert '全市配额对位' in answer and '250/3' in answer


def test_balance_page_shows_quota_gaps(client):
    answer=client.get('/survey/balance').get_data(as_text=True)
    assert '全市配额偏差' in answer


def test_allocation_page_follows_archive(tmp_path,tables):
    path=tmp_path/'page.db'
    legacy=seed_legacy(Archive(path),tables)
    app=create_app(path).test_client()
    archived=app.get(f"/survey/allocation?run={legacy['id']}").get_data(as_text=True)
    live=app.get('/survey/allocation').get_data(as_text=True)
    assert '101 人' in archived and '全市配额对位' not in archived
    assert '100 人' in live and '全市配额对位' in live
