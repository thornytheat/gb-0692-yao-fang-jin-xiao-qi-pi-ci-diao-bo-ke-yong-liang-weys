from app.modules.m4_demand.rules import apply
def test_net_need(ctx): assert ctx['net_demands'][0]['net_need']==29
def test_total_need(ctx): assert sum(r['net_need'] for r in ctx['net_demands'])==675
def test_store_count(ctx): assert len({r['store'] for r in ctx['net_demands']})==18
def test_zero_need():
    c={'demands':[{'qty_n':5,'frozen_n':5,'record':'x','store':'a','sku':'s','min_days_n':1}]};apply(c);assert c['net_demands'][0]['net_need']==0
def test_no_demand(): assert apply({'demands':[]})['rows']==[]
def test_date_retained(ctx): assert ctx['net_demands'][0]['arrival']=='2026-11-20'
def test_sample_min_days(ctx): assert {r['min_days_n'] for r in ctx['net_demands']}=={10,11,12}

