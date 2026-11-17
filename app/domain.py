from datetime import date
from decimal import Decimal
from app.numeric import number
from app.errors import DomainError
AS_OF=date(2026,11,18)
def day(value):
    try: return date.fromisoformat(value)
    except ValueError: raise DomainError('DATE','日期格式无效')
def whole(value):
    n=number(value)
    if n<0 or n!=n.to_integral_value(): raise DomainError('QUANTITY','数量须为非负整数')
    return int(n)
def eligible(stock,demand):
    return stock['sku']==demand['sku'] and stock['status']=='normal' and (day(stock['expiry'])-day(demand['arrival'])).days>=demand['min_days_n'] and day(stock['expiry'])>day(demand['arrival'])
def allocate(stocks,demands):
    remaining={s.get('stock_key',s['lot']):s['available'] for s in stocks};rows=[];shortages=[]
    for d in sorted(demands,key=lambda r:(r['arrival'],r['store'],r['record'])):
        need=d['net_need'];requested=need
        for s in sorted(stocks,key=lambda r:(r['expiry'],r['lot'])):
            if not eligible(s,d): continue
            take=min(remaining[s.get('stock_key',s['lot'])],need)//s['pack_n']*s['pack_n']
            if not take: continue
            remaining[s.get('stock_key',s['lot'])]-=take;need-=take
            rows.append({'需求单':d['record'],'门店':d['store'],'药品':d['sku'],'批号':s['lot'],'到期日':s['expiry'],'调拨数量':take,'整包装':s['pack_n'],'到店余期_天':(day(s['expiry'])-day(d['arrival'])).days})
        shortages.append({'需求单':d['record'],'门店':d['store'],'净需求':requested,'已分配':requested-need,'缺口':need})
    return rows,remaining,shortages
