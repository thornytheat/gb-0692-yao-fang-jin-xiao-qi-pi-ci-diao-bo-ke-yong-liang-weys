"""修订替代版本：同批号补录的关联、占库承接与裁决。

设计要点：
- 批次内容不可变；修订生成同链上的新 run，不覆盖旧 run，原复核结果与原占库依据保留可查。
- 同链判定来自业务实体键（库存来源单据号、需求单号），与文件顺序无关；
  批号可在修订中消失/替换，其未承接占用通过 lost_holds 显式留痕。
- 旧方案未发数量按批号汇总为 hold，在新方案分配前从最新可用量中预留；
  hold 只调整 m5 的分配输入，不改动 m3 的效期/整包装算法。
- 同一修订号对同一业务键出现不同内容直接拒绝（隔离 CONFLICT），不按文件顺序覆盖；
  修订号倒退不倒扣，仅隔离提示，业务键仍维持已见到的最高修订内容。
"""
import hashlib

from app.errors import DomainError
from app.reasons import isolate


def parse_revision(value):
    """来源修订号：正整数；无法解析时抛出由调用方隔离的 DomainError。"""
    text = str(value).strip()
    if not text.isdigit():
        raise DomainError('VERSION', '修订号必须为正整数')
    rev = int(text)
    if rev < 1:
        raise DomainError('VERSION', '修订号必须为正整数')
    return rev


def chain_key(stocks, demands):
    """按业务实体键计算同链指纹：库存按来源单据号、需求按需求单。

    批号本身可在修订中消失或替换（占用承接据此登记 lost_holds），
    因此批号不参与链身份，只作为占库与分配的明细维度。
    """
    parts = ['S:' + s['record'] for s in stocks]
    parts += ['D:' + d['record'] for d in demands]
    digest = hashlib.sha256('\n'.join(sorted(parts)).encode('utf-8')).hexdigest()
    return digest[:16]


def prior_holds(parent_run):
    """从父方案的未发调拨行汇总批号级占库（本工具不做实际物流，全部视为未发）。"""
    holds = {}
    for row in parent_run.get('allocations', []):
        key = row['药品'] + ':' + row['批号']
        holds[key] = holds.get(key, 0) + int(row['调拨数量'])
    return holds


def build_revision(ctx, parent_run):
    """注入承接信息：父方案快照、批号占库、链标识与序号。"""
    holds = prior_holds(parent_run)
    parent_manifest = parent_run['manifest']
    ctx['holds'] = holds
    ctx['revision_info'] = {
        'chain_id': parent_manifest.get('chain_id', parent_manifest['run_id']),
        'parent_id': parent_manifest['run_id'],
        'parent_decision': parent_run.get('decision', '待复核'),
        'parent_revision_no': parent_manifest.get('revision_no', 1),
        'revision_no': parent_manifest.get('revision_no', 1) + 1,
        'holds': holds,
        'lost_holds': [],
        'released_holds': [],
    }


def seed_revision(ctx):
    """无父方案的独立运行：链从自身开始，不承接任何占库。"""
    ctx.setdefault('holds', {})
    ctx.setdefault('revision_info', {
        'chain_id': None,
        'parent_id': None,
        'parent_decision': None,
        'parent_revision_no': 0,
        'revision_no': 1,
        'holds': {},
        'lost_holds': [],
        'released_holds': [],
    })


def reserve_holds(ctx):
    """在不改动效期/整包装结果的前提下，把旧方案未发占用从最新库存中预留。

    返回分配用的库存副本（available 已扣 hold），并登记失效/释放的占用。
    """
    info = ctx.get('revision_info') or {}
    holds = ctx.get('holds') or {}
    usable = ctx['usable']
    latest = {s['stock_key']: s for s in usable}
    adjusted = []
    for s in usable:
        key = s['stock_key']
        hold = int(holds.get(key, 0))
        available = int(s['available'])
        if hold > available:
            # 最新库存已不足以承接原占用：全部锁住，缺口由分配结果体现，依据保留。
            info.setdefault('lost_holds', []).append(
                {'批号': s['lot'], '药品': s['sku'], '原未发占用': hold,
                 '最新可调拨': available, '承接占用': available,
                 '承接缺口': hold - available})
            hold = available
        item = {**s, '原可调拨': available, '未发占用': hold,
                '本版可分配': available - hold,
                # 域算法 allocate 读取 available：副本上替换为扣占用后的量，
                # ctx['usable'] 原对象与 m3 效期/整包装结果不受影响。
                'available': available - hold}
        adjusted.append(item)
    for key, hold in holds.items():
        if key not in latest:
            sku, lot = key.split(':', 1)
            info.setdefault('lost_holds', []).append(
                {'批号': lot, '药品': sku, '原未发占用': hold,
                 '最新可调拨': 0, '承接占用': 0, '承接缺口': hold})
    # 旧需求单在新输入消失时，对应占用释放回可用库存（hold 仅按仍存在的批号保留）。
    parent_demands = set()
    parent = ctx.get('_parent_run')
    if parent is not None:
        parent_demands = {d['record'] for d in parent.get('net_demands', [])}
    current_demands = {d['record'] for d in ctx['net_demands']}
    for record in sorted(parent_demands - current_demands):
        info.setdefault('released_holds', []).append({'需求单': record})
    ctx['allocatable'] = adjusted
    return adjusted


def adjudicate_record(ctx, r, parse):
    """M2 修订裁决。返回 (item, action)；action 为 new/replaced/duplicate/conflict/stale。

    裁决与文件行序无关：第一遍 determine_max_revisions 确定各键最高修订号，
    晚到的低修订号在任何位置都判倒退，不倒扣已采信内容。
    """
    key = (r['kind'], r['record'])
    try:
        rev = parse(r.get('version'))
    except DomainError as error:
        isolate(ctx, r, error.code, error.message)
        return None, 'conflict'
    max_rev = ctx.get('_max_rev', {})
    if key in max_rev and rev < max_rev[key]:
        isolate(ctx, r, 'REV_STALE', '修订号倒退，维持已采信的较高修订')
        return None, 'stale'
    fingerprint = tuple((k, v) for k, v in r.items() if k != '行号')
    seen = ctx.setdefault('_rev_seen', {})
    if key in seen:
        old_rev, old_print = seen[key]
        if old_print == fingerprint:
            return None, 'duplicate'
        if rev == old_rev:
            isolate(ctx, r, 'CONFLICT', '同修订号内容冲突，拒绝覆盖')
            return None, 'conflict'
        seen[key] = (rev, fingerprint)
        return {**r, '_rev': rev}, 'replaced'
    seen[key] = (rev, fingerprint)
    return {**r, '_rev': rev}, 'new'


def determine_max_revisions(rows, parse):
    """第一遍扫描：每个业务键可见的最高修订号（无法解析的行跳过）。"""
    max_rev = {}
    for r in rows:
        try:
            rev = parse(r.get('version'))
        except DomainError:
            continue
        key = (r['kind'], r['record'])
        if rev > max_rev.get(key, 0):
            max_rev[key] = rev
    return max_rev
