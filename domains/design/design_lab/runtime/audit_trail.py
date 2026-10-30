# SPDX-License-Identifier: MIT
"""Read back the writer journal that the asset store has always written.

``audit_event`` was written in two places -- an asset version created under an attempt, and a
``writer_takeover`` -- and read by nothing in the product. A journal nobody can read is not an
audit trail: it looks like one in the schema and answers no question at runtime. The takeover
row is the one that matters most. ``takeover_writer`` deliberately increments the generation
and hands a resource to a new holder, which is how a stalled or crashed holder stops blocking
a project; after it happens, the operator's next question is "who took what over, and when",
and today the only way to ask is to open SQLite by hand.

Read-only by construction: the connection is opened ``mode=ro``, so this module cannot be the
place where a journal quietly gains a writer.

The ``actor`` column holds an attempt id, not a person. Nothing here turns it into a name:
an identity claim the stored bytes cannot support would be exactly the false green the rest of
this project is built to refuse.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

WRITTEN_ACTIONS = ('asset_version_created', 'writer_takeover')


def connect(service):
    """A read-only connection to the project's state database, through its own path policy."""
    path = service.paths.database_path(service.database)
    if not Path(path).exists():
        return None
    return sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)


def _rows(conn, limit, after_at, after_id):
    """Journal rows newest-first.

    The cursor is the pair (at, audit_id) and the comparison is a row-value comparison,
    because ordering by a timestamp alone can put two same-microsecond rows in either order:
    a count-based page would then repeat or skip a row while somebody is reading it.
    """
    if after_at:
        return conn.execute(
            'SELECT audit_id, actor, action, at FROM audit_event'
            ' WHERE (at, audit_id) < (?, ?) ORDER BY at DESC, audit_id DESC LIMIT ?',
            (after_at, after_id, limit + 1)).fetchall()
    return conn.execute(
        'SELECT audit_id, actor, action, at FROM audit_event'
        ' ORDER BY at DESC, audit_id DESC LIMIT ?', (limit + 1,)).fetchall()


def recent(service, *, limit: int = 50, after_at: str = '', after_id: str = '',
           action: str | None = None) -> dict:
    """Return the journal, or an explicit statement that it was never written."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
        raise ValueError('limit must be an integer from 1 to 200')
    if action is not None and action not in WRITTEN_ACTIONS:
        raise ValueError(f'action must be one of {", ".join(WRITTEN_ACTIONS)} or omitted')
    conn = connect(service)
    if conn is None:
        return {'status': 'NO_STATE_DATABASE', 'events': [], 'counts': {},
                'meaning': '该项目还没有状态库,因此没有任何写入记录可读回;这不代表写入过零事件。'}
    try:
        conn.row_factory = sqlite3.Row
        rows = _rows(conn, limit, after_at, after_id)
    except sqlite3.Error as exc:
        raise RuntimeError(f'audit journal cannot be read: {exc}') from None
    try:
        if not rows:
            return {'status': 'EMPTY', 'events': [], 'counts': {},
                    'meaning': '状态库里没有 journal 行:资产写入与写者接管都未在此发生过。'}
        events = [dict(audit_id=r['audit_id'], actor=r['actor'], action=r['action'],
                       at=r['at'], kind=r['action'].split(':', 1)[0]) for r in rows[:limit]]
        if action is not None:
            events = [e for e in events if e['kind'] == action]
        counts = {}
        for event in events:
            counts[event['kind']] = counts.get(event['kind'], 0) + 1
        last = rows[min(limit, len(rows)) - 1]
        return {'status': 'PRESENT', 'events': events, 'counts': counts,
                'next_cursor': ({'after_at': last['at'], 'after_id': last['audit_id']}
                                if len(rows) > limit else None),
                'meaning': ('actor 是尝试 id,不是人名:这里不把它翻译成任何身份。'
                            'writer_takeover 表示写者租约被显式接管(generation 递增),'
                            'asset_version_created 表示某次尝试产出了一个版本。'),
                'written_actions': list(WRITTEN_ACTIONS)}
    finally:
        conn.close()
