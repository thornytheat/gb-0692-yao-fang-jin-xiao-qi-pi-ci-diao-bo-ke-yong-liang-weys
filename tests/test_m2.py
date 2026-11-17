from app.domain import whole
from app.errors import DomainError
import pytest
def test_sku_leading_zero(ctx): # TRAP-08
    assert ctx['stocks'][0]['sku']=='0002'
def test_missing_quantity(ctx): # TRAP-07
    assert any(r['原因码']=='MISSING' for r in ctx['quarantine'])
def test_conflict_not_override(ctx): # TRAP-14
    assert next(r for r in ctx['stocks'] if r['record']=='S0002')['qty_n']==110
def test_recall_dominates(ctx): # TRAP-19
    assert all(s['lot']!='RECALL' for s in ctx['stocks'])
def test_integral_quantity(): assert whole('２５')==25
def test_fraction_rejected():
    with pytest.raises(DomainError): whole('1.5')
def test_duplicate_count(ctx): assert ctx['duplicates']==1


def test_store_stock_exceeding_request_is_zero_need(raw):
    from app.pipeline import calculate
    lines=raw.splitlines();lines[25]=lines[25].replace(',31,2,',',31,99,')
    result=calculate('\n'.join(lines)+'\n')
    demand=next(d for d in result['net_demands'] if d['record']=='D0001')
    assert demand['net_need']==0

def test_same_lot_in_different_drugs_is_separate(raw):
    from app.pipeline import calculate
    result=calculate(raw+'S9999,stock,0099,B0001,100,0,5,2027-01-01,中央仓,0,2026-11-20,1,normal\n')
    assert len([s for s in result['stocks'] if s['lot']=='B0001'])==2
