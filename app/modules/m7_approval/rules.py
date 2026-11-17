from app.domain import day
def apply(ctx):
    rows=[];lookup={d['record']:d for d in ctx['net_demands']}
    for r in ctx['shortages']:
        d=lookup[r['需求单']];alloc=[a for a in ctx['allocations'] if a['需求单']==r['需求单']]
        min_days=min((a['到店余期_天'] for a in alloc),default=0)
        rows.append({**r,'最短余期_天':min_days,'复核':'可下发' if not r['缺口'] else '缺口待补','计划版本':1})
    return {'rows':rows,'metrics':[['可下发',sum(r['复核']=='可下发' for r in rows),'单'],['待补',sum(r['复核']=='缺口待补' for r in rows),'单'],['版本',1,'']]}

