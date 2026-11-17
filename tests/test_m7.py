from app.modules.m7_approval.rules import apply
from copy import deepcopy
def test_plan_per_demand(ctx): assert len(ctx['stages']['7']['rows'])==18
def test_plan_revision(ctx): # TRAP-26
    assert all(r['计划版本']==1 for r in ctx['stages']['7']['rows'])
def test_known_shortage(ctx): assert any(r['复核']=='缺口待补' for r in ctx['stages']['7']['rows'])
def test_minimum_remaining_life(ctx): assert all(r['最短余期_天']>=10 for r in ctx['stages']['7']['rows'])
def test_empty_plan(ctx):
    c=deepcopy(ctx);c['shortages']=[];assert apply(c)['rows']==[]
def test_no_shortage_approved(ctx): assert all(r['缺口']==0 for r in ctx['stages']['7']['rows'] if r['复核']=='可下发')
def test_review_api_stale(client):
    x=client.post('/api/run',json={}).get_json();p={'id':x['manifest']['run_id'],'revision':1,'decision':'退回'};assert client.post('/api/review',json=p).status_code==200;assert client.post('/api/review',json=p).status_code==409

