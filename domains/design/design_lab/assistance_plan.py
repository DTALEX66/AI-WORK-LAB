# SPDX-License-Identifier: MIT
"""The assistance plan: one neutral design intent, its revisions, and who adopted one.

DL-KB-07, extended by DL-KB-11. A short task should not need a complete project before it can be
written down. This module is the object that holds the intent itself -- objective, output type,
neutral creative, brand/role constraints, lens and sound requirements, the shot rows a 分镜表 is
made of, external steps, known gaps and the material revisions it was built from -- and it reuses
the repository's existing objects for everything it can: the project owns it, and brief / direction
/ prompt result / asset references carry the revision and digest they had when the plan was written.

Four facts are kept apart on purpose, because the screen has to show them apart:

* **saved** -- the plan's bytes are in the state database. That is all a write answer claims.
* **provided** -- the current revision carries a neutral creative. A draft with an objective and
  no creative is saved but not provided, and the readback says so.
* **chosen** -- a named human adopted a revision (``assistance_plan_choice``). The table's CHECK
  refuses any other actor_kind, so an application bug cannot file an agent's choice as a person's.
* **externally verified** -- always false. No route in this repository dispatches an external
  step, so the readback carries the constant and the schema pins it with ``const: false``: turning
  it true requires a contract change, not a flag flip.

Analysis is never inferred from a reference. A plan that names an asset is *linked* to it; the
readback reports ``ANALYZED`` only when a stored reversal (``prompt_result`` with kind REVERSAL)
exists for that asset at its current digest. When a reference is only registered as a link, every
surface reads ``LINKED_ONLY`` -- there is no branch that upgrades it because the plan mentions it.

Like the knowledge library, one writer appends revisions and "current" is MAX(revision) at read
time. A plan's revision pins the revisions of its references; if a referenced object moves on, the
readback reports the reference as CHANGED rather than quietly showing the new bytes as if they were
what the plan used.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import re
import sqlite3
import uuid

from .assurance import utc_now_rfc3339
from .creative import store as cstore
from .interop import InteropError, load_schema, resource_registry, schema_errors
from .runtime.state_resources import repo_resource, state_schema

PLAN_VERSION = 'design-lab/assistance-plan/v1'
WRITE_VERSION = 'design-lab/assistance-plan-write/v1'
READBACK_VERSION = 'design-lab/assistance-plan-readback/v1'
LIST_VERSION = 'design-lab/assistance-plan-list/v1'
OUTPUT_TYPES_VERSION = 'design-lab/assistance-plan-output-types/v1'
REVISION_VERSION = 'design-lab/assistance-plan-revision/v1'

PLAN_SCHEMA_PATH = repo_resource('schemas/assistance-plan-v1.schema.json')
_READBACK_SCHEMA_PATH = repo_resource('schemas/assistance-plan-readback-v1.schema.json')
_WRITE_SCHEMA_PATH = repo_resource('schemas/assistance-plan-write-v1.schema.json')
_LIST_SCHEMA_PATH = repo_resource('schemas/assistance-plan-list-v1.schema.json')
_OUTPUT_TYPES_SCHEMA_PATH = repo_resource('schemas/assistance-plan-output-types-v1.schema.json')
_REVISION_SCHEMA_PATH = repo_resource('schemas/assistance-plan-revision-v1.schema.json')
_STATE = state_schema('design-lab-state-assistance-plan-v1.sql')

OUTPUT_TYPES = ('IMAGE', 'UI', 'MOTION', 'STORYBOARD', 'AUDIO', 'CAMPAIGN')
#: The output types that may carry shot rows (DL-KB-11). A poster or a brand guideline has no 分镜,
#: and a plan that files shot rows under one of those is a mistake the service says out loud
#: instead of quietly keeping rows no export will ever show.
SHOT_BEARING_TYPES = ('STORYBOARD', 'MOTION')
MAX_SHOTS = 60
#: One shot row's fields, in the order the CSV header writes them. `camera`/`sound`/
#: `reference_role` are `null` when the person left them blank -- deliberately NOT the plan-level
#: ``UNKNOWN``: a spreadsheet cell is read by a person in another tool, and an empty cell there
#: means "this row does not say", which is the same answer the plan's own state words give, carried
#: in the one notation a table understands.
SHOT_FIELDS = ('index', 'duration_s', 'purpose', 'camera', 'sound', 'reference_role')
#: The output types as the initial screen names them. One table, served with every answer, so the
#: view cannot offer a word the service refuses or hide one it accepts.
OUTPUT_LABELS = {'IMAGE': '平面与品牌', 'UI': '界面与交互', 'MOTION': '动效与视频',
                 'STORYBOARD': '分镜与脚本', 'AUDIO': '声音', 'CAMPAIGN': '整合方案'}
UNKNOWN = 'UNKNOWN'
UNUSED = 'UNUSED'
#: KNOWLEDGE was added for DL-KB-05 D5: a plan that used a library entry has to be able to say
#: which revision of it, or "the recommendation moved" would silently rewrite what the plan
#: claims it worked from. The four schema enums of this list are tied to this tuple by
#: design-lab/tests/test_assistance_plan.py -- a word added to one side only is the defect.
REFERENCE_KINDS = ('ASSET', 'BRIEF', 'DIRECTION', 'PROMPT_RESULT', 'KNOWLEDGE')
REFERENCE_ID = {
    'ASSET': re.compile(r'^img-[0-9a-f]{64}$'),
    'BRIEF': re.compile(r'^brief-[0-9a-f]{32}$'),
    'DIRECTION': re.compile(r'^direction-[0-9a-f]{32}$'),
    'PROMPT_RESULT': re.compile(r'^(?:prompt|reversal)-[0-9a-f]{32}$'),
    'KNOWLEDGE': re.compile(r'^kentry-[0-9a-f]{32}$'),
}
#: Fields the content digest covers. Identity (plan_id, revision) and bookkeeping (timestamps,
#: author) are outside it, so the same content written twice digests to the same value.
CONTENT_FIELDS = ('objective', 'output_type', 'neutral_creative', 'brand_constraints',
                  'role_constraints', 'lens', 'sound', 'shots', 'references', 'external_steps',
                  'known_gaps', 'limits')
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
MAX_OPTIONAL_TEXT = 8000

CLAIMS_NOT_MADE = (
    'this plan is a record of a person\'s intent; no model was run to produce it, and the '
    'assistance model setting is a separate record that does not appear here',
    'an external job_id or operation_id is a label the caller supplied; this service never '
    'dispatched that step and cannot verify whether it ran',
    'referencing an asset is not analysing it; the readback reports analysis evidence separately '
    'and a linked-only reference stays LINKED_ONLY',
    'the references below are pinned to the revisions recorded here; a later revision of a '
    'referenced object does not change what this plan used',
)

DOES_NOT_SAY = (
    '保存方案不是运行模型，也不是生成图片或视频；方案内容由创建者填写',
    '登记外部 job_id/operation_id 不代表已派发或已执行，服务不核验外部结果',
    '参考只登记了链接时，不代表图片或视频已被分析',
    '「用户选用」是一条具名人工记录，不是质量评分或系统推荐',
)

_CHOOSE_FIELDS = ('actor', 'actor_kind')


class AssistancePlanError(ValueError):
    """A store refusal carrying the status and code the route answers with."""

    def __init__(self, status, code, detail=None):
        super().__init__(detail or code)
        self.status = status
        self.code = code
        self.detail = detail


def connect(db_path, *, project_root=None) -> sqlite3.Connection:
    """Open the shared state database with the plan tables present.

    ``cstore.connect`` is the same guarded connection the design layer uses, so ``project``,
    ``asset_version``, ``design_brief`` and ``design_direction`` are guaranteed to exist before a
    reference is resolved. The plan tables are additive to that database.
    """
    try:
        connection = cstore.connect(db_path, project_root=project_root)
    except Exception as exc:  # cstore raises its own error type on a policy failure
        raise AssistancePlanError(500, 'ASSISTANCE_PLAN_STATE_UNAVAILABLE',
                                  f'the state database could not be opened: {exc}') from None
    connection.row_factory = sqlite3.Row
    connection.executescript(_STATE.read_text(encoding='utf-8'))
    connection.commit()
    return connection


def _now() -> str:
    return utc_now_rfc3339()


def _canonical(document) -> str:
    return json.dumps(document, ensure_ascii=False, sort_keys=True)


def _digest(document) -> str:
    return 'sha256:' + hashlib.sha256(_canonical(document).encode('utf-8')).hexdigest()


def _content_digest(document) -> str:
    # `.get`, not `[key]`: a plan stored before DL-KB-11 has no `shots` member at all, and a
    # re-derivation of its digest must answer with a value rather than a KeyError. The write path
    # always builds the field, so a document this service is filing now is unaffected.
    return _digest({key: document.get(key) for key in CONTENT_FIELDS})


_registry = None


def _ref_registry():
    global _registry
    if _registry is None:
        try:
            document = load_schema(PLAN_SCHEMA_PATH)
        except (InteropError, OSError) as exc:
            raise AssistancePlanError(
                500, 'ASSISTANCE_PLAN_CONTRACT_UNREADABLE',
                f'cannot load {PLAN_SCHEMA_PATH.name} for $ref resolution: {exc}') from None
        identifier = document.get('$id')
        if not isinstance(identifier, str):
            raise AssistancePlanError(
                500, 'ASSISTANCE_PLAN_CONTRACT_UNREADABLE',
                f'{PLAN_SCHEMA_PATH.name} carries no $id, so a $ref into it cannot be resolved '
                'offline')
        _registry = resource_registry({identifier: document})
    return _registry


def _check(document, path, label, *, registry=None):
    try:
        problems = schema_errors(load_schema(path), document, registry=registry)
    except (InteropError, OSError) as exc:
        raise AssistancePlanError(500, 'ASSISTANCE_PLAN_CONTRACT_UNREADABLE',
                                  f'cannot load {path.name} for {label}: {exc}') from None
    if problems:
        raise AssistancePlanError(500, 'ASSISTANCE_PLAN_CONTRACT_VIOLATION', problems)
    return document


def _required_text(value, field, *, max_len=2000):
    if not isinstance(value, str) or not value.strip():
        raise AssistancePlanError(400, 'ASSISTANCE_PLAN_FIELD_MISSING',
                                  f'{field} is required and must be a non-empty string')
    value = value.strip()
    if len(value) > max_len:
        raise AssistancePlanError(400, 'ASSISTANCE_PLAN_FIELD_TOO_LONG',
                                  f'{field} exceeds {max_len} characters')
    return value


def _optional_text(value, field, *, max_len=MAX_OPTIONAL_TEXT):
    """A field the caller left out is UNKNOWN in the stored bytes, never absent."""
    if value is None:
        return UNKNOWN
    if not isinstance(value, str):
        raise AssistancePlanError(400, 'ASSISTANCE_PLAN_FIELD_MALFORMED',
                                  f'{field} must be a string (or absent); got '
                                  f'{type(value).__name__}')
    value = value.strip()
    if not value:
        return UNKNOWN
    if len(value) > max_len:
        raise AssistancePlanError(400, 'ASSISTANCE_PLAN_FIELD_TOO_LONG',
                                  f'{field} exceeds {max_len} characters')
    return value


def _string_list(value, field, *, item_max=400, limit=32):
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > limit:
        raise AssistancePlanError(400, 'ASSISTANCE_PLAN_FIELD_MALFORMED',
                                  f'{field} must be a list of at most {limit} strings')
    out = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise AssistancePlanError(400, 'ASSISTANCE_PLAN_FIELD_MALFORMED',
                                      f'{field} contains an empty or non-string value')
        item = item.strip()
        if len(item) > item_max:
            raise AssistancePlanError(400, 'ASSISTANCE_PLAN_FIELD_TOO_LONG',
                                      f'{field} contains a value over {item_max} characters')
        if item not in out:
            out.append(item)
    return out


def _shot_text(value, field):
    """One optional cell of a shot row: a person's words, or null because this row does not say.

    Plan-level fields store the literal ``UNKNOWN`` when the caller left them out (see
    ``_optional_text``). A shot row does the same job in the notation the row's reader understands:
    a 分镜表 is opened in a spreadsheet by somebody who has never seen this service, and there an
    empty cell is the honest "not stated" -- turning it into a state word this store invented would
    put our vocabulary in their table.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise AssistancePlanError(400, 'ASSISTANCE_PLAN_SHOT_FIELD_MALFORMED',
                                  f'{field} must be a string or null (absent); got '
                                  f'{type(value).__name__}')
    value = value.strip()
    if not value:
        return None
    if len(value) > 400:
        raise AssistancePlanError(400, 'ASSISTANCE_PLAN_SHOT_FIELD_TOO_LONG',
                                  f'{field} exceeds 400 characters')
    return value


def _shots(value, output_type):
    """The plan's shot rows, or nothing -- and a refusal when they cannot belong here.

    DL-KB-11's precondition: a 分镜 CSV rendered from an object that has no shot rows would be a
    fabricated deliverable, so the rows have to be stored data first. The list is optional (an
    every-day poster plan has none, and every plan stored before this field existed still validates
    against the same document version), but it is never silently dropped: a malformed row, a
    repeated 序号 or a row without a purpose is refused with a named code, exactly the way
    ``_string_list`` and ``_external_steps`` refuse their own malformed input.

    Shot rows on an output type that has no 分镜 is a 409, not a 400: the request is well-formed
    and the *pairing* is the mistake. Saying it out loud is what keeps a brand-guideline plan from
    quietly accumulating rows no export will ever show.
    """
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_SHOTS:
        raise AssistancePlanError(
            400, 'ASSISTANCE_PLAN_SHOTS_MALFORMED',
            f'shots must be a list of at most {MAX_SHOTS} shot-row objects')
    if value and output_type not in SHOT_BEARING_TYPES:
        raise AssistancePlanError(
            409, 'ASSISTANCE_PLAN_SHOTS_NOT_APPLICABLE',
            f'输出类型「{OUTPUT_LABELS.get(output_type, output_type)}」没有分镜行：分镜只在'
            '「分镜与脚本」和「动效与视频」两类方案里出现。把镜头行写进一份平面方案，'
            '导出的分镜表就成了没有任何人能在拍摄现场核对的材料；要么把方案改成这两类之一，'
            '要么去掉 shots。')
    out = []
    for position, item in enumerate(value):
        if not isinstance(item, dict):
            raise AssistancePlanError(400, 'ASSISTANCE_PLAN_SHOTS_MALFORMED',
                                      f'shots[{position}] must be an object')
        extra = sorted(set(item) - set(SHOT_FIELDS))
        if extra:
            raise AssistancePlanError(
                400, 'ASSISTANCE_PLAN_SHOT_UNKNOWN_FIELD',
                f'shots[{position}] carries undeclared field(s): {extra}')
        index = item.get('index')
        if not isinstance(index, int) or isinstance(index, bool) or not 1 <= index <= MAX_SHOTS:
            raise AssistancePlanError(
                400, 'ASSISTANCE_PLAN_SHOT_INDEX_INVALID',
                f'shots[{position}].index must be an integer between 1 and {MAX_SHOTS}; got '
                f'{index!r} -- a shot number is how a spreadsheet reader finds the row again, so '
                'the service does not renumber what a person counted')
        if any(entry['index'] == index for entry in out):
            raise AssistancePlanError(
                400, 'ASSISTANCE_PLAN_SHOT_INDEX_DUPLICATE',
                f'shots[{position}].index {index} is already used: two rows claiming to be the '
                'same 镜头 cannot both be handed to a shoot')
        duration = item.get('duration_s')
        if duration is not None:
            if isinstance(duration, bool) or not isinstance(duration, (int, float)) \
                    or not 0 < duration <= 86400:
                raise AssistancePlanError(
                    400, 'ASSISTANCE_PLAN_SHOT_DURATION_INVALID',
                    f'shots[{position}].duration_s must be a positive number of seconds (at most '
                    f'86400) or null; got {duration!r}')
            duration = float(duration)
        purpose = item.get('purpose')
        if not isinstance(purpose, str) or not purpose.strip():
            raise AssistancePlanError(
                400, 'ASSISTANCE_PLAN_SHOT_PURPOSE_MISSING',
                f'shots[{position}].purpose is required and must be a non-empty string: a row '
                'with no purpose is a blank line in a shot list, not a shot')
        if len(purpose.strip()) > 800:
            raise AssistancePlanError(
                400, 'ASSISTANCE_PLAN_SHOT_PURPOSE_TOO_LONG',
                f'shots[{position}].purpose exceeds 800 characters')
        label = f'shots[{position}].'
        out.append({'index': index, 'duration_s': duration, 'purpose': purpose.strip(),
                    'camera': _shot_text(item.get('camera'), label + 'camera'),
                    'sound': _shot_text(item.get('sound'), label + 'sound'),
                    'reference_role': _shot_text(item.get('reference_role'),
                                                 label + 'reference_role')})
    return out


def _reference_ids(value):
    """The request's reference list, normalised to ``[{kind, id}]`` in first-seen order.

    Only the two keys a caller may state are accepted; revision and digest are resolved by the
    store from the live object, because a caller-supplied digest would be a claim this service
    has not measured.
    """
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 64:
        raise AssistancePlanError(400, 'ASSISTANCE_PLAN_REFERENCES_MALFORMED',
                                  'references must be a list of at most 64 {kind, id} objects')
    out = []
    for item in value:
        if not isinstance(item, dict):
            raise AssistancePlanError(400, 'ASSISTANCE_PLAN_REFERENCES_MALFORMED',
                                      'each reference must be an object with kind and id')
        extra = sorted(set(item) - {'kind', 'id'})
        if extra:
            raise AssistancePlanError(
                400, 'ASSISTANCE_PLAN_REFERENCE_UNKNOWN_FIELD',
                f'a reference carries field(s) this record resolves itself: {extra}. Revision '
                'and digest are read from the referenced object, never supplied by the caller')
        kind = item.get('kind')
        if kind not in REFERENCE_KINDS:
            raise AssistancePlanError(400, 'ASSISTANCE_PLAN_REFERENCE_KIND_INVALID',
                                      f'reference kind must be one of {REFERENCE_KINDS}; '
                                      f'got {kind!r}')
        identifier = item.get('id')
        if not isinstance(identifier, str) or REFERENCE_ID[kind].match(identifier) is None:
            raise AssistancePlanError(400, 'ASSISTANCE_PLAN_REFERENCE_ID_MALFORMED',
                                      f'{kind} reference id is malformed: {identifier!r}')
        if (kind, identifier) not in [(entry['kind'], entry['id']) for entry in out]:
            out.append({'kind': kind, 'id': identifier})
    return out


def _external_steps(value):
    """External steps carry only caller-supplied labels; a missing id is the literal UNUSED.

    The store mints no job or operation id. ``UNUSED`` is how a person says "I did not use one",
    and the readback repeats the distinction instead of turning a label into evidence.
    """
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 32:
        raise AssistancePlanError(400, 'ASSISTANCE_PLAN_STEPS_MALFORMED',
                                  'external_steps must be a list of at most 32 objects')
    out = []
    for item in value:
        if not isinstance(item, dict):
            raise AssistancePlanError(400, 'ASSISTANCE_PLAN_STEPS_MALFORMED',
                                      'each external step must be an object')
        extra = sorted(set(item) - {'step', 'tool', 'job_id', 'operation_id'})
        if extra:
            raise AssistancePlanError(400, 'ASSISTANCE_PLAN_STEP_UNKNOWN_FIELD',
                                      f'an external step carries undeclared field(s): {extra}')
        step = _required_text(item.get('step'), 'external_steps.step', max_len=400)
        tool = _optional_text(item.get('tool'), 'external_steps.tool', max_len=400)
        label = {}
        for key in ('job_id', 'operation_id'):
            raw = item.get(key)
            if raw is None or (isinstance(raw, str) and not raw.strip()):
                label[key] = UNUSED
                continue
            if not isinstance(raw, str) or any(ord(char) < 32 for char in raw) or len(raw) > 200:
                raise AssistancePlanError(
                    400, 'ASSISTANCE_PLAN_STEP_LABEL_MALFORMED',
                    f'external_steps.{key} must be a supplied label of at most 200 characters '
                    'with no control characters, or the literal UNUSED')
            label[key] = raw.strip()
        out.append({'step': step, 'tool': tool, 'job_id': label['job_id'],
                    'operation_id': label['operation_id']})
    return out


def _fields(value):
    if not isinstance(value, dict):
        raise AssistancePlanError(400, 'ASSISTANCE_PLAN_FIELDS_MALFORMED',
                                  'the request body must be one object')
    objective = _required_text(value.get('objective'), 'objective')
    output_type = value.get('output_type')
    if output_type not in OUTPUT_TYPES:
        raise AssistancePlanError(400, 'ASSISTANCE_PLAN_OUTPUT_TYPE_INVALID',
                                  f'output_type must be one of {OUTPUT_TYPES}; '
                                  f'got {output_type!r}')
    created_by = _required_text(value.get('created_by'), 'created_by', max_len=200)
    return {
        'objective': objective,
        'output_type': output_type,
        'neutral_creative': _optional_text(value.get('neutral_creative'), 'neutral_creative'),
        'brand_constraints': _string_list(value.get('brand_constraints'), 'brand_constraints'),
        'role_constraints': _string_list(value.get('role_constraints'), 'role_constraints'),
        'lens': _optional_text(value.get('lens'), 'lens'),
        'sound': _optional_text(value.get('sound'), 'sound'),
        'shots': _shots(value.get('shots'), output_type),
        'reference_ids': _reference_ids(value.get('references')),
        'external_steps': _external_steps(value.get('external_steps')),
        'known_gaps': _string_list(value.get('known_gaps'), 'known_gaps'),
        'limits': _string_list(value.get('limits'), 'limits'),
        'created_by': created_by,
    }


def _table_exists(conn, name):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (name,)).fetchone() is not None


def _resolve_references(conn, project_id, references):
    """Pin each reference to the revision and digest the object has *now*.

    A missing table means nothing of that kind was ever stored in this checkout, which is the
    same answer as "no such object" -- 404 with the kind named. A cross-project or malformed
    reference fails closed, exactly as the brief writer's reference check does.
    """
    resolved = []
    for entry in references:
        kind, identifier = entry['kind'], entry['id']
        row = None
        if kind == 'ASSET':
            row = conn.execute(
                'SELECT a.project_id, v.version_no, v.content_sha256 FROM asset a'
                ' JOIN asset_version v ON v.asset_id = a.asset_id AND v.state = ?'
                ' WHERE a.asset_id = ? ORDER BY v.version_no DESC LIMIT 1',
                ('ACTIVE', identifier)).fetchone()
            revision, digest = (row['version_no'], row['content_sha256']) if row else (None, None)
            owner = row['project_id'] if row else None
        elif kind == 'BRIEF':
            if _table_exists(conn, 'design_brief'):
                row = conn.execute(
                    'SELECT project_id, version, spec_sha256 FROM design_brief WHERE brief_id=?',
                    (identifier,)).fetchone()
            revision, digest = ((row['version'], 'sha256:' + row['spec_sha256'])
                                if row else (None, None))
            owner = row['project_id'] if row else None
        elif kind == 'DIRECTION':
            if _table_exists(conn, 'design_direction'):
                row = conn.execute(
                    'SELECT project_id, version, spec_sha256 FROM design_direction'
                    ' WHERE direction_id=?', (identifier,)).fetchone()
            revision, digest = ((row['version'], 'sha256:' + row['spec_sha256'])
                                if row else (None, None))
            owner = row['project_id'] if row else None
        elif kind == 'PROMPT_RESULT':
            if _table_exists(conn, 'prompt_result'):
                # result_id is unique per project, not globally (prompt_result is keyed by
                # (project_id, revision)). Prefer this project's row so a same-named result in
                # another project cannot turn a valid reference into a project mismatch.
                rows = conn.execute(
                    'SELECT project_id, revision, content_sha256 FROM prompt_result'
                    ' WHERE result_id=? ORDER BY revision DESC', (identifier,)).fetchall()
                row = next((entry for entry in rows if entry['project_id'] == project_id),
                           rows[0] if rows else None)
            revision, digest = ((row['revision'], row['content_sha256']) if row else (None, None))
            owner = row['project_id'] if row else None
        elif kind == 'KNOWLEDGE':
            # The library is global (like /api/capabilities), so a knowledge entry has no project
            # column to mismatch against: what a plan pins here is the entry's newest *revision*
            # and that revision's own content digest. A judgement that later moves the entry's
            # recommendation writes no revision, so this pin keeps pointing at the same bytes --
            # which is the whole of DL-KB-05 D5's 旧方案仍可读.
            if _table_exists(conn, 'knowledge_entry_revision'):
                row = conn.execute(
                    'SELECT revision, content_sha256 FROM knowledge_entry_revision'
                    ' WHERE entry_id=? ORDER BY revision DESC LIMIT 1', (identifier,)).fetchone()
            revision, digest = ((row['revision'], row['content_sha256']) if row else (None, None))
            # Global library: a knowledge entry belongs to no project, so there is no owner
            # to mismatch against. The pin is the entry's newest revision and its digest.
            owner = None
        if row is None:
            raise AssistancePlanError(
                404, 'ASSISTANCE_PLAN_REFERENCE_NOT_FOUND',
                f'{kind} {identifier} is not stored in this checkout, so a plan cannot cite it')
        if owner is not None and owner != project_id:
            raise AssistancePlanError(
                409, 'ASSISTANCE_PLAN_REFERENCE_PROJECT_MISMATCH',
                f'{kind} {identifier} belongs to another project; a plan cites only material of '
                'its own project')
        if revision is None or not digest:
            raise AssistancePlanError(
                409, 'ASSISTANCE_PLAN_REFERENCE_NOT_READY',
                f'{kind} {identifier} has no current revision to pin (an asset without an active '
                'version, for example), so the plan cannot record what it used')
        resolved.append({'kind': kind, 'id': identifier, 'revision': revision,
                         'sha256': digest})
    return resolved


def _document(plan_id, revision, project_id, fields, references):
    document = {
        'schemaVersion': PLAN_VERSION,
        'plan_id': plan_id,
        'revision': revision,
        'project_id': project_id,
        'objective': fields['objective'],
        'output_type': fields['output_type'],
        'neutral_creative': fields['neutral_creative'],
        'brand_constraints': list(fields['brand_constraints']),
        'role_constraints': list(fields['role_constraints']),
        'lens': fields['lens'],
        'sound': fields['sound'],
        'shots': [dict(row) for row in fields['shots']],
        'references': references,
        'external_steps': fields['external_steps'],
        'known_gaps': list(fields['known_gaps']),
        'limits': list(fields['limits']),
        'content_sha256': '',
        'created_at': _now(),
        'created_by': fields['created_by'],
        'claims_not_made': list(CLAIMS_NOT_MADE),
    }
    document['content_sha256'] = _content_digest(document)
    return _check(document, PLAN_SCHEMA_PATH, 'assistance plan')


def _provided(document):
    return isinstance(document, dict) and document.get('neutral_creative') not in (None, '', UNKNOWN)


def _choice_row(conn, plan_id):
    """The one choice row that answers "which revision did a person adopt?", or None.

    DL-KB-12 moved the query out of ``detail()`` so the single-revision read asks it the same
    question the same way. Two ORDER BY clauses would be two truths about a human gate record: the
    readback's ``choice`` and the revision read's ``is_chosen`` have to agree because they are
    computed by one statement, not because two tests happen to pass.
    """
    return conn.execute(
        'SELECT revision, actor, actor_kind, chosen_at FROM assistance_plan_choice'
        ' WHERE plan_id=? ORDER BY chosen_at DESC, revision DESC LIMIT 1',
        (plan_id,)).fetchone()


def _digest_covers(document, stored) -> bool:
    """Does ``stored`` still name the content bytes this row carries?

    The write path digests over ``CONTENT_FIELDS`` (identity and bookkeeping stay outside it), so a
    row whose text moved while its published digest did not is a drifted record, not a plan -- and a
    comparison page built on it would diff one revision's digest against another revision's words.
    The fields are taken from the ones the document itself carries: ``shots`` (DL-KB-11) is optional,
    and a plan written before it existed digested over the fields it had, so re-deriving with a key
    nobody ever wrote would convict an untouched plan of drift.
    """
    return _digest({key: document[key] for key in CONTENT_FIELDS
                    if key in document}) == stored


class AssistancePlans:
    def __init__(self, service):
        self.service = service
        self.paths = service.paths

    def _connect(self):
        return connect(self.paths.database_path(self.service.database),
                       project_root=self.paths.project_root)

    @staticmethod
    def _check_project(conn, project_id):
        if conn.execute('SELECT 1 FROM project WHERE project_id=?', (project_id,)).fetchone() is None:
            raise AssistancePlanError(404, 'PROJECT_NOT_FOUND')

    def output_types(self, export_formats) -> dict:
        """The closed vocabulary the create route accepts, with the screen's own labels.

        Project-independent on purpose: the initial screen must be able to offer a type before
        a workspace exists, and a view that carried its own copy of these six words could offer
        one the service refuses.

        DL-KB-11 (2026-10-24): the material formats answer on the same document, because this is the
        one surface the handoff screen reads before any plan exists. They come in as a parameter
        rather than an import -- `plan_export` reads this module, so importing it back would make the
        two files one cycle, and a second literal list here would give the same four words two
        owners. The caller hands over `plan_export.material_table()` and this store validates the
        whole envelope, including that each format keeps its own content type and extension.
        """
        return _check({'schemaVersion': OUTPUT_TYPES_VERSION,
                       'output_types': [{'value': value, 'label': OUTPUT_LABELS[value]}
                                        for value in OUTPUT_TYPES],
                       'export_formats': list(export_formats)},
                      _OUTPUT_TYPES_SCHEMA_PATH, 'assistance plan output types')

    def _write_revision(self, conn, plan_id, revision, project_id, fields, created_by):
        references = _resolve_references(conn, project_id, fields['reference_ids'])
        document = _document(plan_id, revision, project_id, fields, references)
        try:
            conn.execute(
                'INSERT INTO assistance_plan_revision (plan_id, revision, objective, output_type,'
                ' content_sha256, created_at, created_by, document_json)'
                ' VALUES (?,?,?,?,?,?,?,?)',
                (plan_id, revision, document['objective'], document['output_type'],
                 document['content_sha256'], document['created_at'], created_by,
                 _canonical(document)))
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            raise AssistancePlanError(409, 'ASSISTANCE_PLAN_CONCURRENT_UPDATE',
                                      f'the state database refused the revision: {exc}') from None
        return document

    # -- writing ------------------------------------------------------------------

    def create(self, project_id, value) -> dict:
        fields = _fields(value)
        with closing(self._connect()) as conn:
            self._check_project(conn, project_id)
            plan_id = 'aplan-' + uuid.uuid4().hex
            conn.execute('INSERT INTO assistance_plan (plan_id, project_id, created_at)'
                         ' VALUES (?,?,?)', (plan_id, project_id, _now()))
            document = self._write_revision(conn, plan_id, 1, project_id, fields,
                                            fields['created_by'])
            conn.commit()
        return _check({'schemaVersion': WRITE_VERSION, 'status': 'ASSISTANCE_PLAN',
                       'stored': True, 'plan': document, 'revision': 1,
                       'claims_not_made': list(CLAIMS_NOT_MADE)},
                      _WRITE_SCHEMA_PATH, 'assistance plan write', registry=_ref_registry())

    def revise(self, project_id, plan_id, value) -> dict:
        fields = _fields(value)
        expected = value.get('expected_revision')
        if not isinstance(expected, int) or isinstance(expected, bool) or expected < 1:
            raise AssistancePlanError(
                400, 'ASSISTANCE_PLAN_EXPECTED_REVISION_REQUIRED',
                'expected_revision must be the revision this write was prepared against; without '
                'it a second writer silently overwrites the first one\'s correction')
        with closing(self._connect()) as conn:
            plan = conn.execute('SELECT project_id FROM assistance_plan WHERE plan_id=?',
                                (plan_id,)).fetchone()
            if plan is None or plan['project_id'] != project_id:
                raise AssistancePlanError(404, 'ASSISTANCE_PLAN_NOT_FOUND')
            current = conn.execute(
                'SELECT MAX(revision) AS top FROM assistance_plan_revision WHERE plan_id=?',
                (plan_id,)).fetchone()['top']
            if expected != current:
                raise AssistancePlanError(
                    409, 'ASSISTANCE_PLAN_REVISION_CONFLICT',
                    f'the plan is at revision {current}, not {expected}; re-read it and write '
                    'against the revision you actually saw')
            document = self._write_revision(conn, plan_id, current + 1, project_id, fields,
                                            fields['created_by'])
            conn.commit()
        return _check({'schemaVersion': WRITE_VERSION, 'status': 'ASSISTANCE_PLAN',
                       'stored': True, 'plan': document, 'revision': current + 1,
                       'claims_not_made': list(CLAIMS_NOT_MADE)},
                      _WRITE_SCHEMA_PATH, 'assistance plan write', registry=_ref_registry())

    def choose(self, project_id, plan_id, value) -> dict:
        """Record that a named human adopted one stored revision.

        Only ``actor_kind: 'human'`` is accepted. This repository's gate rule is that acceptance
        is signed by a named person; an agent's choice is a proposal, and the storage CHECK
        refuses it as well so the rule survives an application bug.
        """
        if not isinstance(value, dict):
            raise AssistancePlanError(400, 'ASSISTANCE_PLAN_FIELDS_MALFORMED',
                                      'the request body must be one object')
        extra = sorted(set(value) - set(_CHOOSE_FIELDS) - {'revision'})
        if extra:
            raise AssistancePlanError(400, 'ASSISTANCE_PLAN_CHOICE_UNKNOWN_FIELD',
                                      f'the choice carries undeclared field(s): {extra}')
        actor = _required_text(value.get('actor'), 'actor', max_len=200)
        if value.get('actor_kind') != 'human':
            raise AssistancePlanError(
                409, 'ASSISTANCE_PLAN_CHOICE_NOT_HUMAN',
                'only a named human can adopt a plan: an agent\'s choice is a proposal, and this '
                'record is the person\'s statement')
        revision = value.get('revision')
        with closing(self._connect()) as conn:
            plan = conn.execute('SELECT project_id FROM assistance_plan WHERE plan_id=?',
                                (plan_id,)).fetchone()
            if plan is None or plan['project_id'] != project_id:
                raise AssistancePlanError(404, 'ASSISTANCE_PLAN_NOT_FOUND')
            top = conn.execute('SELECT MAX(revision) AS top FROM assistance_plan_revision'
                               ' WHERE plan_id=?', (plan_id,)).fetchone()['top']
            if not isinstance(revision, int) or isinstance(revision, bool) or not 1 <= revision <= top:
                raise AssistancePlanError(
                    400, 'ASSISTANCE_PLAN_CHOICE_REVISION_INVALID',
                    f'revision must name a stored revision between 1 and {top}')
            try:
                conn.execute(
                    'INSERT INTO assistance_plan_choice (plan_id, revision, actor, actor_kind,'
                    ' chosen_at) VALUES (?,?,?,?,?)',
                    (plan_id, revision, actor, 'human', _now()))
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                raise AssistancePlanError(
                    409, 'ASSISTANCE_PLAN_ALREADY_CHOSEN',
                    f'revision {revision} already carries a choice: {exc}. A choice is a record, '
                    'not a toggle; a different person changing their mind is a new fact only the '
                    'owner can decide how to contract') from None
            conn.commit()
        return self.detail(project_id, plan_id)

    # -- reading ------------------------------------------------------------------

    def _live_references(self, conn, project_id, references):
        """Each reference at its live revision, plus whether that asset has analysis evidence."""
        statuses = []
        analyzed = linked = 0
        for entry in references:
            kind, identifier = entry['kind'], entry['id']
            current_revision = current_sha = None
            analysis = None
            if kind == 'ASSET':
                row = conn.execute(
                    'SELECT v.version_no, v.content_sha256 FROM asset a JOIN asset_version v'
                    ' ON v.asset_id = a.asset_id AND v.state = ? WHERE a.asset_id = ?'
                    ' ORDER BY v.version_no DESC LIMIT 1', ('ACTIVE', identifier)).fetchone()
                current_revision = row['version_no'] if row else None
                current_sha = row['content_sha256'] if row else None
                if current_sha and _table_exists(conn, 'prompt_result') and conn.execute(
                        'SELECT 1 FROM prompt_result WHERE project_id=? AND kind=? AND asset_id=?'
                        ' AND asset_sha256=? LIMIT 1',
                        (project_id, 'REVERSAL', identifier, current_sha)).fetchone() is not None:
                    analysis = 'ANALYZED'
                    analyzed += 1
                else:
                    analysis = 'LINKED_ONLY'
                    linked += 1
            elif kind == 'BRIEF' and _table_exists(conn, 'design_brief'):
                row = conn.execute('SELECT version, spec_sha256 FROM design_brief'
                                   ' WHERE brief_id=?', (identifier,)).fetchone()
                current_revision = row['version'] if row else None
                current_sha = ('sha256:' + row['spec_sha256']) if row else None
            elif kind == 'DIRECTION' and _table_exists(conn, 'design_direction'):
                row = conn.execute('SELECT version, spec_sha256 FROM design_direction'
                                   ' WHERE direction_id=?', (identifier,)).fetchone()
                current_revision = row['version'] if row else None
                current_sha = ('sha256:' + row['spec_sha256']) if row else None
            elif kind == 'PROMPT_RESULT' and _table_exists(conn, 'prompt_result'):
                row = conn.execute('SELECT revision, content_sha256 FROM prompt_result'
                                   ' WHERE project_id=? AND result_id=?',
                                   (project_id, identifier)).fetchone()
                current_revision = row['revision'] if row else None
                current_sha = row['content_sha256'] if row else None
            elif kind == 'KNOWLEDGE' and _table_exists(conn, 'knowledge_entry_revision'):
                # The newest revision of the entry, which is not the recommended one: a
                # judgement can move the recommendation and this reading stays put, because
                # MAX(revision) is computed from the revision rows alone.
                row = conn.execute('SELECT revision, content_sha256 FROM'
                                   ' knowledge_entry_revision WHERE entry_id=?'
                                   ' ORDER BY revision DESC LIMIT 1', (identifier,)).fetchone()
                current_revision = row['revision'] if row else None
                current_sha = row['content_sha256'] if row else None
            if current_revision is None:
                state = 'MISSING'
            elif (current_revision, current_sha) == (entry['revision'], entry['sha256']):
                state = 'CURRENT'
            else:
                state = 'CHANGED'
            statuses.append({'kind': kind, 'id': identifier,
                             'recorded_revision': entry['revision'],
                             'recorded_sha256': entry['sha256'],
                             'current_revision': current_revision,
                             'current_sha256': current_sha,
                             'state': state, 'analysis': analysis})
        return statuses, {'analyzed': analyzed, 'linked_only': linked}

    def detail(self, project_id, plan_id) -> dict:
        with closing(self._connect()) as conn:
            plan = conn.execute('SELECT project_id FROM assistance_plan WHERE plan_id=?',
                                (plan_id,)).fetchone()
            if plan is None or plan['project_id'] != project_id:
                raise AssistancePlanError(404, 'ASSISTANCE_PLAN_NOT_FOUND')
            rows = conn.execute(
                'SELECT revision, content_sha256, created_at, created_by, document_json'
                ' FROM assistance_plan_revision WHERE plan_id=? ORDER BY revision',
                (plan_id,)).fetchall()
            choice = _choice_row(conn, plan_id)
            documents, unreadable, revisions = {}, 0, []
            for row in rows:
                try:
                    document = json.loads(row['document_json'])
                except (TypeError, ValueError):
                    document = None
                    unreadable += 1
                if document is not None:
                    documents[row['revision']] = document
                revisions.append({'revision': row['revision'],
                                  'content_sha256': row['content_sha256'],
                                  'created_at': row['created_at'],
                                  'created_by': row['created_by'],
                                  'readable': document is not None})
            latest = rows[-1]['revision'] if rows else None
            current = documents.get(latest)
            references = current['references'] if current else []
            statuses, summary = self._live_references(conn, project_id, references)
        latest_choice = None
        if choice is not None:
            latest_choice = {'chosen': True, 'revision': choice['revision'],
                             'actor': choice['actor'], 'actor_kind': choice['actor_kind'],
                             'chosen_at': choice['chosen_at'],
                             'is_latest': choice['revision'] == latest}
        else:
            latest_choice = {'chosen': False, 'revision': None, 'actor': None,
                             'actor_kind': None, 'chosen_at': None, 'is_latest': False}
        supplied = []
        if current:
            for step in current['external_steps']:
                for key in ('job_id', 'operation_id'):
                    if step[key] != UNUSED and step[key] not in supplied:
                        supplied.append(step[key])
        provided = _provided(current)
        return _check({
            'schemaVersion': READBACK_VERSION,
            'plan_id': plan_id,
            'project_id': project_id,
            'latest_revision': latest,
            'revisions': revisions,
            'current': current,
            'basis': [dict(entry) for entry in references],
            'reference_status': statuses,
            'analysis_summary': summary,
            'choice': latest_choice,
            'external': {'verified': False,
                         'steps': len(current['external_steps']) if current else 0,
                         'supplied_ids': supplied},
            'states': {'saved': True, 'provided': provided, 'chosen': latest_choice['chosen'],
                       'externally_verified': False},
            'does_not_say': list(DOES_NOT_SAY),
        }, _READBACK_SCHEMA_PATH, 'assistance plan readback', registry=_ref_registry())

    def revision(self, project_id, plan_id, revision) -> dict:
        """One stored revision, served as the bytes that row holds (DL-KB-12).

        The readback can only ever hand over the newest revision's document: its ``revisions`` list
        names each row's digest, created_at and created_by, and nothing else. So a page that shows
        「新版本不覆盖历史；对比页读的是两份真实修订」 had no second document to read -- it would have
        had to guess the older text or compare hashes. This route answers one row's own stored
        document.

        Nothing here is re-rendered, upgraded to today's bytes or rebuilt from the current
        revision: ``document`` is the stored JSON, and ``content_sha256`` / ``created_at`` /
        ``created_by`` are this row's own columns, while ``latest_revision`` says where the plan has
        since moved. ``is_chosen`` is the same one query the readback's ``choice`` is computed from,
        so the two routes cannot disagree about which revision a person adopted.

        A revision read says nothing about whether anything ran, and no flag here implies it did:
        the plan's four states stay the readback's answer rather than being restated as a second
        copy that could drift, and ``does_not_say`` is that store's own list, verbatim. The
        document travels by ``$ref`` into ``assistance-plan-v1.schema.json`` -- the contract the
        writer validated these bytes against when they were filed.
        """
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            raise AssistancePlanError(
                400, 'ASSISTANCE_PLAN_REVISION_NUMBER_INVALID',
                'revision must be a positive integer naming a stored row; the route\'s path '
                'pattern already refuses anything else, so a caller that reaches the store with a '
                'non-number is a defect this refuses by name rather than reading as revision 1')
        with closing(self._connect()) as conn:
            self._check_project(conn, project_id)
            plan = conn.execute('SELECT project_id FROM assistance_plan WHERE plan_id=?',
                                (plan_id,)).fetchone()
            if plan is None or plan['project_id'] != project_id:
                raise AssistancePlanError(404, 'ASSISTANCE_PLAN_NOT_FOUND')
            top = conn.execute('SELECT MAX(revision) AS top FROM assistance_plan_revision'
                               ' WHERE plan_id=?', (plan_id,)).fetchone()['top']
            row = conn.execute(
                'SELECT content_sha256, created_at, created_by, document_json'
                ' FROM assistance_plan_revision WHERE plan_id=? AND revision=?',
                (plan_id, revision)).fetchone()
            if row is None:
                # 404 with the plan id and the highest revision that really is there: "no such
                # revision" and "no such plan" are different questions for a comparison page, and a
                # silent fallback to the newest row is the bug this route exists to make impossible.
                raise AssistancePlanError(
                    404, 'ASSISTANCE_PLAN_REVISION_NOT_FOUND',
                    f'plan {plan_id} stores no revision {revision}; the highest revision it has is '
                    f'{top if top is not None else "none"}. Read the readback for the revision '
                    'list and name one of those numbers -- no row is rewritten and none is '
                    'invented here')
            choice = _choice_row(conn, plan_id)
        try:
            document = json.loads(row['document_json'])
        except (TypeError, ValueError):
            document = None
        if not isinstance(document, dict):
            raise AssistancePlanError(
                409, 'ASSISTANCE_PLAN_REVISION_UNREADABLE',
                f'修订 {revision} 存的内容无法解析成方案文档，服务不返回一个猜出来的版本：先读回这条方案'
                '确认修订历史，需要新内容时由人重写一版。')
        if document.get('content_sha256') != row['content_sha256'] \
                or not _digest_covers(document, row['content_sha256']):
            # Same discipline as `plan_feedback.list()`'s PLAN_FEEDBACK_BYTES_MOVED: a stored row
            # that no longer hashes to what its own record publishes is a server-side fault, not a
            # caller mistake, and it is never answered with the bytes anyway.
            raise AssistancePlanError(
                500, 'ASSISTANCE_PLAN_REVISION_BYTES_MOVED',
                f'plan {plan_id} revision {revision} no longer hashes to what was stored: the row '
                f'publishes {row["content_sha256"]} while its own document says '
                f'{document.get("content_sha256")}. Serving these bytes would put a digest and a '
                'different text on the same card, so the read refuses instead')
        return _check({
            'schemaVersion': REVISION_VERSION,
            'plan_id': plan_id,
            'project_id': project_id,
            'revision': revision,
            'latest_revision': top,
            'is_latest': revision == top,
            'is_chosen': choice is not None and choice['revision'] == revision,
            'provided': _provided(document),
            'content_sha256': row['content_sha256'],
            'created_at': row['created_at'],
            'created_by': row['created_by'],
            'document': document,
            'does_not_say': list(DOES_NOT_SAY),
        }, _REVISION_SCHEMA_PATH, 'assistance plan revision', registry=_ref_registry())

    def list(self, project_id, *, offset=0, limit=DEFAULT_LIMIT) -> dict:
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise AssistancePlanError(400, 'ASSISTANCE_PLAN_OFFSET_INVALID', 'offset must be >= 0')
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_LIMIT:
            raise AssistancePlanError(400, 'ASSISTANCE_PLAN_LIMIT_INVALID',
                                      f'limit must be between 1 and {MAX_LIMIT}')
        with closing(self._connect()) as conn:
            self._check_project(conn, project_id)
            total = conn.execute('SELECT COUNT(*) FROM assistance_plan WHERE project_id=?',
                                 (project_id,)).fetchone()[0]
            rows = conn.execute(
                'SELECT p.plan_id, r.revision, r.objective, r.output_type, r.created_at,'
                ' r.created_by, r.document_json FROM assistance_plan p'
                ' JOIN assistance_plan_revision r ON r.plan_id = p.plan_id'
                ' AND r.revision = (SELECT MAX(x.revision) FROM assistance_plan_revision x'
                '                    WHERE x.plan_id = p.plan_id)'
                ' WHERE p.project_id=? ORDER BY r.created_at DESC, p.plan_id DESC'
                ' LIMIT ? OFFSET ?', (project_id, limit, offset)).fetchall()
            choices = {row['plan_id']: row['revision'] for row in conn.execute(
                'SELECT c.plan_id, c.revision FROM assistance_plan_choice c WHERE NOT EXISTS ('
                ' SELECT 1 FROM assistance_plan_choice d WHERE d.plan_id = c.plan_id'
                ' AND (d.chosen_at > c.chosen_at'
                '      OR (d.chosen_at = c.chosen_at AND d.revision > c.revision)))')}
        plans = []
        for row in rows:
            try:
                document = json.loads(row['document_json'])
            except (TypeError, ValueError):
                document = None
            plans.append({'plan_id': row['plan_id'], 'revision': row['revision'],
                          'objective': row['objective'], 'output_type': row['output_type'],
                          'created_at': row['created_at'], 'created_by': row['created_by'],
                          'reference_count': len(document['references']) if document else 0,
                          'provided': _provided(document),
                          'chosen_revision': choices.get(row['plan_id'])})
        return _check({'schemaVersion': LIST_VERSION, 'total': total, 'offset': offset,
                       'limit': limit, 'returned': len(plans),
                       'next_offset': (offset + len(plans)) if offset + len(plans) < total else None,
                       'plans': plans},
                      _LIST_SCHEMA_PATH, 'assistance plan list')
