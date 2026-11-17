from app.modules.m6_reconcile.rules import apply
from copy import deepcopy
def test_balanced(ctx): assert ctx['balanced'] is True
def test_zero_differences(ctx): assert all(r['差额']==0 for r in ctx['stages']['6']['rows'])
def test_stock_invariant(ctx): assert sum(s['available'] for s in ctx['usable'])==sum(ctx['remaining'].values())+sum(a['调拨数量'] for a in ctx['allocations'])
def test_demand_invariant(ctx): assert 675==sum(x['缺口']+x['已分配'] for x in ctx['shortages'])
def test_tampered_remaining(ctx):
    c=deepcopy(ctx);c['remaining']['0002:B0001']+=1;apply(c);assert c['balanced'] is False
def test_no_allocations_not_zeroed(ctx): assert ctx['stages']['6']['rows'][0]['期初']>0
def test_reconcile_units(ctx): assert ctx['stages']['6']['metrics'][0][2]=='件'

