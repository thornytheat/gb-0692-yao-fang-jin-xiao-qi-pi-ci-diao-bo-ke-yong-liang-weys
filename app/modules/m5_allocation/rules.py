from app.domain import allocate
def apply(ctx):
    rows,left,short=allocate(ctx['usable'],ctx['net_demands']);ctx.update(allocations=rows,remaining=left,shortages=short)
    return {'rows':rows,'metrics':[['调拨',sum(r['调拨数量'] for r in rows),'件'],['分配行',len(rows),'条'],['缺口',sum(r['缺口'] for r in short),'件']]}

