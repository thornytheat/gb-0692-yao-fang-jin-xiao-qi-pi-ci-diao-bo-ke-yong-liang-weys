from app.domain import allocate
from app.revision import reserve_holds


def apply(ctx):
    # 承接旧方案未发占用：仅调整分配输入，效期分层与整包装结果保持原样。
    if ctx.get('holds'):
        allocatable = reserve_holds(ctx)
        ctx['allocatable'] = allocatable
    else:
        allocatable = ctx['usable']
    rows, left, short = allocate(allocatable, ctx['net_demands'])
    ctx.update(allocations=rows, remaining=left, shortages=short)
    holds = ctx.get('holds') or {}
    hold_total = sum(holds.values())
    return {'rows': rows,
            'metrics': [['调拨', sum(r['调拨数量'] for r in rows), '件'],
                        ['分配行', len(rows), '条'],
                        ['缺口', sum(r['缺口'] for r in short), '件'],
                        ['承接未发占用', hold_total, '件']]}
