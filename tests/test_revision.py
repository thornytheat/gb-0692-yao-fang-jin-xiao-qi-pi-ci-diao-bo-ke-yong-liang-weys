"""修订替代版本：关联链、占库承接、裁决、幂等与当前方案切换。"""
import pytest

HEADER = 'record,kind,sku,lot,qty,frozen,pack,expiry,store,min_days,arrival,version,status'


def stock(rec, sku, lot, qty, rev=1, pack=5, status='normal'):
    return f'{rec},stock,{sku},{lot},{qty},0,{pack},2027-06-30,中央仓,0,2026-11-20,{rev},{status}'


def demand(rec, sku, qty, store, rev=1):
    return f'{rec},demand,{sku},,{qty},0,1,,{store},10,2026-11-20,{rev},normal'


def csv_of(*lines):
    return '\n'.join([HEADER, *lines]) + '\n'


@pytest.fixture
def head(client):
    text = csv_of(stock('S1', '0001', 'L1', 100), demand('D1', '0001', 60, '门店01'))
    run = client.post('/api/run', json={'csv': text}).get_json()
    client.post('/api/review',
                json={'id': run['manifest']['run_id'], 'revision': 1, 'decision': '通过'})
    return run


def test_revision_takes_latest_stock_and_inherits_hold(client, head):
    text = csv_of(stock('S1', '0001', 'L1', 130, rev=2),
                  demand('D1', '0001', 80, '门店01', rev=2))
    rev = client.post('/api/revision', json={'csv': text}).get_json()
    assert rev['manifest']['parent_id'] == head['manifest']['run_id']
    assert rev['manifest']['chain_id'] == head['manifest']['chain_id']
    assert rev['manifest']['revision_no'] == 2
    # 最新库存 130，承接旧方案未发 60，本版可分配 70；净需求 80 -> 分 70 缺 10。
    lot = rev['lot_revision_view'][0]
    assert (lot['最新可调拨'], lot['未发占用'], lot['本版可分配']) == (130, 60, 70)
    assert rev['stages']['5']['rows'][0]['调拨数量'] == 70
    assert rev['stages']['7']['rows'][0]['缺口'] == 10
    # M6 守恒：库存差额归零。
    assert all(r['差额'] == 0 for r in rev['stages']['6']['rows'])


def test_original_run_and_decision_remain_queryable(client, head):
    text = csv_of(stock('S1', '0001', 'L1', 130, rev=2),
                  demand('D1', '0001', 80, '门店01', rev=2))
    client.post('/api/revision', json={'csv': text})
    old = client.get('/api/runs/' + head['manifest']['run_id']).get_json()
    assert old['decision'] == '通过'
    assert old['stages']['5']['rows'][0]['调拨数量'] == 60


def test_revision_switches_current_execution_plan(client, head):
    text = csv_of(stock('S1', '0001', 'L1', 130, rev=2),
                  demand('D1', '0001', 80, '门店01', rev=2))
    rev = client.post('/api/revision', json={'csv': text}).get_json()
    page = client.get('/work/7').data.decode()
    assert rev['manifest']['run_id'] in page
    assert '未发占用承接' in page and '可用差额' in page


def test_idempotent_retry_does_not_duplicate_hold(client, head):
    text = csv_of(stock('S1', '0001', 'L1', 135, rev=2),
                  demand('D1', '0001', 82, '门店01', rev=2))
    first = client.post('/api/revision',
                        json={'csv': text, 'idempotency_key': 'idem-1'}).get_json()
    second = client.post('/api/revision',
                         json={'csv': text, 'idempotency_key': 'idem-1'}).get_json()
    assert first['manifest']['run_id'] == second['manifest']['run_id']
    assert second.get('idempotent') is True
    runs = client.get('/api/history').get_json()
    assert len(runs) == 2


def test_same_revision_different_value_rejected(client):
    text = csv_of(stock('S1', '0001', 'L1', 200, rev=2),
                  stock('S1', '0001', 'L1', 210, rev=2),
                  demand('D1', '0001', 80, '门店01', rev=2))
    run = client.post('/api/run', json={'csv': text}).get_json()
    assert any(q['原因码'] == 'CONFLICT' for q in run['quarantine'])
    kept = next(s for s in run['stocks'] if s['record'] == 'S1')
    assert kept['qty_n'] == 200


def test_lower_revision_never_rolls_back_regardless_of_order(client):
    # 低修订号出现在高修订号之后（晚到），仍判倒退且维持高修订内容。
    text = csv_of(stock('S1', '0001', 'L1', 130, rev=2),
                  stock('S1', '0001', 'L1', 50, rev=1),
                  demand('D1', '0001', 80, '门店01', rev=2))
    run = client.post('/api/run', json={'csv': text}).get_json()
    assert any(q['原因码'] == 'REV_STALE' for q in run['quarantine'])
    kept = next(s for s in run['stocks'] if s['record'] == 'S1')
    assert kept['qty_n'] == 130 and kept['revision_n'] == 2


def test_chain_detail_and_manual_activation(client, head):
    text = csv_of(stock('S1', '0001', 'L1', 130, rev=2),
                  demand('D1', '0001', 80, '门店01', rev=2))
    rev = client.post('/api/revision', json={'csv': text}).get_json()
    chain_id = rev['manifest']['chain_id']
    detail = client.get('/api/chains/' + chain_id).get_json()
    assert [r['revision_no'] for r in detail['runs']] == [1, 2]
    assert detail['current_id'] == rev['manifest']['run_id']
    back = client.post('/api/runs/' + head['manifest']['run_id'] + '/activate',
                       json={}).get_json()
    assert back['current_id'] == head['manifest']['run_id']


def test_revision_without_chain_is_conflict(client):
    text = csv_of(stock('SX', '0009', 'LX', 10), demand('DX', '0009', 5, '门店09'))
    resp = client.post('/api/revision', json={'csv': text})
    assert resp.status_code == 409 and resp.get_json()['code'] == 'CHAIN'


def test_vanished_lot_hold_is_reported_not_silently_dropped(client):
    head_text = csv_of(stock('S2', '0002', 'L2', 40), demand('D9', '0002', 30, '门店09'))
    head_run = client.post('/api/run', json={'csv': head_text}).get_json()
    new_text = csv_of(stock('S2', '0002', 'L9', 40, rev=2),
                      demand('D9', '0002', 30, '门店09', rev=2))
    rev = client.post('/api/revision',
                      json={'csv': new_text, 'parent_id': head_run['manifest']['run_id']})
    assert rev.status_code == 200
    lost = rev.get_json()['revision_info']['lost_holds']
    assert lost and lost[0]['批号'] == 'L2' and lost[0]['承接缺口'] == 30


def test_repeated_revision_submission_reuses_batch(client, head):
    text = csv_of(stock('S1', '0001', 'L1', 130, rev=2),
                  demand('D1', '0001', 80, '门店01', rev=2))
    first = client.post('/api/revision', json={'csv': text}).get_json()
    second = client.post('/api/revision', json={'csv': text}).get_json()
    assert first['manifest']['run_id'] == second['manifest']['run_id']
    assert second.get('reused') is True


def test_explicit_parent_accepts_entity_set_change_with_release(client, head):
    # 需求单在修订中消失：显式 parent_id 承接，登记 released_holds。
    text = csv_of(stock('S1', '0001', 'L1', 130, rev=2),
                  demand('D1', '0001', 80, '门店01', rev=2),
                  demand('DGONE', '0001', 10, '门店99', rev=2))
    head_two = client.post('/api/run', json={
        'csv': csv_of(stock('S1', '0001', 'L1', 100),
                      demand('D1', '0001', 60, '门店01'),
                      demand('DGONE', '0001', 10, '门店99'))}).get_json()
    rev_text = csv_of(stock('S1', '0001', 'L1', 130, rev=2),
                      demand('D1', '0001', 80, '门店01', rev=2))
    resp = client.post('/api/revision',
                       json={'csv': rev_text, 'parent_id': head_two['manifest']['run_id']})
    assert resp.status_code == 200
    assert {'需求单': 'DGONE'} in resp.get_json()['revision_info']['released_holds']


def test_revision_accepts_csv_file_upload(client, head):
    text = csv_of(stock('S1', '0001', 'L1', 130, rev=2),
                  demand('D1', '0001', 80, '门店01', rev=2))
    import io
    resp = client.post('/api/revision',
                       data={'file': (io.BytesIO(text.encode('utf-8')), 'rev.csv')},
                       content_type='multipart/form-data')
    assert resp.status_code == 200
    assert resp.get_json()['manifest']['parent_id'] == head['manifest']['run_id']


def test_expiry_and_pack_algorithms_unchanged_under_hold(client, head):
    text = csv_of(stock('S1', '0001', 'L1', 133, rev=2),
                  demand('D1', '0001', 80, '门店01', rev=2))
    rev = client.post('/api/revision', json={'csv': text}).get_json()
    # m3 仍按整包装向下取整：133 -> 130，未被占用逻辑改动。
    assert rev['usable'][0]['available'] == 130
    # m5 分配结果仍为整包装倍数。
    assert all(a['调拨数量'] % a['整包装'] == 0 for a in rev['allocations'])


def test_review_page_compare_fields_present(client, head):
    text = csv_of(stock('S1', '0001', 'L1', 130, rev=2),
                  demand('D1', '0001', 80, '门店01', rev=2))
    rev = client.post('/api/revision', json={'csv': text}).get_json()
    row = rev['stages']['7']['rows'][0]
    for field in ('原方案量', '新方案净需求', '未发占用承接', '本版已分配', '可用差额'):
        assert field in row
    assert row['原方案量'] == 60 and row['新方案净需求'] == 80
    assert row['未发占用承接'] == 60 and row['可用差额'] == 10
