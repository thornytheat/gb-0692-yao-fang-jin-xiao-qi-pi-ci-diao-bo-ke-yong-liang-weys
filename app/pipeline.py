from app.modules.m1_receiving.service import execute as stage1
from app.modules.m2_lots.service import execute as stage2
from app.modules.m3_expiry.service import execute as stage3
from app.modules.m4_demand.service import execute as stage4
from app.modules.m5_allocation.service import execute as stage5
from app.modules.m6_reconcile.service import execute as stage6
from app.modules.m7_approval.service import execute as stage7
from app.config import SAMPLE
from app.manifest import make
from app.numeric import serial
from app.revision import build_revision, seed_revision, chain_key
from time import perf_counter


def calculate(text=None, stop=7, parent_run=None):
    started = perf_counter()
    if text is None:
        text = SAMPLE.read_text(encoding='utf-8-sig')
    if not isinstance(text, str):
        from app.errors import DomainError
        raise DomainError('TYPE', 'CSV必须是文本')
    ctx = {'text': text, 'rows': [], 'quarantine': [], 'stages': {},
           'manifest': make(text)}
    if parent_run is not None:
        ctx['_parent_run'] = parent_run
        build_revision(ctx, parent_run)
    else:
        seed_revision(ctx)
    for stage in STAGES[:stop]:
        stage(ctx)
    # M2 之后链指纹即可确定；链序号在无父方案时补全为 1。
    if 'stocks' in ctx and 'demands' in ctx:
        info = ctx.setdefault('revision_info', {})
        key = chain_key(ctx['stocks'], ctx['demands'])
        info['chain_key'] = key
        if parent_run is None:
            info.setdefault('revision_no', 1)
            # 链首以自身 run_id 作为链标识，后续替代版本沿用。
            if not info.get('chain_id'):
                info['chain_id'] = ctx['manifest']['run_id']
        ctx['manifest']['chain_key'] = key
        ctx['manifest']['revision_no'] = info.get('revision_no', 1)
        ctx['manifest']['chain_id'] = info['chain_id']
        if parent_run is not None:
            ctx['manifest']['parent_id'] = info['parent_id']
    ctx['manifest']['elapsed_ms'] = round((perf_counter() - started) * 1000, 3)
    ctx.pop('text', None)
    ctx.pop('_rev_seen', None)
    ctx.pop('_parent_run', None)
    return serial(ctx)


STAGES = [stage1, stage2, stage3, stage4, stage5, stage6, stage7]
