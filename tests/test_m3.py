from app.domain import eligible
def test_expired_isolated(ctx): # TRAP-23
    assert any(r['原因码']=='EXPIRED' for r in ctx['quarantine'])
def test_pack_rounding(ctx): assert all(r['available']%r['pack_n']==0 for r in ctx['usable'])
def test_frozen_removed(ctx): assert ctx['usable'][0]['available']==95
def test_near_expiry_class(ctx): assert ctx['usable'][0]['效期层']=='近效期'
def test_expiry_day_ineligible():
    assert not eligible({'sku':'x','status':'normal','expiry':'2026-11-20'},{'sku':'x','arrival':'2026-11-20','min_days_n':0})
def test_minimum_day_inclusive():
    assert eligible({'sku':'x','status':'normal','expiry':'2026-11-30'},{'sku':'x','arrival':'2026-11-20','min_days_n':10})
def test_lots_survive(ctx): assert len(ctx['usable'])==24

