from app.domain import allocate
def test_allocations_whole_packages(ctx): assert all(a['调拨数量']%a['整包装']==0 for a in ctx['allocations'])
def test_fefo_first(ctx): assert ctx['allocations'][0]['到期日']=='2026-12-02'
def test_no_negative_remainder(ctx): assert min(ctx['remaining'].values())>=0
def test_demand_cap(ctx): assert all(a['已分配']<=a['净需求'] for a in ctx['shortages'])
def test_no_stock(ctx):
    rows,left,short=allocate([],ctx['net_demands']);assert not rows and sum(x['缺口'] for x in short)==675
def test_min_life_kept(ctx): assert all(a['到店余期_天']>=10 for a in ctx['allocations'])
def test_deterministic_order(ctx):
    assert allocate(list(reversed(ctx['usable'])),list(reversed(ctx['net_demands'])))[0]==ctx['allocations']

