# SPDX-License-Identifier: MIT
"""Three handoff materials for one plan, rendered from the same neutral intent (DL-KB-11).

A plan is written down once; the person leaving this service needs it in the shape the next tool
reads. This module renders **Markdown**, **plain text**, **structured JSON** and the **分镜 CSV**
from one builder -- ``_intent()`` -- so "the three exports say the same thing" is a property of the
code, not three hand-copied templates that drift a section at a time. Each renderer changes framing
only: headings, list markers, column order. Nothing in a renderer is allowed to know a fact the
builder did not put in the model, which is what B4 ("三种导出信息一致") actually requires.

What every answer carries, in all four formats:

* the plan **revision** it exported and that revision's content digest -- so a reader can tell
  which version they are holding three weeks later;
* the **pinned reference snapshot** (kind / id / revision / content digest) exactly as the plan
  recorded it. The snapshot is read from the stored document, not re-resolved: an export freezes
  the dependencies the plan claimed, and whether any of them has since moved is the readback's
  job (``reference_status``), not something a handed-off file may quietly restate;
* the **emitter contract version** (``design-lab/plan-export/v1``), so a material produced by an
  older renderer stays distinguishable from one produced by a newer one;
* an explicit **not-executed statement**: rendered text is not a run. Nothing was sent, no external
  step was dispatched, no model or tool produced anything here.

Exporting changes no state. It writes nothing, so ``sent`` and ``executed`` cannot move -- and this
service has no outbound transport for either word; the answer reports the plan's own four states as
the readback computed them and repeats ``externally_verified: false``. A download is a file landing
in the designer's Downloads folder. Saying 「已发送」 about that would be the exact false claim this
card forbids, so the strings 「已发送」/「发送成功」/「delivered」/「模型已执行」 appear nowhere in an
exported byte; ``design-lab/tests/test_plan_export.py`` reads every format to prove it.

Two refusals are the point of this route rather than edge cases:

``PLAN_EXPORT_NO_SHOTS`` (409)
    A 分镜表 with no shot rows is not a storyboard, it is an empty table wearing one. A plan whose
    output type has no 分镜 (a poster, a brand guideline) normally has none at all, so the CSV
    format refuses and names the next step instead of answering 200 with a header row.

The pairing of shot rows with an output type that has none is not refused here: it is refused where
the rows are filed (``assistance_plan._shots``, 409 ``ASSISTANCE_PLAN_SHOTS_NOT_APPLICABLE``), so a
plan can never reach an export holding rows its own output type says it does not have.

Spreadsheet formula injection is a real concern and is deliberately NOT solved by rewriting the
content. The card forbids mutating what a person wrote (a 镜头说明 beginning with ``=`` or ``+`` is
their text, and a back-tick or a leading apostrophe inserted here would be this service editing a
designer's words on the way out). So every field goes through ``csv.writer`` untouched -- RFC4180
quoting only, with ``lineterminator='\\r\\n'`` and a leading BOM so the file opens with CJK text
readable -- and the export instead states the handling rule the reader has to apply: open the sheet
with formula evaluation off, or import the columns as text.

Nothing here proves a model ran: the bytes are rendered from a stored record of a person's intent.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json

from .assistance_plan import AssistancePlans, OUTPUT_LABELS, UNUSED
from .interop import InteropError, load_schema, schema_errors
from .runtime.state_resources import repo_resource

#: The emitter contract version. Named by the ledger row in
#: design-lab/config/contract-bindings.json as this route's emitter pointer, and written into every
#: answer as both ``schemaVersion`` and ``emitter_version`` -- the second one travels inside the
#: exported JSON body, where a reader holds the material without the envelope.
EXPORT_VERSION = 'design-lab/plan-export/v1'
PLAN_SCHEMA_VERSION = 'design-lab/assistance-plan/v1'

_SCHEMA_PATH = repo_resource('schemas/plan-export-v1.schema.json')

#: The closed set of formats this route renders. One word per material, named in the query, and an
#: unknown word is refused by name -- a format the page offers but the emitter cannot produce is
#: the false-green shape ``design-lab/tests/test_deliverable_claims_match_emitters.py`` already
#: refuses elsewhere, so the list lives here and the screen reads it.
FORMATS = ('markdown', 'txt', 'json', 'storyboard_csv')
FORMAT_LABELS = {'markdown': 'Markdown 文档', 'txt': '纯文本', 'json': '结构化 JSON',
                 'storyboard_csv': '分镜表 CSV'}
CONTENT_TYPES = {'markdown': 'text/markdown', 'txt': 'text/plain',
                 'json': 'application/json', 'storyboard_csv': 'text/csv'}
EXTENSIONS = {'markdown': 'md', 'txt': 'txt', 'json': 'json', 'storyboard_csv': 'csv'}

#: The shot table's columns. The first six are ``assistance_plan.SHOT_FIELDS`` in the plan's own
#: order; the last three are what makes a loose printout traceable -- a spreadsheet cell alone says
#: nothing about which revision it came from or whether anything ran.
CSV_COLUMNS = ('index', 'duration_s', 'purpose', 'camera', 'sound', 'reference_role',
               'plan_revision', 'export_contract', 'execution_status')
BOM = '\ufeff'

#: Written into every material, in the reader's language and in the contract's. `NOT_EXECUTED` is
#: the sentence a person hands to a colleague; `NOT_EXECUTED_EN` is the same claim for the record.
NOT_EXECUTED = ('这份文件是按请求从已保存的方案渲染出来的：本机服务没有把它发给任何人或系统，'
                '没有派发外部步骤，也没有运行模型或工具来产出它。'
                '下载不等于交付，也不等于对方已经收到。')
NOT_EXECUTED_EN = ('Rendered on request from a stored plan. Nothing was sent and no external step '
                   'was dispatched: no model and no tool was run by this service to produce these '
                   'bytes. A download is not a delivery.')

#: The handling rule the reader has to apply, stated rather than enforced by rewriting content.
FORMULA_RULE = ('表格里的文字按填写人写下的原样导出，包括以 = + - @ 开头的单元格；'
                '本服务不修改这些内容，所以请在电子表格里以文本方式导入，'
                '或关闭公式自动求值后再编辑。')

#: Every answer says what it does not say. The plan's own claims travel with the stored document;
#: these three are about the export itself.
EXPORT_CLAIMS = (
    'a successful export means these bytes were rendered; it is not a record of a send, a '
    'delivery, an acknowledgement or a run',
    'the reference snapshot below is what this plan recorded at the time it was written; whether '
    'any referenced object has moved since is answered by the plan readback, not by this file',
    FORMULA_RULE,
)

#: The one word an unfilled field reads as. Deliberately the same word the plan screen already
#: prints for a plan-level ``UNKNOWN`` (``apps/workbench/shell.ts`` renders 未登记 for it), so an
#: export does not invent a second marker for the same fact and a designer reads two vocabularies.
_NOT_RECORDED = '未登记'


class PlanExportError(ValueError):
    """A refusal carrying the status and code the route answers with."""

    def __init__(self, status, code, detail=None):
        super().__init__(detail or code)
        self.status = status
        self.code = code
        self.detail = detail


def _check(document) -> dict:
    try:
        problems = schema_errors(load_schema(_SCHEMA_PATH), document)
    except (InteropError, OSError) as exc:
        raise PlanExportError(500, 'PLAN_EXPORT_CONTRACT_UNREADABLE',
                              f'cannot load {_SCHEMA_PATH.name} for the plan export: '
                              f'{exc}') from None
    if problems:
        raise PlanExportError(500, 'PLAN_EXPORT_CONTRACT_VIOLATION', problems)
    return document


def _text(value) -> str:
    """One cell's worth of a plan-level field, in the words a reader of the file understands.

    ``UNKNOWN`` is this service's stored marker for "nobody wrote this". Handing it to a designer
    as if it were their own note reads like a finding, so the prose forms say 未登记 -- the same
    word the plan screen prints; the stored bytes (and the JSON form, which serves the document
    verbatim) keep the marker itself.
    """
    if value is None or value == 'UNKNOWN':
        return _NOT_RECORDED
    return str(value)


def _items(values) -> list:
    """A list field, rendered item by item, or one honest line saying there are none."""
    cleaned = [str(value) for value in (values or []) if str(value)]
    return cleaned or [_NOT_RECORDED]


def _duration(value) -> str:
    """A duration as the person meant it: 5 not 5.0, and blank when the row does not say."""
    if value is None:
        return ''
    number = float(value)
    return str(int(number)) if number.is_integer() else repr(number)


def _intent(document, readback) -> dict:
    """The one canonical view every renderer reads. Framing lives in the renderers; facts do not.

    Nothing here re-reads the database: the plan document is the stored bytes the detail route
    served, and the reference snapshot is the pinned list inside that document. That is what lets
    two exports of the same revision answer with identical bytes. ``stored`` carries the document
    itself because the JSON material hands those bytes back rather than a summary of them.
    """
    states = readback['states']
    choice = readback['choice']
    external = readback['external']
    shots = [dict(row) for row in (document.get('shots') or [])]
    supplied = [entry for entry in external['supplied_ids'] if entry != UNUSED]
    references = [{'kind': entry['kind'], 'id': entry['id'], 'revision': entry['revision'],
                   'content_sha256': entry['sha256']} for entry in document['references']]
    model = {
        'plan_id': document['plan_id'],
        'revision': document['revision'],
        'objective': document['objective'],
        'output_type': document['output_type'],
        'output_label': OUTPUT_LABELS.get(document['output_type'], document['output_type']),
        'created_at': document['created_at'],
        'created_by': document['created_by'],
        'content_sha256': document['content_sha256'],
        'creative': _text(document['neutral_creative']),
        'brand_constraints': _items(document['brand_constraints']),
        'role_constraints': _items(document['role_constraints']),
        'lens': _text(document['lens']),
        'sound': _text(document['sound']),
        'shots': shots,
        'limits': _items(document['limits']),
        'known_gaps': _items(document['known_gaps']),
        'steps': document['external_steps'],
        'references': references,
        'supplied_ids': supplied,
        'states': states,
        'choice': choice,
        'claims_not_made': list(document['claims_not_made']),
        'does_not_say': list(readback['does_not_say']),
        'export_claims': list(EXPORT_CLAIMS),
        'not_executed': NOT_EXECUTED,
        'not_executed_en': NOT_EXECUTED_EN,
        'emitter_version': EXPORT_VERSION,
        'plan_schema_version': PLAN_SCHEMA_VERSION,
        'stored': document,
        'provided': bool(states['provided']),
    }
    return model


def shot_line(row: dict) -> str:
    """One shot as one readable line -- the form the prose materials and the screen share."""
    duration = _duration(row['duration_s'])
    parts = [f"镜头 {row['index']}",
             f'时长 {duration} 秒' if duration else '时长未定',
             row['purpose']]
    for key, label in (('camera', '镜头运动'), ('sound', '声音'),
                       ('reference_role', '参考角色')):
        if row.get(key):
            parts.append(f"{label}：{row[key]}")
    return ' · '.join(parts)


def sections(model: dict) -> list:
    """The ordered (title, lines) content every prose renderer writes.

    One table, two framings: the Markdown path prints each title as a heading and each value as a
    list item, the text path prints the same titles and the same values with plain markers. A limit
    that is missing from TXT is therefore a missing row here, not a template someone forgot to
    update -- which is the failure mode B4 is written against.
    """
    rows = []
    rows.append(('设计目标', [model['objective']]))
    rows.append(('输出类型', [model['output_label']]))
    rows.append(('记录人与记录时间', [f"{model['created_by']} · {model['created_at']}"]))
    rows.append(('设计建议正文',
                 [model['creative']] if model['provided']
                 else [model['creative'],
                       '这条方案已经保存，但还没有写到创意。']))
    rows.append(('品牌约束', model['brand_constraints']))
    rows.append(('角色约束', model['role_constraints']))
    rows.append(('镜头 / 视角要求', [model['lens']]))
    rows.append(('声音要求', [model['sound']]))
    rows.append(('镜头表（分镜）',
                 [shot_line(row) for row in model['shots']]
                 or ['这份方案没有登记镜头行，所以没有可交给拍摄的分镜表。']))
    rows.append(('边界（不做什么）', model['limits']))
    rows.append(('待补充内容', model['known_gaps']))
    rows.append(('外部步骤登记',
                 [f"{step['step']} · 工具 {step['tool']} · 作业编号 {step['job_id']}"
                  f" · 操作编号 {step['operation_id']}" for step in model['steps']]
                 or ['本方案没有登记外部步骤。']))
    rows.append(('参考与依据（写入时固定的版本与摘要）',
                 [f"{entry['kind']} {entry['id']} · 修订 {entry['revision']}"
                  f" · {entry['content_sha256']}" for entry in model['references']]
                 or ['这条方案没有登记参考。']))
    rows.append(('当前状态', [
        '已保存',
        '方案已提供创意' if model['states']['provided'] else '尚未提供创意',
        (f"用户选用 r{model['choice']['revision']} · {model['choice']['actor']}"
         if model['states']['chosen'] else '尚无具名人工选用'),
        '外部步骤登记 ' + str(len(model['steps'])) + ' 条'
        + (f"，其中 {len(model['supplied_ids'])} 个编号由填写人写明"
           if model['supplied_ids'] else '，没有登记任何外部编号')
        + '；本服务未派发、未核验这些步骤。',
        '外部结果未被系统核验。']))
    rows.append(('这份材料没有说的话', model['does_not_say'] + model['claims_not_made']
                 + [model['not_executed'], model['not_executed_en'], FORMULA_RULE]))
    return rows


def _snapshot(model: dict) -> dict:
    """The dependency header the JSON form carries and the envelope reports field by field."""
    return {
        'emitter_version': model['emitter_version'],
        'plan_schema_version': model['plan_schema_version'],
        'plan_id': model['plan_id'],
        'revision': model['revision'],
        'plan_content_sha256': model['content_sha256'],
        'references': [dict(entry) for entry in model['references']],
        'shot_count': len(model['shots']),
        'external_verified': False,
        'sent': False,
        'executed': False,
        'not_executed': model['not_executed'],
        'not_executed_en': model['not_executed_en'],
        'claims_not_made': list(model['export_claims']),
    }


def render_markdown(model: dict) -> str:
    lines = [f"# 设计辅助方案 · r{model['revision']} · {model['objective']}", '']
    lines.append(f"导出合同版本：`{model['emitter_version']}` · "
                 f"方案正文摘要：`{model['content_sha256']}`")
    lines.append('')
    for title, values in sections(model):
        lines.append(f'## {title}')
        for value in values:
            lines.append(f'- {value}')
        lines.append('')
    lines.append(f"*{model['not_executed']}*")
    return '\n'.join(lines).rstrip() + '\n'


def render_text(model: dict) -> str:
    lines = [f'设计辅助方案 · r{model["revision"]} · {model["objective"]}',
             f'导出合同版本：{model["emitter_version"]} · '
             f'方案正文摘要：{model["content_sha256"]}',
             '']
    for title, values in sections(model):
        lines.append(f'【{title}】')
        for value in values:
            lines.append(f'- {value}')
        lines.append('')
    lines.append(model['not_executed'])
    return '\n'.join(lines).rstrip() + '\n'


def render_json(model: dict) -> str:
    """The stored document itself plus the snapshot header -- not a rebuilt summary of it."""
    return json.dumps({'export': _snapshot(model), 'plan': model['stored']},
                      ensure_ascii=False, indent=2, sort_keys=True) + '\n'


def render_csv(model: dict) -> str:
    """The shot table, RFC4180-quoted, BOM first, with the provenance columns on every row.

    Every field is written *through* ``csv.writer``: a 镜头说明 containing a double quote, a comma
    or a newline survives as the person typed it, because the writer quotes it and nothing here
    strips, backslash-escapes or otherwise rewrites the text (see the module docstring on formula
    cells). ``lineterminator='\\r\\n'`` is what RFC4180 requires and what a spreadsheet expects.
    The revision, the emitter version and the not-executed statement ride as trailing columns so
    one printed row still answers "which version, and did anything run?" outside the file's header.
    """
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\r\n')
    writer.writerow(list(CSV_COLUMNS))
    for row in model['shots']:
        writer.writerow([row['index'], _duration(row['duration_s']), row['purpose'],
                         row['camera'] or '', row['sound'] or '', row['reference_role'] or '',
                         model['revision'], model['emitter_version'], model['not_executed']])
    return BOM + stream.getvalue()


#: One renderer per format, all taking the same canonical model. This table, not an if-chain, is
#: what makes ``FORMATS`` an honest claim: a format listed here without a renderer would be a
#: button the page could press and the service could not answer, which is exactly the shape
#: design-lab/tests/test_deliverable_claims_match_emitters.py convicts in the delivery layer.
RENDERERS = {'markdown': render_markdown, 'txt': render_text, 'json': render_json,
             'storyboard_csv': render_csv}


def material_table() -> list:
    """The formats this emitter can actually render, in the shape a screen offers them.

    ``FORMATS`` is the emitter's own list and ``RENDERERS`` is the proof behind it; the Workbench
    reads this table rather than typing the four words a second time, so a format that stops
    rendering disappears from the buttons instead of becoming one that answers 500. A word in
    ``FORMATS`` with no renderer is refused here -- that is the assertion, and the route raises the
    same code it raises for its own dispatch.
    """
    missing = [fmt for fmt in FORMATS if fmt not in RENDERERS]
    if missing:
        raise PlanExportError(500, 'PLAN_EXPORT_RENDERER_MISSING',
                              f'offered but not rendered: {missing}')
    return [{'value': fmt, 'label': FORMAT_LABELS[fmt], 'content_type': CONTENT_TYPES[fmt],
             'extension': EXTENSIONS[fmt]} for fmt in FORMATS]


def filename_for(model: dict, fmt: str) -> str:
    """A name a person recognises later: what it is, which plan, which revision.

    The plan id is truncated to the same 8 hex characters the screen shows, because a full id in a
    filename is noise a designer cannot use and the revision is the part that answers "which one?".
    """
    return f'design-plan-{model["plan_id"][6:14]}-r{model["revision"]}.{EXTENSIONS[fmt]}'


class PlanExport:
    def __init__(self, service):
        self.service = service
        self.plans = AssistancePlans(service)

    def export(self, project_id, plan_id, fmt) -> dict:
        """Render one stored revision. Reads the plan; writes nothing; changes no state."""
        if fmt is None or fmt == '':
            raise PlanExportError(
                400, 'PLAN_EXPORT_FORMAT_REQUIRED',
                '导出要在查询里写明 format，可取 ' + '、'.join(FORMATS)
                + '；没有 format 时服务不猜测要哪一种材料。')
        if fmt not in FORMATS:
            raise PlanExportError(
                400, 'PLAN_EXPORT_FORMAT_INVALID',
                f'format 只能是 ' + '、'.join(FORMATS) + f'；收到 {fmt!r}。')
        # A plan that does not exist, and a plan that belongs to another project, both answer the
        # plan store's own 404 ASSISTANCE_PLAN_NOT_FOUND (detail() scopes the read by the plan's
        # owning project), so the page branches on one vocabulary for the whole plan family rather
        # than learning a second one for the export route.
        readback = self.plans.detail(project_id, plan_id)
        document = readback.get('current')
        if not isinstance(document, dict):
            raise PlanExportError(
                409, 'PLAN_EXPORT_REVISION_UNREADABLE',
                '这条方案最新的修订存的是无法解析的内容，服务不导出一个猜出来的版本：'
                '请先读回该方案确认修订历史，再决定是否需要新写一版。')
        if fmt == 'storyboard_csv' and not (document.get('shots') or []):
            raise PlanExportError(
                409, 'PLAN_EXPORT_NO_SHOTS',
                '这份方案没有登记任何镜头行，分镜 CSV 只能导出一张空表——空表不是分镜。'
                '下一步：写一版方案并带上 shots（每行一个镜头：序号、时长秒、这一镜头要完成什么，'
                '以及可选的镜头运动、声音、参考角色），输出类型需要是「分镜与脚本」或'
                '「动效与视频」；只要文字材料的话，markdown 与 txt 现在就能导出。')
        model = _intent(document, readback)
        # Fail closed rather than defaulting to a text file: a format the table does not know would
        # otherwise answer with a material the caller never asked for.
        renderer = RENDERERS.get(fmt)
        if renderer is None:
            raise PlanExportError(500, 'PLAN_EXPORT_RENDERER_MISSING',
                                  f'format {fmt!r} is offered but no renderer is bound to it')
        body = renderer(model)
        encoded = body.encode('utf-8')
        states = readback['states']
        return _check({
            'schemaVersion': EXPORT_VERSION,
            'format': fmt,
            'format_label': FORMAT_LABELS[fmt],
            'filename': filename_for(model, fmt),
            'content_type': CONTENT_TYPES[fmt],
            'encoding': 'utf-8',
            'body': body,
            'body_bytes': len(encoded),
            'body_sha256': 'sha256:' + hashlib.sha256(encoded).hexdigest(),
            'plan_id': plan_id,
            'project_id': project_id,
            'revision': document['revision'],
            'plan_content_sha256': document['content_sha256'],
            'plan_schema_version': PLAN_SCHEMA_VERSION,
            'emitter_version': EXPORT_VERSION,
            'reference_snapshot': [dict(entry) for entry in model['references']],
            'shot_count': len(model['shots']),
            'states': {'saved': states['saved'], 'provided': states['provided'],
                       'chosen': states['chosen'], 'externally_verified': False},
            'external_verified': False,
            'sent': False,
            'executed': False,
            'not_executed': NOT_EXECUTED,
            'claims_not_made': list(EXPORT_CLAIMS),
        })
