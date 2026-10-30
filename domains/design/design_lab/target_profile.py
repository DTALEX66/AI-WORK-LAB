# SPDX-License-Identifier: MIT
"""Target profiles: software x model x entry x task mode, with per-field provenance.

DL-KB-09. A profile answers one question -- what does THIS entry of THIS software, driving THIS
model, accept and produce -- and it answers it one field at a time, each field carrying the kind
of source it came from. The field list is the union of two sentences in the delivered pack that
do not agree on structure: ``02_完整产品方案.md`` line 64 names the capability fields (输入模态、
参考角色、素材数量与格式限制、时长/画幅/分辨率范围、提示风格、是否有负向输入、可用参数、参数设置
位置、输出形态、已知冲突、官方依据、测试日期、退路) and ``07_接口与数据演进.md`` line 29 names the
identity axes (软件、Agent、模型、提供方、版本、入口、任务模式). Axes are the key, capability
fields are the values; the union is recorded in the task receipt rather than silently picked.

Three rules are the reason this module exists rather than a spreadsheet:

* **A field we could not read stays UNKNOWN with the reason it is unknown.** The spec forbids
  inventing parameters, and an empty cell that says why is more useful than a guessed one.
* **Nothing here is 本项目实测.** No external product or model was run this round, so
  ``PROJECT_MEASURED`` is refused on every write path and ``executable`` is a constant false;
  turning it true needs a contract change plus a real run record, not a flag flip.
* **An official page that says "coming soon" is a conditional row, not support.** The MiniMax
  ComfyUI page and ElevenLabs Director's Mode both advertise undelivered capability; API
  documentation of a feature never implies the desktop or web client exposes it.

The five seeded profiles are served read-only from ``design-lab/config/target-profiles.json`` and
are deliberately NOT copied into the database: one byte must have one owner, or a config edit and
a stored row drift apart and both claim to be the profile. Only a person's draft at the screen is
written, into ``target_profile_draft``, where the table's CHECK pins ``support_state`` to
``USER_DRAFT`` so an application bug cannot file a draft as a documented claim.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from contextlib import closing

from .assurance import utc_now_rfc3339
from .creative import store as cstore
from .interop import InteropError, load_schema, resource_registry, schema_errors
from .runtime.state_resources import repo_resource, state_schema

PROFILE_VERSION = 'design-lab/target-profile/v1'
WRITE_VERSION = 'design-lab/target-profile-write/v1'
LIST_VERSION = 'design-lab/target-profile-list/v1'
AXES_VERSION = 'design-lab/target-profile-axes/v1'
VALIDATE_VERSION = 'design-lab/target-profile-validate/v1'

_PROFILE_SCHEMA_PATH = repo_resource('schemas/target-profile-v1.schema.json')
_WRITE_SCHEMA_PATH = repo_resource('schemas/target-profile-write-v1.schema.json')
_LIST_SCHEMA_PATH = repo_resource('schemas/target-profile-list-v1.schema.json')
_AXES_SCHEMA_PATH = repo_resource('schemas/target-profile-axes-v1.schema.json')
_VALIDATE_SCHEMA_PATH = repo_resource('schemas/target-profile-validate-v1.schema.json')
_SEED_PATH = repo_resource('config/target-profiles.json')
_STATE = state_schema('design-lab-state-target-profile-v1.sql')

#: ``02:64``, in the order the sentence lists them. Grouping is kept as the pack wrote it:
#: duration, aspect and resolution stay one `ranges` field rather than three invented columns.
CAPABILITY_FIELDS = ('input_modality', 'reference_roles', 'asset_limits', 'ranges', 'prompt_style',
                    'negative_input', 'available_parameters', 'parameter_location', 'output_form',
                    'known_conflicts', 'official_basis', 'tested_at', 'fallback')
FIELD_LABELS = {
    'input_modality': '输入模态', 'reference_roles': '支持的参考角色',
    'asset_limits': '素材数量与格式限制', 'ranges': '时长/画幅/分辨率范围',
    'prompt_style': '提示风格', 'negative_input': '是否有负向输入',
    'available_parameters': '可用参数', 'parameter_location': '参数设置位置',
    'output_form': '输出形态', 'known_conflicts': '已知冲突', 'official_basis': '官方依据',
    'tested_at': '测试日期', 'fallback': '退路',
}
AXIS_FIELDS = ('software', 'agent', 'model', 'provider', 'version', 'entry', 'task_mode')
#: The create route's whole request surface. Anything else is refused rather than ignored, so a
#: draft cannot smuggle a column into storage that no contract describes.
REQUEST_FIELDS = AXIS_FIELDS + ('actor', 'source_ref', 'fields')
#: Stated on every write answer, because a stored draft is a statement about intent only.
CLAIMS_NOT_MADE = ('本项目未实测该入口', '未运行任何外部产品或模型', '不授予可执行状态',
                  '未经官方确认的字段保留为未验证')
AXIS_LABELS = {'software': '软件', 'agent': 'Agent', 'model': '模型', 'provider': '提供方',
               'version': '版本', 'entry': '入口', 'task_mode': '任务模式'}

#: The four kinds the pack demands (02:58) plus the fifth this module needs: a rule of our own is
#: not evidence about somebody else's product, and labelling 退路 or 测试日期 as 本项目实测 would
#: put a fake measurement on the screen.
PROVENANCE_KINDS = ('OFFICIAL_DOC', 'OPEN_SOURCE_IMPL', 'PROJECT_MEASURED', 'USER_FEEDBACK',
                    'PROJECT_POLICY')
PROVENANCE_LABELS = {'OFFICIAL_DOC': '官方文档声明', 'OPEN_SOURCE_IMPL': '开源实现证据',
                     'PROJECT_MEASURED': '本项目实测', 'USER_FEEDBACK': '用户反馈',
                     'PROJECT_POLICY': '本项目规则（非对外部目标的证据）'}
#: Refused on every write path this round. See the module docstring.
UNWRITABLE_PROVENANCE = ('PROJECT_MEASURED',)

FIELD_STATES = ('DOCUMENTED', 'NOT_DOCUMENTED', 'UNKNOWN')
SUPPORT_STATES = ('DOCUMENTED_CLAIM', 'CONDITIONAL', 'UNREACHED', 'USER_DRAFT')
ENTRY_KINDS = ('API', 'WEB_APP', 'DESKTOP_CLIENT', 'COMFYUI_NODE', 'UNSTATED')
UNKNOWN = 'UNKNOWN'
UNUSED = 'UNUSED'
DEFAULT_LIMIT = 20
MAX_LIMIT = 100

VALIDATE_DIMENSIONS = ('modality', 'reference_role', 'asset_count', 'asset_format', 'duration',
                       'aspect', 'resolution', 'negative_input', 'parameter')
#: A verdict never grants executability; it only says what the profile's own fields say.
VERDICTS = ('DOCUMENTED_SUPPORT', 'DOCUMENTED_NOT_SUPPORT', 'UNKNOWN', 'NOT_APPLICABLE')
_DIMENSION_FIELD = {'modality': 'input_modality', 'reference_role': 'reference_roles',
                    'asset_count': 'asset_limits', 'asset_format': 'asset_limits',
                    'duration': 'ranges', 'aspect': 'ranges', 'resolution': 'ranges',
                    'negative_input': 'negative_input', 'parameter': 'available_parameters'}


class TargetProfileError(ValueError):
    """A refusal with the HTTP status and code the page has to branch on."""

    def __init__(self, status, code, detail=None):
        super().__init__(f'{code}: {detail}' if detail else code)
        self.status = status
        self.code = code
        self.detail = detail


def connect(db_path, *, project_root=None) -> sqlite3.Connection:
    try:
        connection = cstore.connect(db_path, project_root=project_root)
    except Exception as exc:  # cstore raises its own error type on a policy failure
        raise TargetProfileError(500, 'TARGET_PROFILE_STATE_UNAVAILABLE',
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


def _seed_id(profile_key: str) -> str:
    """A stable address for a config row, derived from its own key -- never a minted one."""
    return 'tprof-' + hashlib.sha256(f'seed:{profile_key}'.encode('utf-8')).hexdigest()[:32]


def load_seeds() -> list[dict]:
    """The tracked config, read whole and refused loudly if it contradicts itself."""
    try:
        document = json.loads(_SEED_PATH.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise TargetProfileError(500, 'TARGET_PROFILE_SEEDS_UNREADABLE',
                                 f'cannot read {_SEED_PATH.name}: {exc}') from None
    seeds = document.get('seeds')
    if not isinstance(seeds, list) or not seeds:
        raise TargetProfileError(500, 'TARGET_PROFILE_SEEDS_EMPTY',
                                 f'{_SEED_PATH.name} carries no seeds population')
    for seed in seeds:
        _check_profile_shape(seed, source=_SEED_PATH.name)
    return seeds


def _check_profile_shape(profile, *, source) -> None:
    key = profile.get('profile_key')
    if not isinstance(key, str) or not key.strip():
        raise TargetProfileError(500, 'TARGET_PROFILE_SEED_MALFORMED',
                                 f'{source}: a profile carries no profile_key')
    fields = profile.get('fields')
    if not isinstance(fields, dict):
        raise TargetProfileError(500, 'TARGET_PROFILE_SEED_MALFORMED', f'{key}: fields missing')
    missing = [name for name in CAPABILITY_FIELDS if name not in fields]
    if missing:
        raise TargetProfileError(500, 'TARGET_PROFILE_SEED_INCOMPLETE',
                                 f'{key}: capability fields absent {missing}')
    for name, field in fields.items():
        if name not in CAPABILITY_FIELDS:
            raise TargetProfileError(500, 'TARGET_PROFILE_SEED_INVENTED_FIELD',
                                     f'{key}: {name} is not in the 02:64 field list')
        _check_field(key, name, field)


def _check_field(profile_key, name, field) -> None:
    state = field.get('state')
    if state not in FIELD_STATES:
        raise TargetProfileError(500, 'TARGET_PROFILE_FIELD_STATE_INVALID',
                                 f'{profile_key}.{name}: {state!r} is not one of {FIELD_STATES}')
    provenance = field.get('provenance')
    if provenance not in PROVENANCE_KINDS:
        raise TargetProfileError(500, 'TARGET_PROFILE_PROVENANCE_INVALID',
                                 f'{profile_key}.{name}: {provenance!r} is not a known kind')
    if field.get('value') is None and state != 'UNKNOWN':
        raise TargetProfileError(500, 'TARGET_PROFILE_FIELD_VALUE_MISSING',
                                 f'{profile_key}.{name}: state {state} must carry a value')
    if state == 'UNKNOWN' and not (field.get('reason') or '').strip():
        raise TargetProfileError(500, 'TARGET_PROFILE_UNKNOWN_UNEXPLAINED',
                                 f'{profile_key}.{name} is UNKNOWN without a reason -- an empty '
                                 'cell has to say why it is empty')
    if state == 'DOCUMENTED' and provenance == 'OFFICIAL_DOC':
        if not (field.get('source') or '').strip() or not field.get('observed_at'):
            raise TargetProfileError(500, 'TARGET_PROFILE_CLAIM_UNCITED',
                                     f'{profile_key}.{name}: a documented official claim must name '
                                     'its URL and the day it was read')


def _profile_document(profile, *, origin) -> dict:
    """The stored form: identity axes, graded fields, and the two constants the page shows.

    An axis left null gets an explicit reason instead of staying blank. The pack's own wording is
    「未知可空并解释原因，不能自动补支持」 (07 line 29), and a blank cell that explains nothing is
    how a missing answer later reads as a permission.
    """
    key = profile['profile_key']
    reasons = {}
    for name in AXIS_FIELDS:
        if profile.get(name) is None:
            reasons[name] = (profile.get(f'{name}_reason')
                             or '调用方未填写该轴；档案按未提供保留，不自动补支持。')
    return {
        'schemaVersion': PROFILE_VERSION,
        'profile_id': profile.get('profile_id') or _seed_id(key),
        'profile_key': key,
        'origin': origin,
        'support_state': profile['support_state'],
        'conditional_reason': profile.get('conditional_reason'),
        'reach_attempts': profile.get('reach_attempts') or [],
        'axes': {name: profile.get(name) for name in AXIS_FIELDS},
        'axis_reasons': reasons,
        'fields': profile['fields'],
        'executable': False,
        'external_run_record': None,
        'content_sha256': None,
    }


def _check(document, path, label, *, registry=None):
    try:
        problems = schema_errors(load_schema(path), document, registry=registry)
    except (InteropError, OSError) as exc:
        raise TargetProfileError(500, 'TARGET_PROFILE_CONTRACT_UNREADABLE',
                                 f'cannot load {path.name} for {label}: {exc}') from None
    if problems:
        raise TargetProfileError(500, 'TARGET_PROFILE_CONTRACT_VIOLATION', problems)
    return document


_registry = None


def _ref_registry():
    """The profile contract, registered by its own $id so one schema owns the shape.

    The list and write answers $ref it rather than restating the field object: a second copy is
    how two versions of one contract get shipped at the same time.
    """
    global _registry
    if _registry is None:
        try:
            document = load_schema(_PROFILE_SCHEMA_PATH)
        except (InteropError, OSError) as exc:
            raise TargetProfileError(
                500, 'TARGET_PROFILE_CONTRACT_UNREADABLE',
                f'cannot load {_PROFILE_SCHEMA_PATH.name} for $ref resolution: {exc}') from None
        identifier = document.get('$id')
        if not isinstance(identifier, str):
            raise TargetProfileError(
                500, 'TARGET_PROFILE_CONTRACT_UNREADABLE',
                f'{_PROFILE_SCHEMA_PATH.name} carries no $id, so a $ref into it cannot be resolved '
                'offline')
        _registry = resource_registry({identifier: document})
    return _registry


def _required_text(value, field, *, max_len=2000):
    if not isinstance(value, str) or not value.strip():
        raise TargetProfileError(400, 'TARGET_PROFILE_FIELD_MISSING',
                                 f'{field} is required and must be a non-empty string')
    value = value.strip()
    if len(value) > max_len:
        raise TargetProfileError(400, 'TARGET_PROFILE_FIELD_TOO_LONG',
                                 f'{field} exceeds {max_len} characters')
    return value


def _draft_fields(value):
    """A draft grades every field itself, but cannot claim a measurement it did not run."""
    if not isinstance(value, dict):
        raise TargetProfileError(400, 'TARGET_PROFILE_FIELDS_MALFORMED',
                                 'fields must be an object keyed by the 02:64 field names')
    extra = sorted(set(value) - set(CAPABILITY_FIELDS))
    if extra:
        raise TargetProfileError(400, 'TARGET_PROFILE_FIELD_NOT_IN_CONTRACT',
                                 f'fields outside the contracted list: {extra}')
    fields = {}
    for name in CAPABILITY_FIELDS:
        entry = value.get(name)
        if entry is None:
            # An omitted field is UNKNOWN, never absent: the page must be able to show the gap.
            fields[name] = {'state': 'UNKNOWN', 'value': None, 'provenance': 'USER_FEEDBACK',
                            'reason': '用户在草稿里未填写该字段', 'source': None,
                            'observed_at': None}
            continue
        if not isinstance(entry, dict):
            raise TargetProfileError(400, 'TARGET_PROFILE_FIELD_MALFORMED',
                                     f'{name} must be an object with state/value/provenance')
        field = dict(entry)
        field.setdefault('state', 'UNKNOWN')
        field.setdefault('provenance', 'USER_FEEDBACK')
        if field['provenance'] in UNWRITABLE_PROVENANCE:
            raise TargetProfileError(
                409, 'TARGET_PROFILE_MEASUREMENT_NOT_AVAILABLE',
                f'{name}: 本项目实测 cannot be written. This round runs no external product or '
                'model; recording a measurement needs a run record bound to a real call and a '
                'readback, which no draft can supply.')
        if field['state'] == 'UNKNOWN' and not (field.get('reason') or '').strip():
            raise TargetProfileError(400, 'TARGET_PROFILE_UNKNOWN_UNEXPLAINED',
                                     f'{name} is UNKNOWN without a reason')
        if field['state'] == 'DOCUMENTED' and not (field.get('source') or '').strip():
            raise TargetProfileError(400, 'TARGET_PROFILE_CLAIM_UNCITED',
                                     f'{name}: a documented field must name where it was read')
        fields[name] = field
    return fields


class TargetProfiles:
    """One service object, mounted per project state database."""

    def __init__(self, service):
        self.service = service
        self.paths = service.paths

    def _connect(self):
        return connect(self.paths.database_path(self.service.database),
                       project_root=self.paths.project_root)

    def axes(self) -> dict:
        """The vocabulary the selection panel needs before it can ask a question."""
        seeds = load_seeds()
        document = {
            'schemaVersion': AXES_VERSION,
            'capability_fields': [{'key': name, 'label': FIELD_LABELS[name]}
                                 for name in CAPABILITY_FIELDS],
            'axes': [{'key': name, 'label': AXIS_LABELS[name]} for name in AXIS_FIELDS],
            'provenance_kinds': [{'key': name, 'label': PROVENANCE_LABELS[name]}
                                for name in PROVENANCE_KINDS],
            'field_states': list(FIELD_STATES),
            'support_states': list(SUPPORT_STATES),
            'entry_kinds': list(ENTRY_KINDS),
            'validate_dimensions': list(VALIDATE_DIMENSIONS),
            'verdicts': list(VERDICTS),
            'software': sorted({seed['software'] for seed in seeds}),
            'task_modes': sorted({seed['task_mode'] for seed in seeds}),
            'measured_fields': sum(1 for seed in seeds for field in seed['fields'].values()
                                   if field['provenance'] == 'PROJECT_MEASURED'),
            'measured_note': ('这一列现数，不写死：本轮它必须是 0，因为没有跑过任何外部产品或模型。'
                             '面板上「本项目未测试」与「官方支持」因此必须是两列，不能合成一个分数。'),
            'executable': False,
        }
        return _check(document, _AXES_SCHEMA_PATH, 'the axes answer')

    def list(self, *, offset=0, limit=DEFAULT_LIMIT) -> dict:
        # Refuse loudly rather than letting an out-of-range page fail inside the contract check:
        # a 500 CONTRACT_VIOLATION would report a caller's typo as a defect in the registry.
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_LIMIT:
            raise TargetProfileError(400, 'TARGET_PROFILE_LIMIT_INVALID',
                                     f'limit must be an integer between 1 and {MAX_LIMIT}')
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise TargetProfileError(400, 'TARGET_PROFILE_OFFSET_INVALID',
                                     'offset must be an integer of at least 0')
        profiles = [self._seed_profile(seed) for seed in load_seeds()]
        with closing(self._connect()) as conn:
            profiles += [self._row_profile(row) for row in conn.execute(
                'SELECT d.* FROM target_profile_draft d JOIN ('
                '  SELECT profile_id, MAX(revision) AS revision FROM target_profile_draft'
                '  GROUP BY profile_id) c ON c.profile_id = d.profile_id AND c.revision = d.revision'
                ' ORDER BY d.created_at, d.profile_id').fetchall()]
        total = len(profiles)
        page = profiles[offset:offset + limit]
        document = {
            'schemaVersion': LIST_VERSION,
            'total': total, 'offset': offset, 'limit': limit,
            'profiles': page,
            'support_histogram': {state: sum(1 for p in profiles
                                           if p['support_state'] == state)
                                 for state in SUPPORT_STATES},
            'provenance_histogram': self._provenance_histogram(profiles),
            'executable': False,
        }
        return _check(document, _LIST_SCHEMA_PATH, 'the profile list', registry=_ref_registry())

    def _provenance_histogram(self, profiles) -> dict:
        counts = {kind: 0 for kind in PROVENANCE_KINDS}
        for profile in profiles:
            for field in profile['fields'].values():
                counts[field['provenance']] += 1
        return counts

    def detail(self, profile_id: str) -> dict:
        profile_id = _required_text(profile_id, 'profile_id', max_len=80)
        for seed in load_seeds():
            if _seed_id(seed['profile_key']) == profile_id:
                return self._seed_profile(seed)
        with closing(self._connect()) as conn:
            row = conn.execute('SELECT * FROM target_profile_draft WHERE profile_id = ?'
                               ' ORDER BY revision DESC LIMIT 1', (profile_id,)).fetchone()
        if row is None:
            raise TargetProfileError(404, 'TARGET_PROFILE_NOT_FOUND',
                                     f'no profile {profile_id} is registered; a profile is either '
                                     'a seeded row in the tracked config or a draft somebody wrote')
        return self._row_profile(row)

    def create(self, value: dict) -> dict:
        if not isinstance(value, dict):
            raise TargetProfileError(400, 'TARGET_PROFILE_WRITE_MALFORMED', 'body must be an object')
        unexpected = sorted(set(value) - set(REQUEST_FIELDS))
        if unexpected:
            raise TargetProfileError(400, 'TARGET_PROFILE_REQUEST_FIELD_NOT_IN_CONTRACT',
                                     f'the create route does not accept {unexpected}; a draft '
                                     'cannot invent a column and have it stored')
        software = _required_text(value.get('software'), 'software', max_len=200)
        entry = value.get('entry')
        if entry not in ENTRY_KINDS:
            raise TargetProfileError(400, 'TARGET_PROFILE_ENTRY_INVALID',
                                     f'entry must be one of {ENTRY_KINDS}')
        task_mode = _required_text(value.get('task_mode'), 'task_mode', max_len=200)
        actor = _required_text(value.get('actor'), 'actor', max_len=200)
        # An external identifier is the user's to fill; an absent one stays the literal UNUSED
        # rather than something this module invented and later shows as a source.
        source_ref = value.get('source_ref')
        if source_ref is None or not str(source_ref).strip():
            source_ref = UNUSED
        profile = {
            'profile_key': f'draft:{software}',
            'profile_id': 'tprof-' + uuid.uuid4().hex,
            'software': software,
            'agent': value.get('agent'),
            'model': value.get('model'),
            'provider': value.get('provider'),
            'version': value.get('version'),
            'entry': entry,
            'task_mode': task_mode,
            'support_state': 'USER_DRAFT',
            'fields': _draft_fields(value.get('fields') or {}),
        }
        document = _profile_document(profile, origin='DRAFT')
        document['source_ref'] = str(source_ref).strip()[:200]
        document['content_sha256'] = _digest(document)
        _check(document, _PROFILE_SCHEMA_PATH, 'a profile draft readback')
        with closing(self._connect()) as conn:
            conn.execute('INSERT INTO target_profile_draft (profile_id, revision, support_state,'
                         ' content_sha256, document_json, created_at, created_by)'
                         ' VALUES (?, 1, ?, ?, ?, ?, ?)',
                         (document['profile_id'], 'USER_DRAFT', document['content_sha256'],
                          _canonical(document), _now(), actor))
            conn.commit()
        return _check({'schemaVersion': WRITE_VERSION, 'status': 'TARGET_PROFILE',
                       'stored': True, 'profile': document, 'revision': 1,
                       'claims_not_made': list(CLAIMS_NOT_MADE)},
                      _WRITE_SCHEMA_PATH, 'a profile draft write',
                      registry=_ref_registry())

    def validate(self, profile_id: str, value: dict) -> dict:
        """What the profile's own fields say about a proposed input. Never whether it will run."""
        profile = self.detail(profile_id)
        if not isinstance(value, dict):
            raise TargetProfileError(400, 'TARGET_PROFILE_INPUT_MALFORMED',
                                     'the input to validate must be an object')
        dimensions = value.get('dimensions') or {}
        if not isinstance(dimensions, dict):
            raise TargetProfileError(400, 'TARGET_PROFILE_INPUT_MALFORMED',
                                     'dimensions must be an object')
        unknown_keys = sorted(set(dimensions) - set(VALIDATE_DIMENSIONS))
        if unknown_keys:
            raise TargetProfileError(400, 'TARGET_PROFILE_DIMENSION_NOT_IN_CONTRACT',
                                     f'dimensions outside the contracted list: {unknown_keys}')
        verdicts = []
        for dimension in VALIDATE_DIMENSIONS:
            if dimension not in dimensions:
                continue
            verdicts.append(self._verdict(profile, dimension, dimensions[dimension]))
        document = {
            'schemaVersion': VALIDATE_VERSION,
            'profile_id': profile['profile_id'],
            'profile_key': profile['profile_key'],
            'support_state': profile['support_state'],
            'verdicts': verdicts,
            'conflicts': [profile['fields']['known_conflicts']],
            'executable': False,
            'execution_note': ('校验只回答档案里写了什么，不回答能不能跑：本轮没有任何外部调用，'
                              '任何 verdict 都不授予可执行状态。'),
            'fallback': profile['fields']['fallback'],
        }
        return _check(document, _VALIDATE_SCHEMA_PATH, 'a validation answer', registry=_ref_registry())

    def _verdict(self, profile, dimension, asked) -> dict:
        field = profile['fields'][_DIMENSION_FIELD[dimension]]
        state = field['state']
        if profile['support_state'] == 'UNREACHED' or state == 'UNKNOWN':
            verdict = 'UNKNOWN'
            reason = (field.get('reason') or '档案未记录该维度')
        elif state == 'NOT_DOCUMENTED':
            verdict = 'NOT_APPLICABLE'
            reason = f'该维度对本入口不适用：{field.get("value") or field.get("reason", "")}'
        else:
            text = json.dumps(field.get('value'), ensure_ascii=False)
            blocked = [token for token in ('不支持', '不接受', '不适用', 'does not support',
                                           'not supported') if token in text]
            verdict = 'DOCUMENTED_NOT_SUPPORT' if blocked else 'DOCUMENTED_SUPPORT'
            reason = ('档案正文把这一项写成了否定，按原样报告，不软化'
                      if blocked else '档案正文正面记录了这一项')
        return {'dimension': dimension, 'asked': asked, 'verdict': verdict,
                'field': _DIMENSION_FIELD[dimension], 'provenance': field['provenance'],
                'source': field.get('source'), 'observed_at': field.get('observed_at'),
                'reason': reason, 'grants_execution': False}

    def _seed_profile(self, seed) -> dict:
        document = _profile_document(seed, origin='SEEDED')
        document['fetch_note'] = seed.get('fetch_note')
        document['seed_file'] = _SEED_PATH.name
        document['content_sha256'] = _digest(document)
        return document

    def _row_profile(self, row) -> dict:
        document = json.loads(row['document_json'])
        if document['content_sha256'] != row['content_sha256']:
            raise TargetProfileError(500, 'TARGET_PROFILE_BYTES_MOVED',
                                     f'{row["profile_id"]} revision {row["revision"]} no longer '
                                     'hashes to what was stored')
        document['revision'] = row['revision']
        document['created_at'] = row['created_at']
        document['created_by'] = row['created_by']
        return document
