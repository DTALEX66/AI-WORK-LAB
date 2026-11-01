# SPDX-License-Identifier: MIT
"""DL-KB-02 A5, asserted instead of assumed: 模型服务关闭时仍可写入、检索、编辑与复制.

The clause stayed PARTIAL because nothing drove the knowledge paths while the model catalogue
refused. Independence was *implicit* -- the stores are separate -- and an implicit argument is not
a receipt. This module patches the catalogue so it raises, then proves two things at once: every
knowledge operation still answers 2xx over HTTP, and the knowledge paths never once asked the
catalogue for anything. The second half is what makes the first non-accidental -- a route that
merely happens to work today while still reading the catalogue would pass the status assertions
and fail this one.
"""
from __future__ import annotations

import http.client
import json
import os
import secrets
import sys
import tempfile
import threading
import unittest
import urllib.parse
from contextlib import closing
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))

from design_lab import model_selection                        # noqa: E402
from design_lab.http_service import make_server               # noqa: E402
from design_lab.service import ProjectService                 # noqa: E402

SOURCE = {'sourceId': 'owner-note', 'origin': 'UNKNOWN', 'author': 'owner',
          'license': 'UNKNOWN', 'licenseStatus': 'unknown', 'allowedUsage': 'UNKNOWN',
          'citationScope': 'UNKNOWN', 'version': '1', 'observedAt': '2026-10-24T00:00:00Z',
          'contentHash': 'UNKNOWN', 'verification': 'UNVERIFIED'}


def entry(**overrides):
    """A complete create request; each case overrides only what it is about."""
    body = {
        'entry_type': 'METHOD', 'title': '分镜拆解三步法',
        'summary': '把一段脚本拆成镜头表：先定节拍，再定景别，最后定转场。',
        'domain_tags': ['film'], 'task_tags': ['storyboard'], 'target_tools': ['storyboarder'],
        'body': '第一步按段落切节拍。第二步给每个节拍选景别。第三步只标必要的转场。',
        'applicability': '适合 30-90 秒短片的分镜前置。',
        'limits': '不适用于需要精确口型对位的动画。',
        'source': dict(SOURCE), 'related_capability_ids': [], 'recommended': True,
        'created_by': 'owner', 'supersedes': None,
    }
    body.update(overrides)
    return body


class KnowledgeSurvivesModelOutageTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop('PROJECT_LOCAL_ROOT', None)
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        self.project = self.base / 'project'
        self.project.mkdir()
        (self.project / 'AGENTS.md').write_text('# knowledge outage fixture', encoding='utf-8')
        self.service = ProjectService(self.project)
        self.project_id = self.service.create_project('Outage Probe')['id']
        self.token = secrets.token_hex(32)
        self.httpd = make_server(self.service, self.token, 0)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        # The model service is "off" in the only way this repository can say it: the catalogue
        # raises. The counter counts catalogue reads, which is the claim actually being tested.
        self.catalogue_reads = 0
        self._real_catalog = model_selection.catalog

        def refusing_catalog():
            self.catalogue_reads += 1
            raise RuntimeError('model service stopped (fixture)')

        model_selection.catalog = refusing_catalog

    def tearDown(self):
        model_selection.catalog = self._real_catalog
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

    def _four_operations(self):
        """写入 / 检索 / 编辑 / 复制, in that order, returning each answer."""
        status, created = self._call('POST', '/api/knowledge-entries', entry())
        self.assertEqual(201, status, created)
        entry_id = created['entry']['knowledge_entry_id']

        query = urllib.parse.quote('分镜')
        status, found = self._call('GET', f'/api/knowledge-entries/search?q={query}')
        self.assertEqual(200, status, found)

        # The revise route's key set is the create set minus `supersedes` plus
        # `expected_revision`, and it keeps `recommended` -- a correction may move which revision is
        # recommended. Dropping either half of that answers 400, not a shorter body.
        revision = {key: value for key, value in entry().items() if key != 'supersedes'}
        revision['title'] = '分镜拆解三步法（离线修订）'
        status, edited = self._call(
            'POST', f'/api/knowledge-entries/{entry_id}/revisions',
            dict(revision, expected_revision=1))
        self.assertEqual(201, status, edited)

        status, detail = self._call('GET', f'/api/knowledge-entries/{entry_id}')
        self.assertEqual(200, status, detail)
        return created, found, edited, detail

    def test_the_model_surface_really_is_refused_during_the_outage(self):
        """The control: if a choice still landed, the outage would be theatre.

        This is the selection surface, not ``GET /api/models`` -- that route builds its own
        catalogue document and never passes through the patched function, so asserting on it would
        have tested the patch's name rather than the outage.
        """
        status, refused = self._call(
            'POST', f'/api/projects/{self.project_id}/model-selection/choose',
            {'model_id': 'minimax-h3-video-vae', 'declared_unused': False,
             'actor': 'owner', 'actor_kind': 'human'})
        self.assertNotIn(status, (200, 201), refused)
        self.assertEqual('MODEL_CATALOG_UNAVAILABLE', refused.get('error'), refused)
        self.assertGreaterEqual(self.catalogue_reads, 1,
                                'the patch never reached the route -- nothing was simulated')

    def test_write_search_edit_and_copy_answer_while_the_model_service_is_down(self):
        created, found, edited, detail = self._four_operations()

        self.assertEqual('分镜拆解三步法', created['entry']['title'])
        self.assertTrue(found['entries'],
                        'the written entry is not findable while the model is off')
        self.assertEqual('分镜拆解三步法', found['entries'][0]['title'])
        self.assertEqual(2, edited['entry']['revision'], 'the edit did not append a revision')

        # 复制 is the text a person lifts off the screen: the detail answer must still carry the
        # body verbatim, with the edited title, or the copy affordance has nothing honest to copy.
        current = detail['current']
        self.assertEqual('分镜拆解三步法（离线修订）', current['title'])
        self.assertEqual(entry()['body'], current['body'])
        self.assertTrue(current['body'].strip())

    def test_the_knowledge_paths_never_consult_the_catalogue_at_all(self):
        before = self.catalogue_reads
        self._four_operations()
        self.assertEqual(before, self.catalogue_reads,
                         'a knowledge route read the model catalogue; A5 is then only accidentally '
                         'true and would break the day the catalogue is the thing being fixed')

    def test_a_refused_model_choice_and_a_written_entry_do_not_share_a_fate(self):
        """Both halves in one case: the refusal must not soften into a success, and the entry must
        not be dragged down by it."""
        _, refused = self._call(
            'POST', f'/api/projects/{self.project_id}/model-selection/choose',
            {'model_id': 'minimax-h3-video-vae', 'declared_unused': False,
             'actor': 'owner', 'actor_kind': 'human'})
        self.assertEqual('MODEL_CATALOG_UNAVAILABLE', refused.get('error'), refused)
        before = self.catalogue_reads
        status, created = self._call('POST', '/api/knowledge-entries',
                                     entry(title='离线仍可写入的另一条'))
        self.assertEqual(201, status, created)
        self.assertEqual(before, self.catalogue_reads,
                         'the write path reached for the model catalogue')


if __name__ == '__main__':
    unittest.main()
