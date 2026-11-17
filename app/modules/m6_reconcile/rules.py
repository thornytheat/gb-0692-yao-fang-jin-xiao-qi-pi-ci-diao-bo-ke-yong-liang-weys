def apply(ctx):
     pool = ctx.get('allocatable') or ctx['usable']
     opening = sum(int(s['available']) for s in pool)
     original = sum(int(s.get('原可调拨', s['available'])) for s in pool)
     sent = sum(r['调拨数量'] for r in ctx['allocations'])
     left = sum(ctx['remaining'].values())
     holds = ctx.get('holds') or {}
     hold_total = sum(holds.values())
     need = sum(d['net_need'] for d in ctx['net_demands'])
     missing = sum(r['缺口'] for r in ctx['shortages'])
     # 最新库存 = 本版调拨 + 承接占用 + 分配后结余
     balanced = original == sent + hold_total + left and need == sent + missing
     ctx['balanced'] = balanced
     rows = [
         {'项目': '可调拨库存', '期初': original, '发出': sent, '结余或缺口': left,
          '差额': original - sent - hold_total - left},
         {'项目': '净需求', '期初': need, '发出': sent, '结余或缺口': missing,
          '差额': need - sent - missing},
         {'项目': '未发占用承接', '期初': hold_total, '发出': 0, '结余或缺口': hold_total,
          '差额': original - sent - hold_total - left},
         {'项目': '本版可用差额', '期初': opening, '发出': sent,
          '结余或缺口': left, '差额': opening - sent - left},
     ]
     return {'rows': rows,
             'metrics': [['库存差额', original - sent - hold_total - left, '件'],
                         ['需求差额', need - sent - missing, '件'],
                         ['收发核验', '相符' if balanced else '差异', '']]}
