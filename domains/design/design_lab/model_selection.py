# SPDX-License-Identifier: MIT
"""Per-project record of the operator choosing a model, or declining to.

The owner un-locked model choice on 2026-10-20 (「不锁死 做好菜单导航和接口
用户自行选择本地或者是云端模型」). Listing candidates without remembering a decision makes the user
re-choose on every request, which is the same lock with a friendlier face; this module is the
difference between "you may pick" and "your pick is recorded and read back".

What a row is: one act of choosing, by a named actor, at a revision. What it is not: a
qualification, a licence, a run, or a delivery. ``readiness/model_radar.py`` keeps the fail-closed
rules about what may default-enable, and nothing here can move them -- the catalogue facts copied
into ``snapshot`` are copied from the row this service validated the ``model_id`` against, so a
caller cannot assert its own readiness by naming a model.

The three states a reader has to be able to tell apart, and this module refuses to collapse:

* ``CHOSEN`` -- a model was picked, with the catalogue's facts at that moment;
* ``DECLINED`` -- the operator explicitly chose not to use a model (``declared_unused``), which is
  a decision, not a missing answer;
* ``NEVER_ASKED`` -- no row exists, so nobody has been asked yet. Reporting that as a declination
  would put words in the operator's mouth.

Append-only by the store's own triggers: changing one's mind appends ``revision + 1``. "Current" is
MAX(revision) computed at read time -- this repository's ACTIVE-version invariant says a mutable
``active`` flag is how a second truth source gets born, so there is none here.
"""
from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3

from .interop import InteropError, load_schema, schema_errors
from .model_catalog import catalog
from .runtime.state_resources import repo_resource, state_schema

SELECTION_VERSION = 'design-lab/model-selection/v1'
READBACK_VERSION = 'design-lab/model-selection-readback/v1'
SCHEMA_PATH = repo_resource('schemas/model-selection-v1.schema.json')
_STATE = state_schema('design-lab-state-model-selection-v1.sql')

ACTOR_KINDS = ('human', 'agent')
STATES = ('CHOSEN', 'DECLINED', 'NEVER_ASKED')

CLAIMS_NOT_MADE = (
    'this row records a choice; it does not qualify, license or endorse the model',
    'no model was loaded, no inference ran and nothing was sent when this choice was recorded',
    'the snapshot is what the catalogue said at that moment, not what it says now',
    'a later revision supersedes this choice for future reads but does not undo anything this '
    'choice was already used for',
)


class ModelSelectionError(ValueError):
    """A refusal with the status and machine-readable code the route answers with."""

    def __init__(self, status, code, detail=None):
        super().__init__(detail or code)
        self.status = status
        self.code = code
        self.detail = detail


def connect(db_path, *, project_root=None) -> sqlite3.Connection:
    """Open the shared state database with the selection table present.

    The asset store owns the path policy and the earlier migrations; re-applying them here would be
    a second implementation of the same migration (``research_store``, ``rights_ledger`` precedent).
    """
    from .runtime.asset_store import connect as connect_assets

    connection = connect_assets(db_path, project_root=project_root)
    connection.row_factory = sqlite3.Row
    connection.executescript(_STATE.read_text(encoding='utf-8'))
    connection.commit()
    return connection


def _canonical(document) -> str:
    return json.dumps(document, ensure_ascii=False, sort_keys=True)


def _check(document):
    """Refuse to store a selection document its own contract would reject.

    Every field is written here, so a mismatch means code and contract diverged -- a renamed key, a
    snapshot that came along on a declination, a qualification word that crept in.
    """
    try:
        problems = schema_errors(load_schema(SCHEMA_PATH), document)
    except (InteropError, OSError) as exc:
        raise ModelSelectionError(500, 'MODEL_SELECTION_CONTRACT_UNREADABLE',
                                  f'cannot load {SCHEMA_PATH.name}: {exc}') from None
    if problems:
        raise ModelSelectionError(500, 'MODEL_SELECTION_CONTRACT_VIOLATION', problems)
    return document


def _catalogue_row(model_id):
    """The catalogue's own row for this model, or None. Never a caller-supplied substitute."""
    try:
        document = catalog()
    except Exception as exc:                              # readiness refuses, and that is the answer
        raise ModelSelectionError(503, 'MODEL_CATALOG_UNAVAILABLE', str(exc)) from None
    row = next((row for row in document['models'] if row['model_id'] == model_id), None)
    return row, document


class ModelSelection:
    def __init__(self, service):
        self.service = service
        self.paths = service.paths

    def _connect(self):
        return connect(self.paths.database_path(self.service.database),
                       project_root=self.paths.project_root)

    def _check_project(self, project_id):
        if self.service.get_project(project_id) is None:
            raise ModelSelectionError(404, 'PROJECT_NOT_FOUND')

    def record(self, project_id, *, model_id=None, declared_unused=False, actor, actor_kind):
        """Append the next revision of this project's choice, or replay the identical one."""
        self._check_project(project_id)
        if actor_kind not in ACTOR_KINDS:
            raise ModelSelectionError(400, 'INVALID_ACTOR_KIND',
                                      f'actor_kind must be one of {", ".join(ACTOR_KINDS)}')
        if not isinstance(actor, str) or not actor.strip():
            raise ModelSelectionError(400, 'ACTOR_REQUIRED',
                                      'a choice must name who made it; an unattributed selection '
                                      'is not a decision anyone can read back')
        if bool(declared_unused) and model_id:
            raise ModelSelectionError(400, 'MODEL_SELECTION_CONFLICT',
                                      'declared_unused and model_id cannot both be set: pick a '
                                      'model or decline, this service will not guess which')
        if not declared_unused and not model_id:
            raise ModelSelectionError(
                400, 'MODEL_SELECTION_REQUIRED',
                'name a model_id, or send declared_unused true to record an explicit "not used". '
                'An absent answer is not the same fact as a declination.')

        snapshot = None
        if not declared_unused:
            row, _document = _catalogue_row(model_id)
            if row is None:
                raise ModelSelectionError(
                    404, 'MODEL_NOT_IN_CATALOGUE',
                    f'{model_id!r} is not a candidate in GET /api/models; a choice can only be '
                    'made from what the registries actually record')
            snapshot = {'placement': row['placement'], 'radar_state': row['radar_state'],
                        'machine_state': row['machine_state'],
                        'commercial_use': row['commercial_use'],
                        'weights_recorded': row['weights_recorded'],
                        'qualified_local': row['radar_state'] == 'QUALIFIED_LOCAL'}

        with closing(self._connect()) as conn:
            current = conn.execute(
                'SELECT revision, document_json FROM model_selection WHERE project_id=?'
                ' ORDER BY revision DESC LIMIT 1', (project_id,)).fetchone()
            if current is not None:
                stored = json.loads(current['document_json'])
                if stored.get('model_id') == (None if declared_unused else model_id):
                    # The same answer again is a replay, not a second decision: appending a new
                    # revision for every page load would bury the decision path in no-ops.
                    return {'status': 'MODEL_SELECTION', 'selection': stored,
                            'replayed': True, 'revision_count': current['revision'],
                            'state': 'DECLINED' if stored['declared_unused'] else 'CHOSEN',
                            'claims_not_made': list(CLAIMS_NOT_MADE)}
            revision = 0 if current is None else current['revision']
            document = _check({
                'schemaVersion': SELECTION_VERSION,
                'project_id': project_id,
                'revision': revision + 1,
                'model_id': None if declared_unused else model_id,
                'declared_unused': bool(declared_unused),
                'snapshot': snapshot,
                'actor': actor.strip(),
                'actor_kind': actor_kind,
                'recorded_at': _now(),
                'claims_not_made': list(CLAIMS_NOT_MADE),
            })
            try:
                conn.execute(
                    'INSERT INTO model_selection (project_id, revision, model_id, declared_unused,'
                    ' placement, radar_state, machine_state, commercial_use, weights_recorded,'
                    ' qualified_local_at_choice, actor, actor_kind, recorded_at, document_json)'
                    ' VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (project_id, document['revision'], document['model_id'],
                     1 if document['declared_unused'] else 0,
                     None if snapshot is None else snapshot['placement'],
                     None if snapshot is None else snapshot['radar_state'],
                     None if snapshot is None else snapshot['machine_state'],
                     None if snapshot is None else snapshot['commercial_use'],
                     None if snapshot is None else snapshot['weights_recorded'],
                     1 if (snapshot or {}).get('qualified_local') else 0,
                     document['actor'], document['actor_kind'], document['recorded_at'],
                     _canonical(document)))
                conn.commit()
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                raise ModelSelectionError(409, 'MODEL_SELECTION_CONCURRENT_UPDATE',
                                          f'{type(exc).__name__}: {exc}') from None
        return {'status': 'MODEL_SELECTION', 'selection': document, 'replayed': False,
                'revision_count': document['revision'],
                'state': 'DECLINED' if document['declared_unused'] else 'CHOSEN',
                'claims_not_made': list(CLAIMS_NOT_MADE)}

    def readback(self, project_id) -> dict:
        """The current choice, the decision path, and the three states kept apart."""
        self._check_project(project_id)
        with closing(self._connect()) as conn:
            rows = conn.execute(
                'SELECT revision, declared_unused, document_json FROM model_selection'
                ' WHERE project_id=? ORDER BY revision', (project_id,)).fetchall()
        unreadable = 0
        history = []
        for row in rows:
            try:
                history.append(json.loads(row['document_json']))
            except (TypeError, ValueError):
                unreadable += 1
        current = history[-1] if history else None
        state = ('NEVER_ASKED' if current is None
                 else 'DECLINED' if current['declared_unused'] else 'CHOSEN')
        return {
            'schemaVersion': READBACK_VERSION,
            'project_id': project_id,
            'state': state,
            'selection': current,
            'revision_count': len(rows),
            'unreadable_count': unreadable,
            'history': history,
            'claims_not_made': list(CLAIMS_NOT_MADE),
            'does_not_say': [
                'NEVER_ASKED 不等于"已决定不使用"：前者没人被问过，后者是操作者的显式选择。',
                'CHOSEN 只是选择被记下：没有加载模型、没有推理、没有发送，也没有任何资格判定。',
                'snapshot 是选择当时目录的说法；目录今天怎么说是 GET /api/models 的事，两者可以不同。',
            ],
        }


def _now() -> str:
    from .assurance import utc_now_rfc3339

    return utc_now_rfc3339()
