from app.domain import whole, day
from app.errors import DomainError
from app.reasons import isolate
from app.revision import adjudicate_record, parse_revision, determine_max_revisions


def apply(ctx):
    accepted = {}
    duplicates = 0
    replaced = 0
    stale = 0
    # 第一遍：确定各业务键最高修订号，保证裁决与行序无关。
    ctx['_max_rev'] = determine_max_revisions(ctx['rows'], parse_revision)
    for r in ctx['rows']:
        try:
            if r['kind'] not in ('stock', 'demand'):
                raise DomainError('KIND', '记录类别无效')
            qty = whole(r['qty'])
            frozen = whole(r['frozen'])
            pack = whole(r['pack'])
            days = whole(r['min_days'])
            if (r['kind'] == 'stock' and frozen > qty) or pack < 1:
                raise DomainError('QUANTITY', '冻结量或包装数量无效')
            if not r['sku'] or not r['record']:
                raise DomainError('MISSING', '业务编号为空')
            day(r['arrival'])
            if r['kind'] == 'stock':
                day(r['expiry'])
                if not r['lot']:
                    raise DomainError('MISSING', '批号为空')
            item, action = adjudicate_record(ctx, r, parse_revision)
            if action in ('conflict', 'stale'):
                if action == 'stale':
                    stale += 1
                continue
            if action == 'duplicate':
                duplicates += 1
                continue
            if action == 'replaced':
                replaced += 1
            key = (r['kind'], r['record'])
            accepted[key] = {**item, 'qty_n': qty, 'frozen_n': frozen,
                             'pack_n': pack, 'min_days_n': days,
                             'revision_n': item['_rev']}
            accepted[key].pop('_rev', None)
        except DomainError as e:
            isolate(ctx, r, e.code, e.message)
    stocks = [v for k, v in accepted.items() if k[0] == 'stock']
    demands = [v for k, v in accepted.items() if k[0] == 'demand']
    # Recall is dominant even when a normal copy appeared earlier.
    recalls = {(r['sku'], r['lot']) for r in ctx['rows']
               if r['kind'] == 'stock' and r['status'] == 'recall'}
    unique = {}
    valid = []
    for s in stocks:
        if (s['sku'], s['lot']) in recalls:
            isolate(ctx, s, 'RECALL', '召回批禁止调拨')
            continue
        if (s['sku'], s['lot']) in unique:
            isolate(ctx, s, 'LOT_DUP', '批号重复来源')
            continue
        s['stock_key'] = s['sku'] + ':' + s['lot']
        unique[(s['sku'], s['lot'])] = s
        valid.append(s)
    ctx.update(stocks=valid, demands=demands, duplicates=duplicates,
               replaced=replaced, stale=stale)
    return {'rows': valid + demands,
            'metrics': [['有效库存', len(valid), '批'], ['门店需求', len(demands), '单'],
                        ['修订替换', replaced, '条'], ['倒退隔离', stale, '条'],
                        ['隔离', len(ctx['quarantine']), '条']]}
