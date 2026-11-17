import json
import os
import sqlite3
from pathlib import Path

from app.errors import DomainError

_SCHEMA = [
    '''CREATE TABLE IF NOT EXISTS runs(
        id TEXT PRIMARY KEY,
        chain_id TEXT,
        parent_id TEXT,
        chain_key TEXT,
        revision_no INTEGER NOT NULL DEFAULT 1,
        payload TEXT NOT NULL,
        revision INTEGER NOT NULL DEFAULT 1,
        decision TEXT NOT NULL DEFAULT '待复核',
        idempotency_key TEXT,
        created_seq INTEGER NOT NULL DEFAULT 0
    )''',
    '''CREATE TABLE IF NOT EXISTS chains(
        chain_id TEXT PRIMARY KEY,
        chain_key TEXT NOT NULL,
        current_id TEXT NOT NULL,
        updated_seq INTEGER NOT NULL DEFAULT 0
    )''',
    '''CREATE TABLE IF NOT EXISTS idempotency(
        key TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        created_seq INTEGER NOT NULL DEFAULT 0
    )''',
]


def connection():
    path = Path(os.environ.get('APP_DB', 'data/runs.sqlite3'))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    for statement in _SCHEMA:
        db.execute(statement)
    _migrate(db)
    return db


def _migrate(db):
    """对初始快照中的单表结构做幂等加列。"""
    cols = {r['name'] for r in db.execute('PRAGMA table_info(runs)')}
    for name, decl in (
        ('chain_id', "TEXT"), ('parent_id', "TEXT"), ('chain_key', "TEXT"),
        ('revision_no', "INTEGER NOT NULL DEFAULT 1"),
        ('idempotency_key', "TEXT"), ('created_seq', "INTEGER NOT NULL DEFAULT 0"),
    ):
        if name not in cols:
            db.execute(f'ALTER TABLE runs ADD COLUMN {name} {decl}')
    db.execute('CREATE INDEX IF NOT EXISTS idx_runs_chain ON runs(chain_id, revision_no)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_runs_chain_key ON runs(chain_key)')
    db.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_idem ON idempotency(key)')


def _next_seq(db):
    row = db.execute('SELECT COALESCE(MAX(created_seq),0)+1 AS n FROM runs').fetchone()
    return row['n']


def save(result):
    with connection() as db:
        ident = result['manifest']['run_id']
        row = db.execute(
            'SELECT payload,revision,decision FROM runs WHERE id=?', (ident,)).fetchone()
        if row:
            return {**json.loads(row['payload']), 'revision': row['revision'],
                    'decision': row['decision'], 'reused': True}
        info = result.get('revision_info') or {}
        chain_key = result['manifest'].get('chain_key') or info.get('chain_key')
        revision_no = result['manifest'].get('revision_no') or info.get('revision_no', 1)
        chain_id = result['manifest'].get('chain_id') or info.get('chain_id')
        parent_id = result['manifest'].get('parent_id') or info.get('parent_id')
        seq = _next_seq(db)
        db.execute(
            'INSERT INTO runs(id,chain_id,parent_id,chain_key,revision_no,payload,created_seq)'
            ' VALUES (?,?,?,?,?,?,?)',
            (ident, chain_id, parent_id, chain_key, revision_no,
             json.dumps(result, ensure_ascii=False), seq))
        if chain_id:
            # 链首：建立链并指向自己；散批次（无链）不登记。
            db.execute(
                'INSERT OR IGNORE INTO chains(chain_id,chain_key,current_id,updated_seq)'
                ' VALUES (?,?,?,?)', (chain_id, chain_key, ident, seq))
            db.execute('UPDATE chains SET current_id=?,updated_seq=? WHERE chain_id=?',
                       (ident, seq, chain_id))
    return {**result, 'revision': 1, 'decision': '待复核', 'reused': False}


def save_revision(result, idempotency_key=None):
    """原子写入替代版本并切换链上当前执行方案；重试不重复占库。"""
    ident = result['manifest']['run_id']
    info = result.get('revision_info') or {}
    chain_id = result['manifest'].get('chain_id') or info['chain_id']
    parent_id = result['manifest'].get('parent_id') or info['parent_id']
    chain_key = result['manifest'].get('chain_key') or info['chain_key']
    revision_no = result['manifest'].get('revision_no') or info['revision_no']
    with connection() as db:
        if idempotency_key:
            seen = db.execute('SELECT run_id FROM idempotency WHERE key=?',
                              (idempotency_key,)).fetchone()
            if seen:
                row = db.execute(
                    'SELECT payload,revision,decision FROM runs WHERE id=?',
                    (seen['run_id'],)).fetchone()
                return {**json.loads(row['payload']), 'revision': row['revision'],
                        'decision': row['decision'], 'reused': True,
                        'idempotent': True}
        row = db.execute(
            'SELECT payload,revision,decision FROM runs WHERE id=?', (ident,)).fetchone()
        if row:
            return {**json.loads(row['payload']), 'revision': row['revision'],
                    'decision': row['decision'], 'reused': True}
        parent = db.execute('SELECT chain_id FROM runs WHERE id=?', (parent_id,)).fetchone()
        if parent is None:
            raise DomainError('CHAIN', '父方案不存在，无法生成替代版本', 404)
        if parent['chain_id'] != chain_id:
            raise DomainError('CHAIN', '父方案与新方案不属于同一修订链', 409)
        dup = db.execute(
            'SELECT id FROM runs WHERE chain_id=? AND revision_no=?',
            (chain_id, revision_no)).fetchone()
        if dup:
            raise DomainError('VERSION', '同链修订序号已存在', 409)
        seq = _next_seq(db)
        db.execute(
            'INSERT INTO runs(id,chain_id,parent_id,chain_key,revision_no,payload,'
            'idempotency_key,created_seq) VALUES (?,?,?,?,?,?,?,?)',
            (ident, chain_id, parent_id, chain_key, revision_no,
             json.dumps(result, ensure_ascii=False), idempotency_key, seq))
        if idempotency_key:
            db.execute(
                'INSERT OR IGNORE INTO idempotency(key,run_id,created_seq) VALUES (?,?,?)',
                (idempotency_key, ident, seq))
        changed = db.execute(
            'UPDATE chains SET current_id=?,updated_seq=? WHERE chain_id=?',
            (ident, seq, chain_id)).rowcount
        if not changed:
            raise DomainError('CHAIN', '修订链不存在，无法切换当前方案', 409)
    return {**result, 'revision': 1, 'decision': '待复核', 'reused': False}


def get_run(ident):
    with connection() as db:
        row = db.execute(
            'SELECT payload,revision,decision FROM runs WHERE id=?', (ident,)).fetchone()
        if row is None:
            raise DomainError('NOT_FOUND', '批次不存在', 404)
        return {**json.loads(row['payload']), 'revision': row['revision'],
                'decision': row['decision']}


def latest():
    """最新的当前执行方案（无链散批次按写入顺序兜底）。"""
    with connection() as db:
        row = db.execute(
            'SELECT r.payload,r.revision,r.decision FROM chains c JOIN runs r '
            'ON r.id=c.current_id ORDER BY c.updated_seq DESC LIMIT 1').fetchone()
        if row is None:
            row = db.execute(
                'SELECT payload,revision,decision FROM runs ORDER BY rowid DESC LIMIT 1'
            ).fetchone()
        return {**json.loads(row['payload']), 'revision': row['revision'],
                'decision': row['decision']} if row else None


def history():
    with connection() as db:
        return [dict(r) for r in db.execute(
            'SELECT id,chain_id,parent_id,revision_no,revision,decision,created_seq '
            'FROM runs ORDER BY created_seq DESC')]


def review(ident, revision, decision):
    if decision not in ('通过', '退回'):
        raise DomainError('DECISION', '复核动作无效')
    with connection() as db:
        changed = db.execute(
            'UPDATE runs SET revision=revision+1,decision=? WHERE id=? AND revision=?',
            (decision, ident, revision)).rowcount
        if not changed:
            raise DomainError('VERSION', '版本已变化，请重新载入', 409)
    return {'revision': revision + 1, 'decision': decision}


def find_chain_by_key(chain_key):
    with connection() as db:
        row = db.execute('SELECT * FROM chains WHERE chain_key=? ORDER BY updated_seq DESC',
                         (chain_key,)).fetchone()
        return dict(row) if row else None


def chain_detail(chain_id):
    with connection() as db:
        chain = db.execute('SELECT * FROM chains WHERE chain_id=?', (chain_id,)).fetchone()
        if chain is None:
            raise DomainError('NOT_FOUND', '修订链不存在', 404)
        runs = [dict(r) for r in db.execute(
            'SELECT id,parent_id,revision_no,revision,decision,created_seq FROM runs '
            'WHERE chain_id=? ORDER BY revision_no', (chain_id,))]
        return {'chain_id': chain_id, 'chain_key': chain['chain_key'],
                'current_id': chain['current_id'], 'runs': runs}


def activate(ident):
    with connection() as db:
        row = db.execute('SELECT chain_id FROM runs WHERE id=?', (ident,)).fetchone()
        if row is None:
            raise DomainError('NOT_FOUND', '批次不存在', 404)
        if row['chain_id'] is None:
            raise DomainError('CHAIN', '该批次不属于任何修订链', 409)
        seq = _next_seq(db)
        changed = db.execute(
            'UPDATE chains SET current_id=?,updated_seq=? WHERE chain_id=?',
            (ident, seq, row['chain_id'])).rowcount
        if not changed:
            raise DomainError('CHAIN', '修订链不存在', 409)
    return chain_detail(row['chain_id'])
