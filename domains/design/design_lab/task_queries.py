# SPDX-License-Identifier: MIT
"""Read-only, project-scoped projections of service-owned import/native attempts.

No receipts, request bodies, notes, keys or arbitrary adapter details are exposed.
These are stored observations, not fresh artifact validation or host acceptance.

The three reads share one envelope version since 2026-10-22 (backend D) because the Stitch design's
D08 needs three things no caller could previously get from the payload alone: which state words the
service can emit at all (so a page never hardcodes a list it invented), whether the page it got is
the whole answer (the read caps itself at 100 and hands back a cursor), and what
``cancel.acknowledged`` actually asserts. The vocabulary is read from the one file that owns it --
``design-lab/config/state-vocabularies.json``, guarded by
``design-lab/scripts/verify_state_vocabularies.py`` -- and is never re-typed here.
"""
from contextlib import closing
import functools
import json
import sqlite3

from .image_assets import ImageAssetError
from .interop import InteropError, load_schema, schema_errors
from .runtime.state_resources import repo_resource

TASK_READBACK_VERSION = 'design-lab/task-readback/v1'
#: The list and event pages stop here; `truncated` and `next_cursor` are computed from the same
#: expression, so a payload cannot claim "the end" while still holding a cursor.
PAGE_LIMIT = 100
VOCABULARY_FILE = 'design-lab/config/state-vocabularies.json'
#: Both files are read through ``repo_resource`` rather than ``PROJECT_ROOT``: three levels above an
#: installed ``site-packages/design_lab/runtime`` is the interpreter's own ``Lib``, so a
#: ``PROJECT_ROOT`` read answers "the bytes are not here" on a wheel and the route 500s. That is the
#: same D09 defect the research and rights contracts already hit. ``design-lab/tests/
#: test_packaged_contract_resources.py`` refuses a call site pyproject no longer declares.
SCHEMA_PATH = repo_resource('schemas/task-readback-v1.schema.json')

CANCEL_MEANING = (
    'cancel.requested 是操作者按过取消；cancel.acknowledged 是适配层确认了那次取消'
    '（job_store.acknowledge_cancel 在 CANCEL_REQUESTED 上置位，native_tasks 在派发前被拒的'
    '取消路径也置位）。两者都不说宿主已经停下，也不说产物已核对——确认之后状态转 RECONCILING，'
    '代码里的原话是 "adapter acknowledged cancellation; readback still required"。')

DOES_NOT_SAY = (
    '这里的 state 与 updated_at 是这台服务此刻存着的观测，不是刚去宿主问过；宿主已经不在，'
    '记录也不会因此自己变绿。',
    'truncated=false 且 next_cursor=null 才表示这一项目前就这些任务；空列表还要求 stateVocabulary '
    '照旧给出，页面不能把"没读到"降格成"没有"。',
    CANCEL_MEANING,
)


class TaskReadbackError(ValueError):
    """This read cannot be answered honestly; the route carries the code and the detail.

    A refusal is named rather than degraded: a task page that receives no vocabulary would fall back
    to the words it remembered from an earlier build, and a payload that contradicts its own envelope
    is exactly the kind of answer a reviewer then trusts.
    """

    def __init__(self, status, code, detail):
        super().__init__(detail)
        self.status, self.code = status, code


@functools.lru_cache(maxsize=1)
def state_vocabulary() -> dict:
    """The attempt-state words, read from the file that owns them.

    An unreadable vocabulary is a refusal rather than a silently absent list: a page that receives
    no words would fall back to whatever it remembered from an earlier build.
    """
    try:
        document = json.loads(repo_resource('config/state-vocabularies.json')
                              .read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise TaskReadbackError(503, 'TASK_VOCABULARY_UNREADABLE',
                                f'{VOCABULARY_FILE} cannot be read: {type(exc).__name__}') from None
    attempt = document.get('attemptStates')
    if not isinstance(attempt, dict) or not isinstance(attempt.get('all'), list):
        raise TaskReadbackError(503, 'TASK_VOCABULARY_INCOMPLETE',
                                f'{VOCABULARY_FILE} declares no attemptStates.all list')
    return {'attemptStates': {key: attempt[key] for key in
                              ('all', 'terminal', 'failed', 'needsHuman', 'inFlight', 'done')
                              if key in attempt},
            'operationStates': {
                # Said out loud rather than papered over: the operation-level words exist only as
                # literals at the write sites, so a page must render what the read reports and not
                # assume a closed list it was never given.
                'owner': 'src/design_lab/runtime/job_store.py',
                'declaredAs': 'inline literals at the _op() write sites; no named set exists',
                'observedInThisPage': None},
            'vocabularyFile': VOCABULARY_FILE}


def _guard(envelope: dict) -> dict:
    """Refuse to answer with a payload that contradicts its own envelope contract."""
    try:
        problems = schema_errors(load_schema(SCHEMA_PATH), envelope)
    except InteropError as exc:
        raise TaskReadbackError(500, 'TASK_READBACK_CONTRACT_UNAVAILABLE',
                                f'{TASK_READBACK_VERSION} contract cannot be applied: '
                                f'{exc}') from None
    if problems:
        raise TaskReadbackError(
            500, 'TASK_READBACK_CONTRACT_VIOLATION',
            f'{TASK_READBACK_VERSION} violated by its own read: '
            + json.dumps(problems[:3], ensure_ascii=False))
    return envelope


def _envelope(surface: str, payload: dict, *, truncated: bool, cursor,
              states, count: int) -> dict:
    """Wrap one of the three reads in the shared envelope.

    ``truncated`` and ``next_cursor`` are decided by the caller from one comparison, so a payload
    cannot say "this is the end" while still handing back a cursor.
    """
    vocabulary = json.loads(json.dumps(state_vocabulary()))
    vocabulary['operationStates']['observedInThisPage'] = sorted(set(states))
    return _guard({'schemaVersion': TASK_READBACK_VERSION, 'surface': surface,
                   'limit': PAGE_LIMIT, 'truncated': truncated, 'next_cursor': cursor,
                   'stateVocabulary': vocabulary, 'count': count,
                   **payload, 'does_not_say': list(DOES_NOT_SAY)})


class TaskQueries:
    def __init__(self, service):
        self.service = service

    def _connect(self, project_id):
        if self.service.get_project(project_id) is None:
            raise ImageAssetError(404, 'PROJECT_NOT_FOUND')
        path = self.service.paths.database_path(self.service.database)
        conn = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute('BEGIN')
        return conn

    @staticmethod
    def _ready(conn):
        if conn.execute("SELECT 1 FROM runtime_migration WHERE name='attempt-v2'").fetchone():
            return True
        # A newly created project has no attempts yet. Do not migrate on GET.
        if conn.execute('SELECT 1 FROM job LIMIT 1').fetchone():
            raise ImageAssetError(503, 'TASK_SCHEMA_UNQUALIFIED')
        return False

    @staticmethod
    def _rows(conn, project_id, job_id=None, after=''):
        return conn.execute(
            'SELECT j.job_id,j.operation_id,o.state,o.updated_at,i.idempotency_scope,'
            'a.attempt_id,a.attempt_no,a.state AS attempt_state,a.started_at,a.ended_at,'
            # The cancel flags travel with the attempt so a reader can tell "nobody asked"
            # from "the operator asked and the host delivered anyway". COALESCE because a
            # pre-v2 attempt can have no resolution row at all.
            "COALESCE(r.cancel_requested,0) AS cancel_requested,"
            'COALESCE(r.cancel_acked,0) AS cancel_acked '
            'FROM job j JOIN operation_intent i ON i.operation_id=j.operation_id '
            'JOIN operation_state o ON o.operation_id=j.operation_id '
            'JOIN attempt_state a ON a.job_id=j.job_id '
            'LEFT JOIN attempt_resolution r ON r.attempt_id=a.attempt_id '
            'WHERE i.idempotency_scope IN (?,?,?) AND (? IS NULL OR j.job_id=?) AND j.job_id>? '
            'AND a.attempt_no=(SELECT MAX(b.attempt_no) FROM attempt_state b WHERE b.job_id=j.job_id) '
            f'ORDER BY j.job_id LIMIT {PAGE_LIMIT + 1}',
            ('image-import:' + project_id, 'native:'+project_id+':photoshop',
             'native:'+project_id+':illustrator', job_id, job_id, after)).fetchall()

    @staticmethod
    def _task(row):
        return {'job_id': row['job_id'], 'operation_id': row['operation_id'],
                'kind': ('image-import' if row['idempotency_scope'].startswith('image-import:')
                         else row['idempotency_scope'].rsplit(':',1)[1]+'-native'),
                'state': row['state'], 'updated_at': row['updated_at'],
                'cancel': {'requested': bool(row['cancel_requested']),
                           'acknowledged': bool(row['cancel_acked'])},
                'attempt': {'attempt_id': row['attempt_id'], 'attempt_no': row['attempt_no'],
                            'state': row['attempt_state'], 'started_at': row['started_at'],
                            'ended_at': row['ended_at']}}

    def list(self, project_id, after=''):
        with closing(self._connect(project_id)) as conn:
            rows = self._rows(conn, project_id, after=after) if self._ready(conn) else []
        page = rows[:PAGE_LIMIT]
        return _envelope('list', {'tasks': [self._task(row) for row in page]},
                         truncated=len(rows) > PAGE_LIMIT,
                         cursor=page[-1]['job_id'] if len(rows) > PAGE_LIMIT else None,
                         states=[row['state'] for row in page], count=len(page))

    def get(self, project_id, job_id):
        with closing(self._connect(project_id)) as conn:
            rows = self._rows(conn, project_id, job_id) if self._ready(conn) else []
            if len(rows) != 1:
                raise ImageAssetError(404, 'TASK_NOT_FOUND')
            return _envelope('task', {'task': self._task(rows[0])}, truncated=False, cursor=None,
                             states=[rows[0]['state']], count=1)

    def events(self, project_id, job_id, after=0):
        with closing(self._connect(project_id)) as conn:
            if not self._ready(conn) or len(self._rows(conn, project_id, job_id)) != 1:
                raise ImageAssetError(404, 'TASK_NOT_FOUND')
            rows = conn.execute(
                'SELECT e.event_no,e.attempt_id,a.attempt_no,e.from_state,e.to_state,e.at '
                'FROM attempt_event e JOIN attempt_state a ON a.attempt_id=e.attempt_id '
                f'WHERE a.job_id=? AND e.event_no>? ORDER BY e.event_no LIMIT {PAGE_LIMIT + 1}',
                (job_id, after)).fetchall()
        page = rows[:PAGE_LIMIT]
        return _envelope('events', {'events': [dict(row) for row in page]},
                         truncated=len(rows) > PAGE_LIMIT,
                         cursor=page[-1]['event_no'] if len(rows) > PAGE_LIMIT else None,
                         states=[row['to_state'] for row in page], count=len(page))
