# SPDX-License-Identifier: MIT
"""Voluntary external-use feedback on an assistance plan (DL-KB-16).

The closed loop the owner defined ends with 「用户自愿记录外部使用反馈」: someone takes a plan's
material to an external tool, comes back, and says what happened. This module is that statement.

It is kept deliberately separate from the plan's four readback states, because the four states and
this record answer different questions:

* ``saved`` / ``provided`` / ``chosen`` are computed from what this service stored and who adopted
  it, and ``externally_verified`` is a constant false because no route here dispatches an external
  step. Recording feedback touches none of them -- there is no column that could, and the readback
  still says 外部未验证 after a person reports the material worked.
* a feedback row is a **person's report of an external outcome**. "It produced a usable take" is
  not "the system verified the run", and the two verbs are never merged into one status field.

Three outcome words only (``USABLE`` / ``PARTIAL`` / ``NOT_USABLE``), declared in
``design-lab/config/state-vocabularies.json`` and checked against this emitter in both directions by
``verify_state_vocabularies.py`` -- the screen does not hand-copy them. Absence of a record means
"not recorded"; there is no ``UNKNOWN`` outcome word, because a person who does not want to report
should not have to file a statement to make the panel honest.

``actor_kind`` is pinned to ``human`` by the table's CHECK, and an absent external identifier stays
the literal ``UNUSED``: this module mints no external job id and never presents a self-authored one
as provenance.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing

from .assurance import utc_now_rfc3339
from .interop import InteropError, load_schema, resource_registry, schema_errors
from .runtime.state_resources import repo_resource, state_schema

FEEDBACK_VERSION = 'design-lab/plan-feedback/v1'
WRITE_VERSION = 'design-lab/plan-feedback-write/v1'
LIST_VERSION = 'design-lab/plan-feedback-list/v1'

_SCHEMA_PATH = repo_resource('schemas/plan-feedback-v1.schema.json')
_WRITE_SCHEMA_PATH = repo_resource('schemas/plan-feedback-write-v1.schema.json')
_LIST_SCHEMA_PATH = repo_resource('schemas/plan-feedback-list-v1.schema.json')
_STATE = state_schema('design-lab-state-plan-feedback-v1.sql')

#: The whole-record outcome words. Anything else -- "sent", "delivered", "deployed" -- is not an
#: outcome this service is allowed to recognise, because it cannot observe those verbs. The labels
#: are the card's own words (「符合/部分符合/不符合」), and both lists are declared in
#: design-lab/config/state-vocabularies.json and checked back against this emitter.
OUTCOMES = ('MATCHES', 'PARTIALLY_MATCHES', 'DOES_NOT_MATCH')
OUTCOME_LABELS = {'MATCHES': '符合', 'PARTIALLY_MATCHES': '部分符合', 'DOES_NOT_MATCH': '不符合'}
#: A 维度结论 names one thing about the material and says how it turned out. The dimension itself
#: is the reporter's words (画幅 / 时长 / 品牌色 / 参考角色 ...), because a fixed list here would be
#: this service inventing which axes a plan cares about; the verdict is closed.
DIMENSION_VERDICTS = ('MATCHES', 'PARTIALLY_MATCHES', 'DOES_NOT_MATCH')
DIMENSION_VERDICT_LABELS = {'MATCHES': '符合', 'PARTIALLY_MATCHES': '部分符合',
                             'DOES_NOT_MATCH': '不符合'}
MAX_DIMENSIONS = 12
MAX_TIMECODES = 12
UNUSED = 'UNUSED'
DEFAULT_LIMIT = 20
MAX_LIMIT = 100

#: Printed with every answer. The last clause is the one a reader most often gets wrong: a
#: satisfied report is still somebody's word, not a verification.
DOES_NOT_SAY = (
    '本记录不证明外部工具运行过：服务没有发送通道，也不核验外部结果。',
    '记录反馈不会把方案的「外部未验证」状态改成已验证，也不会改变已保存/已提供/已选用。',
    '「可用」是使用者的自愿陈述，不是系统核验通过，更不是可执行性的合格判定。',
)


class PlanFeedbackError(ValueError):
    def __init__(self, status, code, detail=None):
        super().__init__(f'{code}: {detail}' if detail else code)
        self.status = status
        self.code = code
        self.detail = detail


def connect(db_path, *, project_root=None) -> sqlite3.Connection:
    from . import assistance_plan as plan_store
    try:
        connection = plan_store.connect(db_path, project_root=project_root)
    except plan_store.AssistancePlanError as exc:
        raise PlanFeedbackError(exc.status, 'PLAN_FEEDBACK_STATE_UNAVAILABLE',
                                exc.detail) from None
    connection.executescript(_STATE.read_text(encoding='utf-8'))
    connection.commit()
    return connection


def _canonical(document) -> str:
    return json.dumps(document, ensure_ascii=False, sort_keys=True)


def _digest(document) -> str:
    return 'sha256:' + hashlib.sha256(_canonical(document).encode('utf-8')).hexdigest()


_registry = None


def _ref_registry():
    """The feedback record, registered by its own $id so one schema owns the shape.

    The write and list answers $ref it instead of restating the record: two copies of one contract
    is how they start disagreeing, and the offline registry means a $ref can never reach the network.
    """
    global _registry
    if _registry is None:
        try:
            document = load_schema(_SCHEMA_PATH)
        except (InteropError, OSError) as exc:
            raise PlanFeedbackError(
                500, 'PLAN_FEEDBACK_CONTRACT_UNREADABLE',
                f'cannot load {_SCHEMA_PATH.name} for $ref resolution: {exc}') from None
        identifier = document.get('$id')
        if not isinstance(identifier, str):
            raise PlanFeedbackError(
                500, 'PLAN_FEEDBACK_CONTRACT_UNREADABLE',
                f'{_SCHEMA_PATH.name} carries no $id, so a $ref into it cannot be resolved offline')
        _registry = resource_registry({identifier: document})
    return _registry


def _check(document, path, label, *, registry=None):
    try:
        problems = schema_errors(load_schema(path), document, registry=registry)
    except (InteropError, OSError) as exc:
        raise PlanFeedbackError(500, 'PLAN_FEEDBACK_CONTRACT_UNREADABLE',
                                f'cannot load {path.name} for {label}: {exc}') from None
    if problems:
        raise PlanFeedbackError(500, 'PLAN_FEEDBACK_CONTRACT_VIOLATION', problems)
    return document


def _text(value, field, *, required=True, max_len=2000):
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise PlanFeedbackError(400, 'PLAN_FEEDBACK_FIELD_MISSING',
                                    f'{field} is required and must be a non-empty string')
        return None
    if not isinstance(value, str):
        raise PlanFeedbackError(400, 'PLAN_FEEDBACK_FIELD_MALFORMED',
                                f'{field} must be a string')
    value = value.strip()
    if len(value) > max_len:
        raise PlanFeedbackError(400, 'PLAN_FEEDBACK_FIELD_TOO_LONG',
                                f'{field} exceeds {max_len} characters')
    return value


def _dimensions(value):
    """Per-dimension verdicts: the axis is the reporter's words, the verdict is closed."""
    if value is None or value == []:
        return []
    if not isinstance(value, list):
        raise PlanFeedbackError(400, 'PLAN_FEEDBACK_DIMENSIONS_MALFORMED',
                                'dimensions must be a list of {name, verdict, note}')
    if len(value) > MAX_DIMENSIONS:
        raise PlanFeedbackError(400, 'PLAN_FEEDBACK_TOO_MANY_DIMENSIONS',
                                f'a report names at most {MAX_DIMENSIONS} dimensions')
    seen = set()
    rows = []
    for item in value:
        if not isinstance(item, dict):
            raise PlanFeedbackError(400, 'PLAN_FEEDBACK_DIMENSIONS_MALFORMED',
                                    'each dimension is an object with name and verdict')
        unexpected = sorted(set(item) - {'name', 'verdict', 'note'})
        if unexpected:
            raise PlanFeedbackError(400, 'PLAN_FEEDBACK_FIELD_NOT_IN_CONTRACT',
                                    f'dimension fields outside the contract: {unexpected}')
        name = _text(item.get('name'), 'dimension.name', max_len=120)
        verdict = item.get('verdict')
        if verdict not in DIMENSION_VERDICTS:
            raise PlanFeedbackError(
                400, 'PLAN_FEEDBACK_DIMENSION_VERDICT_INVALID',
                f'dimension {name!r} verdict must be one of {list(DIMENSION_VERDICTS)}; '
                'there is no UNKNOWN verdict here -- not naming a dimension is how you say it '
                'was not checked')
        if name in seen:
            raise PlanFeedbackError(400, 'PLAN_FEEDBACK_DIMENSION_DUPLICATED',
                                    f'dimension {name!r} is reported twice in one statement')
        seen.add(name)
        rows.append({'name': name, 'verdict': verdict,
                     'verdict_label': DIMENSION_VERDICT_LABELS[verdict],
                     'note': _text(item.get('note'), 'dimension.note', required=False,
                                   max_len=1000)})
    return rows


def _timecodes(value):
    """问题时间码: short spans the reporter saw, kept verbatim and never invented."""
    if value is None or value == []:
        return []
    if not isinstance(value, list):
        raise PlanFeedbackError(400, 'PLAN_FEEDBACK_TIMECODES_MALFORMED',
                                'issue_timecodes must be a list of short strings')
    if len(value) > MAX_TIMECODES:
        raise PlanFeedbackError(400, 'PLAN_FEEDBACK_TOO_MANY_TIMECODES',
                                f'a report names at most {MAX_TIMECODES} timecodes')
    rows = []
    for item in value:
        text = _text(item, 'issue_timecodes item', max_len=60)
        if not any(char.isdigit() for char in text):
            raise PlanFeedbackError(400, 'PLAN_FEEDBACK_TIMECODE_MALFORMED',
                                    f'{text!r} is not a timecode; a label with no digits in it '
                                    'is not a place in the material')
        rows.append(text)
    return rows


def _document(*, plan_id, revision, feedback_no, value, actor):
    outcome = value.get('outcome')
    if outcome not in OUTCOMES:
        raise PlanFeedbackError(
            400, 'PLAN_FEEDBACK_OUTCOME_INVALID',
            f'outcome must be one of {list(OUTCOMES)}; a report this service cannot observe '
            '(sent / delivered / executed) is not an outcome word here')
    source_ref = value.get('source_ref')
    if source_ref is None or not str(source_ref).strip():
        source_ref = UNUSED
    document = {
        'schemaVersion': FEEDBACK_VERSION,
        'plan_id': plan_id,
        'revision': revision,
        'feedback_no': feedback_no,
        'outcome': outcome,
        'outcome_label': OUTCOME_LABELS[outcome],
        'target_key': _text(value.get('target_key'), 'target_key'),
        # 「反馈绑定当时资料与模型版本」: the model/version the person actually used travels with the
        # record, and the material is bound through `revision`, which is what pins the reference
        # revisions and digests. Neither is inferred -- an unreported model stays null with a reason.
        'target_model': _text(value.get('target_model'), 'target_model', required=False),
        'target_model_reason': None if value.get('target_model') else '记录人没有说明当时用的模型/版本',
        'dimensions': _dimensions(value.get('dimensions')),
        'issue_timecodes': _timecodes(value.get('issue_timecodes')),
        'actor': actor,
        'actor_kind': 'human',
        'note': _text(value.get('note'), 'note', required=False, max_len=4000),
        'source_ref': str(source_ref).strip()[:200],
        'recorded_at': _now(),
        'voluntary': True,
        'externally_verified': False,
        'does_not_say': list(DOES_NOT_SAY),
    }
    document['content_sha256'] = _digest(document)
    return _check(document, _SCHEMA_PATH, 'a feedback record')


def _now() -> str:
    return utc_now_rfc3339()


class PlanFeedback:
    def __init__(self, service):
        self.service = service
        self.paths = service.paths

    def _connect(self):
        return connect(self.paths.database_path(self.service.database),
                       project_root=self.paths.project_root)

    def record(self, project_id: str, plan_id: str, value: dict) -> dict:
        if not isinstance(value, dict):
            raise PlanFeedbackError(400, 'PLAN_FEEDBACK_WRITE_MALFORMED',
                                    'body must be an object')
        unexpected = sorted(set(value) - {'outcome', 'target_key', 'target_model',
                                          'dimensions', 'issue_timecodes', 'actor', 'note',
                                          'source_ref', 'revision'})
        if unexpected:
            raise PlanFeedbackError(400, 'PLAN_FEEDBACK_FIELD_NOT_IN_CONTRACT',
                                    f'the feedback route does not accept {unexpected}')
        actor = _text(value.get('actor'), 'actor', max_len=200)
        with closing(self._connect()) as conn:
            row = conn.execute('SELECT 1 FROM project WHERE project_id=?',
                               (project_id,)).fetchone()
            if row is None:
                raise PlanFeedbackError(404, 'PROJECT_NOT_FOUND')
            plan = conn.execute(
                'SELECT 1 FROM assistance_plan WHERE plan_id=? AND project_id=?',
                (plan_id, project_id)).fetchone()
            if plan is None:
                raise PlanFeedbackError(404, 'ASSISTANCE_PLAN_NOT_FOUND',
                                        f'no plan {plan_id} in this project')
            revision = value.get('revision')
            if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
                raise PlanFeedbackError(400, 'PLAN_FEEDBACK_REVISION_INVALID',
                                        'revision must be an integer of at least 1: a report is '
                                        'about the material somebody actually took away')
            stored = conn.execute('SELECT 1 FROM assistance_plan_revision WHERE plan_id=?'
                                  ' AND revision=?', (plan_id, revision)).fetchone()
            if stored is None:
                raise PlanFeedbackError(409, 'PLAN_FEEDBACK_REVISION_NOT_FOUND',
                                        f'revision {revision} of {plan_id} was never written; a '
                                        'feedback row cannot cite a revision that does not exist')
            next_no = conn.execute(
                'SELECT COALESCE(MAX(feedback_no), 0) + 1 FROM plan_feedback WHERE plan_id=?',
                (plan_id,)).fetchone()[0]
            document = _document(plan_id=plan_id, revision=revision, feedback_no=next_no,
                                 value=value, actor=actor)
            conn.execute(
                'INSERT INTO plan_feedback (plan_id, revision, feedback_no, outcome, target_key,'
                ' actor, actor_kind, note, source_ref, recorded_at, document_json, content_sha256)'
                ' VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                (plan_id, revision, next_no, document['outcome'], document['target_key'], actor,
                 'human', document['note'], document['source_ref'], document['recorded_at'],
                 _canonical(document), document['content_sha256']))
            conn.commit()
        return _check({'schemaVersion': WRITE_VERSION, 'status': 'PLAN_FEEDBACK',
                       'stored': True, 'feedback': document,
                       'plan_states_unchanged': True,
                       'claims_not_made': [
                           '外部结果未被系统核验', '未发送任何东西', '未运行任何外部产品或模型']},
                      _WRITE_SCHEMA_PATH, 'a feedback write',
                      registry=_ref_registry())

    def list(self, project_id: str, plan_id: str, *, offset=0, limit=DEFAULT_LIMIT) -> dict:
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_LIMIT:
            raise PlanFeedbackError(400, 'PLAN_FEEDBACK_LIMIT_INVALID',
                                    f'limit must be an integer between 1 and {MAX_LIMIT}')
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise PlanFeedbackError(400, 'PLAN_FEEDBACK_OFFSET_INVALID',
                                    'offset must be an integer of at least 0')
        with closing(self._connect()) as conn:
            if conn.execute('SELECT 1 FROM project WHERE project_id=?',
                            (project_id,)).fetchone() is None:
                raise PlanFeedbackError(404, 'PROJECT_NOT_FOUND')
            # An unknown plan is a 404, not an empty history. "Nothing was recorded" and "there is
            # no such plan" are different answers, and collapsing them is how a page ends up
            # telling somebody their report was lost when they mistyped an id.
            if conn.execute('SELECT 1 FROM assistance_plan WHERE plan_id=? AND project_id=?',
                            (plan_id, project_id)).fetchone() is None:
                raise PlanFeedbackError(404, 'ASSISTANCE_PLAN_NOT_FOUND',
                                        f'no plan {plan_id} in this project -- the history is not '
                                        'empty, the plan is absent')
            rows = conn.execute(
                'SELECT document_json, content_sha256 FROM plan_feedback WHERE plan_id=?'
                ' ORDER BY feedback_no', (plan_id,)).fetchall()
        records = []
        for row in rows:
            document = json.loads(row['document_json'])
            if document['content_sha256'] != row['content_sha256']:
                raise PlanFeedbackError(500, 'PLAN_FEEDBACK_BYTES_MOVED',
                                        f'{plan_id} r{document["feedback_no"]} no longer hashes '
                                        'to what was stored')
            records.append(document)
        total = len(records)
        page = records[offset:offset + limit]
        return _check({
            'schemaVersion': LIST_VERSION, 'plan_id': plan_id, 'total': total,
            'offset': offset, 'limit': limit,
            'next_offset': offset + limit if offset + limit < total else None,
            'records': page,
            'outcome_histogram': {outcome: sum(1 for r in records if r['outcome'] == outcome)
                                  for outcome in OUTCOMES},
            'latest': page[-1] if records else None,
            # LANGUAGE-POLICY §5: the screen must not hand-copy these words. The service emits the
            # value/label pairs it is enforcing, so a drift between the two is impossible by
            # construction rather than by review discipline.
            'outcome_words': [{'value': value, 'label': OUTCOME_LABELS[value]}
                              for value in OUTCOMES],
            'dimension_verdict_words': [{'value': value, 'label': DIMENSION_VERDICT_LABELS[value]}
                                        for value in DIMENSION_VERDICTS],
            'externally_verified': False,
            'does_not_say': list(DOES_NOT_SAY),
        }, _LIST_SCHEMA_PATH, 'the feedback list', registry=_ref_registry())
