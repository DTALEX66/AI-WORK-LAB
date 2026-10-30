# SPDX-License-Identifier: MIT
"""Read-only projection of the native runtime tables for one project (DL-UI-U06).

`native_tasks.py` already keeps the facts U06's acceptance names: which host is currently
occupied by which attempt (`native_host_guard_v1`), whether an attempt reached quiescence and
got a receipt (`native_quiescence_v1`), whether a reconciliation is open
(`native_reconciliation_v1`), and which recovery protocol was recorded
(`native_recovery_protocol_v2`). None of that was reachable over HTTP -- `http_service.py`
dispatches the *actions* (`run` / `cancel` / `patch` / `bundle`) and no route projected the
state those actions leave behind, so the workbench could show a job's status word but not
whether Photoshop was currently held by it.

This façade is the observation half of that, and it is deliberately read-only:

* It opens the database `mode=ro`. Creating tables is `native_tasks._connect`'s job; a reader
  that silently created a table would report "nothing occupied" for a database that was never
  written, which is the exact failure this file exists to avoid.
* A table that does not exist yet is reported as `ABSENT` with a row count of `None`, and is
  kept apart from an existing-but-empty table (`EMPTY`, count 0). "No attempt holds the host"
  and "this service has never run a native attempt" are different sentences.
* **No verdict word is invented.** There is no `RUNTIME_HEALTHY`, no `SAFE_TO_RETRY`, no
  `IDLE`: a guard row that exists says a host is held, and says nothing about whether waiting
  is the right thing to do. `proves_production_ready` and `is_host_action_performed` are
  `False`, and `budget` is `null` with the reason, because no table in this repository carries
  a budget or quota concept -- the UI must show "无该字段" rather than a zero.
"""
from __future__ import annotations

import sqlite3

_READBACK_VERSION = 'design-lab/native-runtime-readback/v1'

#: The tables this projection reads, in the order a reader meets them on screen.
_TABLES = ('native_host_guard_v1', 'native_quiescence_v1', 'native_reconciliation_v1',
           'native_recovery_protocol_v2', 'native_execution_v1')

_NO_BUDGET_NOTE = (
    'no table in this repository records a run budget, quota or cost for a native attempt, '
    'so this surface publishes null instead of a zero: 0 would read as "budget available"')


class NativeRuntimeError(ValueError):
    """The runtime read-back was refused. ``status``/``code``/``detail`` stay separate so an
    operator can tell an unknown project from an unreadable database."""

    def __init__(self, status, code, detail=None):
        self.status, self.code, self.detail = status, code, detail


def _tables_present(conn) -> dict[str, bool]:
    have = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return {name: name in have for name in _TABLES}


def readback(service, project_id: str) -> dict:
    """The runtime observation envelope for one project, from what is actually stored."""
    if service.get_project(project_id) is None:
        raise NativeRuntimeError(404, 'PROJECT_NOT_FOUND',
                                 f'project {project_id!r} is not recorded here')
    path = service.paths.database_path(service.database)
    conn = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    try:
        present = _tables_present(conn)
        guard = ([dict(row) for row in conn.execute(
            'SELECT host, attempt_id, acquired_at FROM native_host_guard_v1')]
            if present['native_host_guard_v1'] else None)
        quiescence = ([dict(row) for row in conn.execute(
            'SELECT attempt_id, started_at, receipt_json FROM native_quiescence_v1')]
            if present['native_quiescence_v1'] else None)
        reconciliation = ([dict(row) for row in conn.execute(
            'SELECT attempt_id, started_at FROM native_reconciliation_v1')]
            if present['native_reconciliation_v1'] else None)
        recovery = ([dict(row) for row in conn.execute(
            'SELECT attempt_id, protocol FROM native_recovery_protocol_v2')]
            if present['native_recovery_protocol_v2'] else None)
        executions = ([dict(row) for row in conn.execute(
            'SELECT attempt_id, host, receipt_json, result_json FROM native_execution_v1 '
            'WHERE project_id=?', (project_id,))]
            if present['native_execution_v1'] else None)
    except sqlite3.Error as exc:
        raise NativeRuntimeError(503, 'NATIVE_RUNTIME_UNREADABLE',
                                 f'the state database refused the read: {exc}') from None
    finally:
        conn.close()

    def state(rows):
        return {'table': 'ABSENT', 'rows': None} if rows is None else \
            {'table': 'PRESENT', 'rows': rows}

    receipts = [r for r in (executions or []) if r.get('receipt_json')]
    results = [r for r in (executions or []) if r.get('result_json')]
    receipted_quiescence = [r for r in (quiescence or []) if r.get('receipt_json')]
    return {
        'schemaVersion': _READBACK_VERSION,
        'project_id': project_id,
        'host_guard': state(guard),
        'quiescence': state(quiescence),
        'reconciliation': state(reconciliation),
        'recovery_protocol': state(recovery),
        'executions': state(executions),
        # Counts a page can print without re-deriving them, and each one is a count of rows
        # this function actually read -- never a count of what a healthy system would have.
        'counts': {
            'hosts_held': len(guard) if guard is not None else None,
            'attempts_quiescent_receipted': (len(receipted_quiescence) if quiescence is not None
                                             else None),
            'reconciliations_open': (len(reconciliation) if reconciliation is not None else None),
            'executions_receipted': len(receipts) if executions is not None else None,
            'executions_with_result': len(results) if executions is not None else None,
        },
        'budget': None,
        'budget_reason': _NO_BUDGET_NOTE,
        'proves_production_ready': False,
        'is_host_action_performed': False,
        'does_not_say': [
            'a held guard row says a host is occupied by an attempt, not that waiting is right',
            'an absent table means no native attempt was ever recorded here, not an idle host',
            'a reconciliation row means one was opened, not that it found or fixed anything',
        ],
    }
