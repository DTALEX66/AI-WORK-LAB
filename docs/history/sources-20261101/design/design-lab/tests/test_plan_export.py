# SPDX-License-Identifier: MIT
"""DL-KB-11: three handoff materials from one neutral intent, and no claim that anything ran.

What this suite is for. An export is the moment a plan leaves this service, and the ways it can
start lying are specific:

* **three templates, three answers.** If Markdown, TXT and the JSON body were written separately,
  one of them loses a 边界 line and nothing notices. So the comparison here is per item, taken from
  the plan's own ``limits`` / ``known_gaps`` / claim lists: a limit that reaches Markdown but not
  TXT is a failure, not a formatting choice.
* **an empty table dressed as a storyboard.** A 分镜 CSV rendered from a plan that has no shot rows
  would be a fabricated deliverable, so the CSV refuses (409 ``PLAN_EXPORT_NO_SHOTS``) and names the
  next step. The shot rows themselves are stored data -- validated, digest-covered, and refused by
  name when they are malformed or filed under an output type that has no 分镜.
* **a download read as a delivery.** ``sent`` / ``executed`` / ``external_verified`` are constants
  false in the contract, and the exported bytes must not contain 「已发送」/「发送成功」/「delivered」/
  「模型已执行」 either. Exporting must also leave the plan's own four states byte-identical, the way
  the feedback row does.
* **internal vocabulary sold as delivery evidence.** Evidence axes, ledger states, module paths and
  commit SHAs mean nothing to the person receiving the file; here they are named and hunted.
* **a spreadsheet that eats the designer's text.** A 镜头说明 containing a quote, a comma or a newline
  has to survive the round trip intact -- the writer quotes it, nothing rewrites it.

Nothing in this file proves a model ran, an external job executed, or a file reached anybody: the
bytes are rendered from a local record of a person's intent, read back over a loopback socket.
"""
from __future__ import annotations

import csv
import http.client
import io
import json
import os
import secrets
import sys
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))

from design_lab import assistance_plan                                # noqa: E402
from design_lab import plan_export                                    # noqa: E402
from design_lab.assistance_plan import AssistancePlans                 # noqa: E402
from design_lab.http_service import make_server                        # noqa: E402
from design_lab.interop import load_schema, schema_errors               # noqa: E402
from design_lab.service import ProjectService                           # noqa: E402

FORMATS = plan_export.FORMATS
#: Words an export may never print, whatever the format. The first four are the card's own
#: forbidden claims; the rest are this repository's internal vocabulary, which is evidence about
#: our own governance and says nothing to a designer opening the file.
BANNED = ('已发送', '发送成功', 'delivered', '模型已执行', 'FROZEN_DEFERRED', 'E2',
          'project_id=', 'src/design_lab', 'apps/workbench', 'design-lab/tests',
          'D:/All projects', 'DL-KB', '.schema.json')

SHOTS = [
    {'index': 1, 'duration_s': 4, 'purpose': '开场：侧光落在纸纤维上',
     'camera': '缓推', 'sound': None, 'reference_role': '主参考'},
    # The row every CSV reader is written to break: a double quote, a comma and a newline, all in
    # the one cell a person typed.
    {'index': 2, 'duration_s': None,
     'purpose': '中景：标题落定，副标题带"引号"、逗号, 与\n换行的说明',
     'camera': None, 'sound': '低频垫底，无对白', 'reference_role': None},
    {'index': 3, 'duration_s': 2.5, 'purpose': '收束：留出落版空白',
     'camera': '固定', 'sound': None, 'reference_role': None},
]


def plan_body(**overrides):
    body = {
        'objective': '为秋季新品做一段十五秒主视觉动效',
        'output_type': 'MOTION',
        'neutral_creative': '侧光缓慢移动，标题以一次落定收束，全程留白承载品牌名。',
        'brand_constraints': ['只用两种油墨', '不使用渐变'],
        'role_constraints': ['面向线下门店大屏'],
        'lens': '固定机位为主，一次缓推',
        'sound': '无对白，一条低频垫底',
        'shots': [dict(row) for row in SHOTS],
        'references': [],
        'external_steps': [{'step': '手动导出 MP4', 'tool': 'After Effects',
                            'job_id': None, 'operation_id': 'op-plan-export-1'}],
        'known_gaps': ['节奏点未定', '落版字号未定'],
        'limits': ['不含多语言字幕', '不含真人出镜', '不产出可编辑源文件'],
        'created_by': 'owner',
    }
    body.update(overrides)
    return body


class PlanExportTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop('PROJECT_LOCAL_ROOT', None)
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        self.root = self.base / 'project'
        self.root.mkdir()
        (self.root / 'AGENTS.md').write_text('# plan export fixture', encoding='utf-8')
        self.token = secrets.token_hex(32)
        self.service = ProjectService(self.root)
        self.httpd = make_server(self.service, self.token, 0)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.project = self.service.create_project('Export Plan')['id']

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    def _call(self, method, path, body=None):
        headers = {'Authorization': 'Bearer ' + self.token}
        if body is not None:
            headers['Content-Type'] = 'application/json'
        with closing(http.client.HTTPConnection('127.0.0.1', self.httpd.server_port,
                                                timeout=20)) as conn:
            conn.request(method, path, body=None if body is None else json.dumps(body),
                         headers=headers)
            response = conn.getresponse()
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)

    def _create(self, **overrides):
        status, created = self._call('POST', f'/api/projects/{self.project}/assistance-plans',
                                     plan_body(**overrides))
        self.assertEqual(201, status, created)
        return created['plan']

    def _detail(self, plan_id):
        return self._call('GET', f'/api/projects/{self.project}/assistance-plans/{plan_id}')[1]

    def _export(self, plan_id, fmt):
        return self._call('GET', f'/api/projects/{self.project}/assistance-plans'
                                 f'/{plan_id}/export?format={fmt}')

    def _export_body(self, plan_id, fmt):
        status, answer = self._export(plan_id, fmt)
        self.assertEqual(200, status, answer)
        return answer['body'], answer

    def _append_revision(self, plan_id, document, created_by='owner'):
        """File one row holding exactly these bytes, the way the store would have written it.

        The revision table is append-only *by trigger* -- an UPDATE aborts, and that is the point of
        it -- so history that predates a field is reproduced as a new revision rather than by
        editing a stored one. What goes in is the document this test assembles, byte for byte.
        """
        with closing(assistance_plan.connect(
                self.service.database, project_root=self.service.paths.project_root)) as conn:
            top = conn.execute('SELECT MAX(revision) AS top FROM assistance_plan_revision'
                               ' WHERE plan_id=?', (plan_id,)).fetchone()['top']
            document = dict(document, revision=top + 1)
            conn.execute('INSERT INTO assistance_plan_revision (plan_id, revision, objective,'
                         ' output_type, content_sha256, created_at, created_by, document_json)'
                         ' VALUES (?,?,?,?,?,?,?,?)',
                         (plan_id, document['revision'], document['objective'],
                          document['output_type'], document['content_sha256'],
                          document.get('created_at', '2026-10-24T00:00:00Z'), created_by,
                          assistance_plan._canonical(document)))
            conn.commit()
        return document

    # -- B4: the three materials say the same thing ----------------------------------

    def test_every_prose_material_carries_every_stated_item(self):
        """Per item, from the plan's own lists -- so a limit dropped by one renderer is caught.

        Not "the three files look similar": each entry of 边界 / 待补充 / 服务声明 has to appear in
        Markdown, in TXT and in the JSON body, which is the stored document. A renderer that skips a
        section fails on the item that vanished with it.
        """
        plan = self._create()
        markdown, _ = self._export_body(plan['plan_id'], 'markdown')
        text, _ = self._export_body(plan['plan_id'], 'txt')
        json_body, _ = self._export_body(plan['plan_id'], 'json')
        prose = {'markdown': markdown, 'txt': text}
        stored = plan_body()
        items = (
            [plan['objective'], plan['neutral_creative'], plan['lens'], plan['sound']]
            + list(stored['limits']) + list(stored['known_gaps'])
            + list(stored['brand_constraints']) + list(stored['role_constraints'])
            + [row['purpose'] for row in stored['shots']]
            + [step['step'] for step in stored['external_steps']])
        self.assertGreaterEqual(len(items), 12, 'the fixture stopped carrying enough content '
                                                'for the comparison to mean anything')
        for item in items:
            for name, body in prose.items():
                self.assertIn(item, body, f'{name} lost the stated item {item!r}')
        # The JSON form is the stored document, so it is compared field by field rather than by
        # substring: a newline inside a 镜头说明 is escaped in those bytes, and the claim that
        # matters is that the decoded value is the one the plan holds.
        stored_document = self._detail(plan['plan_id'])['current']
        carried = json.loads(json_body)['plan']
        for field in ('objective', 'neutral_creative', 'lens', 'sound', 'limits', 'known_gaps',
                      'brand_constraints', 'role_constraints', 'shots', 'external_steps',
                      'claims_not_made'):
            self.assertEqual(stored_document[field], carried[field],
                             f'the JSON export does not carry the stored {field}')
        # And the three-way agreement, per item: whatever the JSON form carries as a list of stated
        # limits, gaps or constraints has to be printed by both prose materials.
        for field in ('limits', 'known_gaps', 'brand_constraints', 'role_constraints'):
            for item in carried[field]:
                for name, body in prose.items():
                    self.assertIn(item, body,
                                  f'{name} dropped the {field} item {item!r} the JSON export '
                                  'carries')
        for claim in carried['claims_not_made']:
            for name, body in prose.items():
                self.assertIn(claim, body, f'{name} stopped printing the claim {claim!r}')
        for line in self._detail(plan['plan_id'])['does_not_say']:
            for name, body in prose.items():
                self.assertIn(line, body, f'{name} stopped printing {line!r}')

    def test_the_two_prose_materials_render_the_same_section_list(self):
        plan = self._create()
        markdown, _ = self._export_body(plan['plan_id'], 'markdown')
        text, _ = self._export_body(plan['plan_id'], 'txt')
        titles = [title for title, _values in plan_export.sections(plan_export._intent(
            plan, self._detail(plan['plan_id'])))]
        self.assertGreaterEqual(len(titles), 12, titles)
        for title in titles:
            self.assertIn(title, markdown, f'markdown has no {title!r} section')
            self.assertIn(title, text, f'txt has no {title!r} section')

    def test_the_json_form_is_the_stored_document_not_a_rebuilt_summary(self):
        plan = self._create()
        body, _ = self._export_body(plan['plan_id'], 'json')
        document = json.loads(body)
        self.assertEqual(self._detail(plan['plan_id'])['current'], document['plan'],
                         'the JSON export re-rendered the plan instead of handing back the bytes '
                         'that are stored')
        self.assertEqual(assistance_plan.PLAN_VERSION, document['plan']['schemaVersion'])
        self.assertEqual(plan_export.EXPORT_VERSION, document['export']['emitter_version'])
        self.assertFalse(document['export']['sent'])
        self.assertFalse(document['export']['executed'])
        self.assertFalse(document['export']['external_verified'])

    def test_the_snapshot_pins_the_references_the_plan_recorded(self):
        """The export freezes what the plan said it used -- it does not re-resolve today's bytes."""
        plan = self._create()
        with closing(assistance_plan.connect(
                self.service.database, project_root=self.service.paths.project_root)) as conn:
            asset_id = 'img-' + 'c4' * 32
            conn.execute('INSERT INTO asset VALUES (?, ?, "raster", ?)',
                         (asset_id, self.project, '2026-10-24T00:00:00Z'))
            conn.execute('INSERT INTO asset_version (version_id, asset_id, version_no,'
                         ' content_sha256, state, created_at) VALUES (?,?,?,?,?,?)',
                         ('v-' + 'c4' * 16, asset_id, 1, 'sha256:' + 'c' * 64, 'ACTIVE',
                          '2026-10-24T00:00:00Z'))
            conn.commit()
        cited = self._create(references=[{'kind': 'ASSET', 'id': asset_id}])
        for fmt in FORMATS:
            _, answer = self._export(cited['plan_id'], fmt)
            self.assertEqual([{'kind': 'ASSET', 'id': asset_id, 'revision': 1,
                               'content_sha256': 'sha256:' + 'c' * 64}],
                             answer['reference_snapshot'], f'{fmt} lost the pinned snapshot')
        self.assertEqual(0, len(plan['references']))

    # -- B5: the export is a rendering, not an action -------------------------------

    def test_exporting_leaves_the_plan_states_and_verification_untouched(self):
        plan = self._create()
        before = json.dumps(self._detail(plan['plan_id']), sort_keys=True)
        for fmt in FORMATS:
            self.assertEqual(200, self._export(plan['plan_id'], fmt)[0], fmt)
        after = self._detail(plan['plan_id'])
        self.assertEqual(before, json.dumps(after, sort_keys=True),
                         'an export changed the plan it exported')
        self.assertFalse(after['external']['verified'])
        self.assertFalse(after['states']['externally_verified'])
        self.assertTrue(after['states']['saved'])

    def test_an_export_answer_reports_sent_and_executed_as_they_are(self):
        plan = self._create()
        for fmt in FORMATS:
            status, answer = self._export(plan['plan_id'], fmt)
            self.assertEqual(200, status, answer)
            self.assertIs(False, answer['sent'])
            self.assertIs(False, answer['executed'])
            self.assertIs(False, answer['external_verified'])
            self.assertIs(False, answer['states']['externally_verified'])
            self.assertEqual(plan['revision'], answer['revision'])
            self.assertEqual(plan['content_sha256'], answer['plan_content_sha256'])
            self.assertEqual(plan_export.EXPORT_VERSION, answer['emitter_version'])
            self.assertIn('没有把它发给任何人或系统', answer['not_executed'])
            self.assertIn('下载不等于交付', answer['not_executed'])

    def test_no_material_prints_a_forbidden_claim_or_internal_vocabulary(self):
        plan = self._create()
        for fmt in FORMATS:
            body, answer = self._export_body(plan['plan_id'], fmt)
            for word in BANNED:
                self.assertNotIn(word, body, f'{fmt} printed {word!r} in the exported bytes')
            # The envelope is what the page renders, so the claim is checked there too.
            joined = json.dumps(answer, ensure_ascii=False)
            for word in ('已发送', '发送成功', '模型已执行', 'FROZEN_DEFERRED'):
                self.assertNotIn(word, joined, f'{fmt} answered {word!r}')

    def test_the_emitter_holds_its_line_and_no_format_is_claimed_that_is_not_built(self):
        """The four formats are the ones this file can actually render, in both directions."""
        source = (REPO / 'src' / 'design_lab' / 'plan_export.py').read_text(encoding='utf-8')
        lines = source.splitlines()
        index = next((i for i, line in enumerate(lines, 1)
                      if line.startswith('EXPORT_VERSION = ')), None)
        self.assertIsNotNone(index, 'EXPORT_VERSION is no longer a module-level constant')
        self.assertIn(plan_export.EXPORT_VERSION, lines[index - 1])
        self.assertEqual(sorted(FORMATS), sorted(plan_export.FORMAT_LABELS),
                         'a format is offered without a label, or built without being offered')
        self.assertEqual(sorted(FORMATS), sorted(plan_export.CONTENT_TYPES))
        self.assertEqual(sorted(FORMATS), sorted(plan_export.EXTENSIONS))
        self.assertEqual(sorted(FORMATS), sorted(plan_export.RENDERERS),
                         'a format is in FORMATS with no renderer bound to it -- the page could '
                         'press the button and the service would answer with something else')
        for fmt, renderer in plan_export.RENDERERS.items():
            self.assertTrue(callable(renderer), fmt)
        http = (REPO / 'src' / 'design_lab' / 'http_service.py').read_text(encoding='utf-8')
        self.assertIn('assistance-plans/(aplan-[0-9a-f]{32})/export', http,
                      'the export route is not dispatched by the service')
        self.assertIn('PlanExport(service).export', http)
        self.assertIn('except PlanExportError', http)

    def test_the_material_list_the_screen_reads_is_the_list_the_emitter_renders(self):
        """DL-KB-11: the handoff vocabulary is served, so the page cannot offer an error.

        The design-assistant screen reads `GET /api/assistance-plan-output-types` before any plan
        exists; that envelope is therefore the only place it can learn which materials there are.
        Checked three ways: the served words are the emitter's own `FORMATS`, the served labels and
        types are the emitter's own tables, and every served word renders a real 200 whose envelope
        repeats that word, type and extension back.
        """
        status, vocabulary = self._call('GET', '/api/assistance-plan-output-types')
        self.assertEqual(200, status, vocabulary)
        served = vocabulary['export_formats']
        self.assertEqual([row['value'] for row in served], list(FORMATS),
                         'the served material list is not the list the emitter renders')
        self.assertEqual(served, plan_export.material_table(),
                         'the screen would be handed labels or types the emitter does not use')
        plan = self._create()
        for row in served:
            answer_status, answer = self._export(plan['plan_id'], row['value'])
            self.assertEqual(200, answer_status, answer)
            self.assertEqual(row['value'], answer['format'])
            self.assertEqual(row['label'], answer['format_label'])
            self.assertEqual(row['content_type'], answer['content_type'])
            self.assertTrue(answer['filename'].endswith('.' + row['extension']),
                            answer['filename'])

    # -- the CSV is the shot table, and the shot table is data ----------------------

    def test_a_shot_cell_with_quote_comma_and_newline_round_trips(self):
        plan = self._create()
        body, _ = self._export_body(plan['plan_id'], 'storyboard_csv')
        self.assertTrue(body.startswith('\ufeff'), 'the CSV must carry the byte-order mark so a'
                        ' spreadsheet opens the Chinese text readable')
        raw = body.encode('utf-8')
        self.assertEqual(b'\xef\xbb\xbf', raw[:3])
        # The repo's own reader precedent: design-lab/tests/test_history_baseline_retrieval.py
        # opens a CSV with encoding='utf-8-sig' and newline=''.
        with io.StringIO(raw.decode('utf-8-sig'), newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(SHOTS), len(rows))
        self.assertEqual(SHOTS[1]['purpose'], rows[1]['purpose'],
                         'the writer rewrote, escaped or truncated what the person typed')
        self.assertEqual(SHOTS[0]['purpose'], rows[0]['purpose'])
        self.assertEqual('', rows[1]['camera'], 'a cell the row does not state must stay empty, '
                        'not become this service\'s own marker')
        self.assertEqual('2.5', rows[2]['duration_s'])
        self.assertEqual('4', rows[0]['duration_s'])
        self.assertEqual('', rows[1]['duration_s'])
        self.assertEqual('1', rows[0]['index'])
        # Provenance rides on every row, so a printed page still answers the two questions.
        self.assertEqual(str(plan['revision']), rows[0]['plan_revision'])
        self.assertEqual(plan_export.EXPORT_VERSION, rows[0]['export_contract'])
        self.assertIn('没有把它发给任何人或系统', rows[0]['execution_status'])
        self.assertIn('\r\n', body, 'RFC4180 line endings are what a spreadsheet expects')

    def test_a_plan_without_shot_rows_refuses_the_csv_and_names_the_next_step(self):
        poster = self._create(output_type='IMAGE', shots=[])
        status, answer = self._export(poster['plan_id'], 'storyboard_csv')
        self.assertEqual(409, status, answer)
        self.assertEqual('PLAN_EXPORT_NO_SHOTS', answer['error'])
        detail = answer['detail']
        self.assertNotIn('empty', detail.lower(), 'the refusal must not be a status word')
        for hint in ('镜头行', 'shots', 'markdown'):
            self.assertIn(hint, detail, f'the refusal does not say what to do next: {hint}')
        # The prose materials still answer for the same plan: the refusal is about the table, not
        # about the plan being unexportable.
        self.assertEqual(200, self._export(poster['plan_id'], 'markdown')[0])

    def test_shot_rows_on_a_type_that_has_no_storyboard_are_refused_by_name(self):
        for output_type in ('IMAGE', 'UI', 'AUDIO', 'CAMPAIGN'):
            status, body = self._call(
                'POST', f'/api/projects/{self.project}/assistance-plans',
                plan_body(output_type=output_type))
            self.assertEqual(409, status, body)
            self.assertEqual('ASSISTANCE_PLAN_SHOTS_NOT_APPLICABLE', body['error'], output_type)
        # The two types that do carry them still write.
        for output_type in ('STORYBOARD', 'MOTION'):
            self._create(output_type=output_type)

    def test_a_malformed_shot_list_is_refused_rather_than_dropped(self):
        cases = {
            'ASSISTANCE_PLAN_SHOTS_MALFORMED': {'shots': 'not a list'},
            'ASSISTANCE_PLAN_SHOT_UNKNOWN_FIELD': {'shots': [{'index': 1, 'purpose': 'x',
                                                              'lens': '推'}]},
            'ASSISTANCE_PLAN_SHOT_INDEX_INVALID': {'shots': [{'index': 0, 'purpose': 'x'}]},
            'ASSISTANCE_PLAN_SHOT_INDEX_DUPLICATE': {
                'shots': [{'index': 2, 'purpose': 'a'}, {'index': 2, 'purpose': 'b'}]},
            'ASSISTANCE_PLAN_SHOT_PURPOSE_MISSING': {'shots': [{'index': 1, 'purpose': '  '}]},
            'ASSISTANCE_PLAN_SHOT_DURATION_INVALID': {
                'shots': [{'index': 1, 'purpose': 'a', 'duration_s': -3}]},
        }
        for code, override in cases.items():
            status, body = self._call('POST', f'/api/projects/{self.project}/assistance-plans',
                                      plan_body(**override))
            self.assertEqual(400, status, (code, body))
            self.assertEqual(code, body['error'], f'{code} answered {body}')
        oversized = [{'index': position, 'purpose': f'镜头 {position}'}
                     for position in range(1, assistance_plan.MAX_SHOTS + 2)]
        status, body = self._call('POST', f'/api/projects/{self.project}/assistance-plans',
                                  plan_body(shots=oversized))
        self.assertEqual(400, status)
        self.assertEqual('ASSISTANCE_PLAN_SHOTS_MALFORMED', body['error'])

    def test_shot_rows_are_covered_by_the_content_digest(self):
        """A row is content: the same plan with a different 镜头表 is a different document.

        This is the assertion the digest would silently lose if `shots` were stored but left out of
        CONTENT_FIELDS -- two revisions would claim the same digest while handing out different
        tables.
        """
        first = self._create()
        moved = self._call(
            'POST', f'/api/projects/{self.project}/assistance-plans/{first["plan_id"]}/revisions',
            plan_body(shots=[dict(SHOTS[0], purpose='开场：改了一版')], expected_revision=1))[1]
        self.assertNotEqual(first['content_sha256'], moved['plan']['content_sha256'],
                            'the digest does not cover the shot rows the export renders')
        self.assertEqual(assistance_plan._content_digest(moved['plan']),
                         moved['plan']['content_sha256'],
                         'the stored digest does not cover the bytes it claims to')
        self.assertIn('shots', assistance_plan.CONTENT_FIELDS)

    def test_an_unknown_shot_field_names_the_row_it_refused(self):
        status, body = self._call('POST', f'/api/projects/{self.project}/assistance-plans',
                                  plan_body(shots=[{'index': 1, 'purpose': 'ok'},
                                                   {'index': 2, 'purpose': 'x', 'note': 'y'}]))
        self.assertEqual(400, status, body)
        self.assertEqual('ASSISTANCE_PLAN_SHOT_UNKNOWN_FIELD', body['error'])
        self.assertIn('shots[1]', body['detail'])

    # -- the export is a snapshot ---------------------------------------------------

    def test_exporting_the_same_revision_twice_answers_identical_bytes(self):
        plan = self._create()
        for fmt in FORMATS:
            first = json.dumps(self._export(plan['plan_id'], fmt)[1], sort_keys=True)
            second = json.dumps(self._export(plan['plan_id'], fmt)[1], sort_keys=True)
            self.assertEqual(first, second, f'{fmt} is rebuilt live, not snapshotted')
        # A new revision is a different export, and it says which revision it took.
        moved = self._call(
            'POST', f'/api/projects/{self.project}/assistance-plans/{plan["plan_id"]}/revisions',
            plan_body(objective='为秋季新品做一段十五秒主视觉动效（第二版）',
                      expected_revision=1))[1]['plan']
        _, answer = self._export(plan['plan_id'], 'markdown')
        self.assertEqual(2, answer['revision'])
        self.assertIn('（第二版）', answer['body'])
        self.assertIn(moved['content_sha256'], answer['body'])

    def test_the_format_query_is_named_not_guessed(self):
        plan = self._create()
        status, body = self._export(plan['plan_id'], '')
        self.assertEqual(400, status, body)
        self.assertEqual('PLAN_EXPORT_FORMAT_REQUIRED', body['error'])
        status, answer = self._call('GET', f'/api/projects/{self.project}/assistance-plans'
                                          f'/{plan["plan_id"]}/export')
        self.assertEqual(400, status, answer)
        self.assertEqual('PLAN_EXPORT_FORMAT_REQUIRED', answer['error'])
        for wrong in ('pdf', 'MARKDOWN', 'docx'):
            status, body = self._export(plan['plan_id'], wrong)
            self.assertEqual(400, status, body)
            self.assertEqual('PLAN_EXPORT_FORMAT_INVALID', body['error'])
            for fmt in FORMATS:
                self.assertIn(fmt, body['detail'], 'the refusal must name what can be asked for')

    def test_an_unknown_plan_keeps_the_plan_vocabulary(self):
        """The export borrows the plan store's refusals instead of minting a second vocabulary.

        A foreign project id answers the same 404 as a missing plan, because the plan lookup is
        what scopes the read -- which is the honest answer to a page that asked for one plan of
        another project: the plan it named is not in the project it named.
        """
        status, body = self._export('aplan-' + '0' * 32, 'markdown')
        self.assertEqual(404, status, body)
        self.assertEqual('ASSISTANCE_PLAN_NOT_FOUND', body['error'])
        plan = self._create()
        status, body = self._call('GET', f'/api/projects/{"0" * 32}/assistance-plans'
                                         f'/{plan["plan_id"]}/export?format=txt')
        self.assertEqual(404, status, body)
        self.assertEqual('ASSISTANCE_PLAN_NOT_FOUND', body['error'])

    def test_a_plan_stored_before_shot_rows_existed_still_exports_and_still_validates(self):
        """`shots` is an added optional field, so a pre-DL-KB-11 document is not a defect.

        The row is rewritten to the exact bytes the writer produced before this field existed (no
        ``shots`` key at all, its digest over the fields it had), because the compatibility claim is
        about stored history, not about a fresh document that happens to carry an empty list.
        """
        plan = self._create()
        document = dict(self._detail(plan['plan_id'])['current'])
        document.pop('shots')
        legacy_fields = tuple(key for key in assistance_plan.CONTENT_FIELDS if key != 'shots')
        document['content_sha256'] = assistance_plan._digest(
            {key: document.get(key) for key in legacy_fields})
        self._append_revision(plan['plan_id'], document)

        readback = self._detail(plan['plan_id'])
        self.assertEqual(200, self._call(
            'GET', f'/api/projects/{self.project}/assistance-plans/{plan["plan_id"]}')[0])
        self.assertNotIn('shots', readback['current'],
                         'the readback rebuilt the document instead of serving the stored bytes')
        self.assertEqual([], schema_errors(load_schema(assistance_plan.PLAN_SCHEMA_PATH),
                                           readback['current']),
                         'a pre-shot-row plan no longer satisfies the plan contract -- an optional '
                         'field was made mandatory somewhere')

        for fmt in ('markdown', 'txt'):
            body, answer = self._export_body(plan['plan_id'], fmt)
            self.assertEqual(0, answer['shot_count'], fmt)
            self.assertIn('这份方案没有登记镜头行', body, fmt)
        # The JSON material is the stored document, so it answers with the absence itself rather
        # than with a sentence about it: `shots` is not in the bytes at all, and the header says 0.
        body, answer = self._export_body(plan['plan_id'], 'json')
        self.assertEqual(0, answer['shot_count'])
        self.assertEqual(0, json.loads(body)['export']['shot_count'])
        self.assertNotIn('shots', json.loads(body)['plan'])
        status, answer = self._export(plan['plan_id'], 'storyboard_csv')
        self.assertEqual(409, status, answer)
        self.assertEqual('PLAN_EXPORT_NO_SHOTS', answer['error'])

    def test_an_unreadable_current_revision_is_refused_not_rendered_from_a_guess(self):
        plan = self._create()
        broken = {'schemaVersion': assistance_plan.PLAN_VERSION, 'plan_id': plan['plan_id'],
                  'revision': 2, 'project_id': self.project, 'objective': plan['objective'],
                  'output_type': plan['output_type'],
                  'content_sha256': 'sha256:' + '1' * 64,
                  'created_at': '2026-10-24T00:00:00Z', 'created_by': 'owner'}
        with closing(assistance_plan.connect(
                self.service.database, project_root=self.service.paths.project_root)) as conn:
            top = conn.execute('SELECT MAX(revision) AS top FROM assistance_plan_revision'
                               ' WHERE plan_id=?', (plan['plan_id'],)).fetchone()['top']
            conn.execute('INSERT INTO assistance_plan_revision (plan_id, revision, objective,'
                         ' output_type, content_sha256, created_at, created_by, document_json)'
                         ' VALUES (?,?,?,?,?,?,?,?)',
                         (plan['plan_id'], top + 1, broken['objective'], broken['output_type'],
                          broken['content_sha256'], broken['created_at'], broken['created_by'],
                          '{not json'))
            conn.commit()
        status, answer = self._export(plan['plan_id'], 'markdown')
        self.assertEqual(409, status, answer)
        self.assertEqual('PLAN_EXPORT_REVISION_UNREADABLE', answer['error'])
        self.assertIn('无法解析', answer['detail'])

    def test_a_draft_with_no_creative_says_so_in_every_material(self):
        draft = self._create(neutral_creative=None)
        for fmt in ('markdown', 'txt'):
            body, _ = self._export_body(draft['plan_id'], fmt)
            self.assertIn('尚未提供创意', body, fmt)
            self.assertIn('这条方案已经保存，但还没有写到创意。', body, fmt)


if __name__ == '__main__':
    unittest.main()
