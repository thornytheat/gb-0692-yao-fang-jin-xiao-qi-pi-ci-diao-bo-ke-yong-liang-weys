from app.domain import day


def apply(ctx):
    rows = []
    lookup = {d['record']: d for d in ctx['net_demands']}
    info = ctx.get('revision_info') or {}
    holds = ctx.get('holds') or {}
    parent = ctx.get('_parent_run')
    parent_alloc = {}
    parent_short = {}
    if parent is not None:
        for a in parent.get('allocations', []):
            parent_alloc[a['需求单']] = parent_alloc.get(a['需求单'], 0) + int(a['调拨数量'])
        for s in parent.get('shortages', []):
            parent_short[s['需求单']] = int(s['缺口'])
    # 批号维度的最新可调拨与承接占用，供页面核对可用差额。
    lot_view = {}
    for s in ctx.get('allocatable', ctx['usable']):
        lot_view[s['stock_key']] = {
            '批号': s['lot'], '药品': s['sku'],
            '最新可调拨': int(s.get('原可调拨', s['available'])),
            '未发占用': int(holds.get(s['stock_key'], 0)),
            '本版可分配': int(s.get('本版可分配', s['available'])),
        }
    ctx['lot_revision_view'] = list(lot_view.values())
    for r in ctx['shortages']:
        d = lookup[r['需求单']]
        alloc = [a for a in ctx['allocations'] if a['需求单'] == r['需求单']]
        min_days = min((a['到店余期_天'] for a in alloc), default=0)
        demand_hold = parent_alloc.get(r['需求单'], 0)
        old_qty = demand_hold + parent_short.get(r['需求单'], 0) if parent is not None else None
        new_net = int(r['净需求'])
        rows.append({
            **r,
            '最短余期_天': min_days,
            '复核': '可下发' if not r['缺口'] else '缺口待补',
            '计划版本': info.get('revision_no', 1),
            '原方案量': old_qty if old_qty is not None else new_net,
            '新方案净需求': new_net,
            '未发占用承接': demand_hold,
            '本版已分配': int(r['已分配']),
            '可用差额': new_net - int(r['已分配']),
        })
    ctx['revision_summary'] = {
        'chain_id': info.get('chain_id'),
        'parent_id': info.get('parent_id'),
        'parent_decision': info.get('parent_decision'),
        'revision_no': info.get('revision_no', 1),
        'hold_total': sum(holds.values()),
        'lost_holds': info.get('lost_holds', []),
        'released_holds': info.get('released_holds', []),
    }
    return {'rows': rows,
            'metrics': [['可下发', sum(r['复核'] == '可下发' for r in rows), '单'],
                        ['待补', sum(r['复核'] == '缺口待补' for r in rows), '单'],
                        ['版本', info.get('revision_no', 1), '']]}
