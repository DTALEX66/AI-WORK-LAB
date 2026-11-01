# SPDX-License-Identifier: MIT
"""Prompt Intelligence over live HTTP -- the capability domain's missing entry point, made callable.

`docs/taskpacks/DESIGN-LAB-DIRECTION-ALIGNMENT-2026-10-19.md` §3.3 names prompt generation and reversal
as a product capability, and `docs/current/PRODUCT_DEFINITION.md` repeats it, while the word `prompt`
appeared zero times in `src/design_lab/http_service.py`, `src/design_lab/cli.py` and
`apps/workbench/shell.ts`. The segment therefore had no entry at all: no route, no command, no panel,
and the standalone chain could not reach it. These cases drive it over HTTP, because a page can only
ever call a route, and they assert the part that is load-bearing -- that a prompt document carries the
provenance of the stored records it was assembled from, and says out loud what it does not know.
"""
from __future__ import annotations

import base64
import hashlib
import http.client
import io
import json
import os
import secrets
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Spelled as literal inserts, not a loop over candidates: design-lab/scripts/verify_test_selfsufficiency.py
# reads the root's name inside the sys.path statement itself, and a module that imports `design_lab`
# must claim that root on its own rather than borrow a sibling's.
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'design-lab' / 'tests'))

from design_lab.prompt_intelligence import (  # noqa: E402
    COMPOSITION_SCHEMA_PATH, PromptIntelligence, PromptIntelligenceError, check_document)
from design_lab.service import ProjectService  # noqa: E402

CANVAS = (8, 6)
DETECTIONS = [
    {'text': 'PROMPT', 'confidence': 0.91, 'polygon': [[1, 1], [4, 1], [4, 3], [1, 3]]},
    {'text': 'HOP', 'confidence': 0.57, 'polygon': [[1, 4], [4, 4], [4, 6], [1, 6]]},
]


def _png_bytes() -> bytes:
    stream = io.BytesIO()
    from PIL import Image
    Image.new('RGB', CANVAS, 'white').save(stream, format='PNG')
    return stream.getvalue()


class PromptIntelligenceTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.project-local/task-runtime/prompt-intelligence-http'
        parent.mkdir(parents=True, exist_ok=True)
        os.environ.pop('PROJECT_LOCAL_ROOT', None)
        self._temp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self._temp.name)
        (self.root / 'AGENTS.md').write_text('# prompt intelligence fixture', encoding='utf-8')
        from design_lab.http_service import make_server
        self.service = ProjectService(str(self.root))
        self.token = secrets.token_hex(32)
        self.server = make_server(self.service, self.token, port=0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        def _stop(self=self):
            self.server.shutdown()
            self.thread.join()
            self.server.server_close()
        self.addCleanup(_stop)
        self.addCleanup(self._temp.cleanup)

    # -- transport --------------------------------------------------------------

    def call(self, method, path, body=None):
        headers = {'Authorization': 'Bearer ' + self.token,
                   'Host': f'127.0.0.1:{self.port}',
                   'Origin': f'http://127.0.0.1:{self.port}',
                   'Sec-Fetch-Site': 'same-origin'}
        raw = None
        if body is not None:
            headers['Content-Type'] = 'application/json'
            raw = json.dumps(body).encode('utf-8')
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        try:
            conn.request(method, path, body=raw, headers=headers)
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def expect(self, method, path, body, status):
        got, payload = self.call(method, path, body)
        self.assertEqual(got, status, f'{method} {path} -> {got}: '
                                      f'{json.dumps(payload, ensure_ascii=False)[:400]}')
        return payload

    # -- fixtures ---------------------------------------------------------------

    def project(self, name='Prompt project'):
        return self.expect('POST', '/api/projects', {'name': name}, 201)['project']['id']

    def asset(self, project):
        return self.expect(
            'POST', f'/api/projects/{project}/assets',
            {'content_base64': base64.b64encode(_png_bytes()).decode('ascii'),
             'idempotency_key': 'prompt-asset'}, 201)['asset']

    def brief(self, project, title='Prompt brief', goals=('standalone',), key='prompt-brief'):
        return self.expect(
            'POST', f'/api/projects/{project}/briefs',
            {'title': title, 'goals': list(goals), 'constraints': 'no external upload',
             'reference_asset_ids': [], 'idempotency_key': key}, 201)['brief']['brief_id']

    def direction(self, project, brief_id, key='prompt-direction', style=('measured',)):
        return self.expect(
            'POST', f'/api/projects/{project}/directions',
            {'brief_id': brief_id, 'title': 'Prompt direction', 'style_notes': list(style),
             'color_mood': 'warm', 'typography_mood': 'sans',
             'idempotency_key': key}, 201)['direction']['direction_id']

    def choose(self, project, direction_id):
        return self.expect('POST', f'/api/projects/{project}/directions/{direction_id}/choose',
                           {'actor': 'owner', 'actor_kind': 'human',
                            'idempotency_key': 'prompt-choose'}, 200)

    def compose(self, project, brief_id, direction_id=None, target='image-generation'):
        return self.expect('POST', f'/api/projects/{project}/prompts',
                           {'brief_id': brief_id, 'direction_id': direction_id, 'target': target},
                           201)

    # -- composition ------------------------------------------------------------

    def test_a_composed_prompt_carries_the_provenance_of_every_stored_field(self):
        project = self.project()
        brief_id = self.brief(project)
        direction_id = self.direction(project, brief_id)
        self.choose(project, direction_id)

        envelope = self.compose(project, brief_id)
        document = envelope['document']
        self.assertEqual(document['schemaVersion'], 'design-lab/prompt-composition/v1')
        self.assertEqual(document['target'], 'image-generation')
        # The route wraps the contract document; a digest over the envelope would move when the
        # transport does, so the bound bytes are the document's own.
        recomputed = hashlib.sha256(json.dumps(
            document, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
        self.assertEqual(envelope['document_sha256'], 'sha256:' + recomputed,
                         'the readback digest does not bind the document it returned')

        kinds = [section['kind'] for section in document['sections']]
        for expected in ('target', 'subject', 'goal', 'constraint', 'stance', 'style', 'colour',
                         'typography'):
            self.assertIn(expected, kinds, f'the chosen direction and brief never reached the prompt')
        stored = [section for section in document['sections']
                  if section['source'].get('kind') == 'stored']
        self.assertTrue(stored, 'every section claims to be framing, so nothing was read from storage')
        for section in stored:
            self.assertRegex(section['source']['spec_sha256'], r'^sha256:[0-9a-f]{64}$')
            self.assertIn(section['text'], document['prompt_text'],
                          f'{section["kind"]} is recorded but never appears in the prompt text')
        # Nothing may enter the prompt without either a stored digest or a naming rule.
        for section in document['sections']:
            self.assertIn(section['source'].get('kind'), ('stored', 'framing'))

    def test_composition_is_reproducible_over_the_same_records(self):
        project = self.project()
        brief_id = self.brief(project)
        direction_id = self.direction(project, brief_id)
        self.choose(project, direction_id)
        first = self.compose(project, brief_id)['document']
        second = self.compose(project, brief_id)['document']
        self.assertEqual(first['composition_id'], second['composition_id'],
                         'two compositions over identical records disagree, so a readback cannot '
                         'be re-computed and compared')

    def test_an_absent_choice_is_reported_instead_of_assumed(self):
        project = self.project()
        brief_id = self.brief(project)
        self.direction(project, brief_id)          # exists, but nobody chose it
        document = self.compose(project, brief_id)['document']
        kinds = {section['kind'] for section in document['sections']}
        self.assertNotIn('style', kinds, 'an unchosen direction leaked its stance into the prompt')
        self.assertIn('direction', [entry['field'] for entry in document['unknown']],
                      'a prompt over a brief with no chosen direction must say the direction is missing')

    def test_the_prompt_says_what_it_does_not_know(self):
        project = self.project()
        brief_id = self.brief(project)
        document = self.compose(project, brief_id)['document']
        fields = {entry['field'] for entry in document['unknown']}
        # Audience, brand assets and copy are not modelled by the design layer. A prompt that left
        # them out silently would read as though they had been considered and found absent.
        self.assertTrue({'audience', 'brand_assets', 'copy_text'} <= fields, f'unknown: {fields}')
        self.assertEqual({'selected': None, 'selection_state': 'NEVER_ASKED', 'executed': False},
                         document['model'],
                         'composition ran no model and must not be able to claim otherwise; a project '
                         'nobody has asked yet is NEVER_ASKED, not a declination')
        self.assertTrue(len(document['claims_not_made']) >= 4)

    def test_a_superseded_brief_version_is_refused(self):
        project = self.project()
        brief_id = self.brief(project)
        self.expect('POST', f'/api/projects/{project}/briefs/{brief_id}/revisions',
                    {'title': 'Prompt brief v2', 'goals': ['revised'], 'constraints': None,
                     'reference_asset_ids': [], 'idempotency_key': 'prompt-revise'}, 201)
        error = self.expect('POST', f'/api/projects/{project}/prompts',
                            {'brief_id': brief_id, 'direction_id': None,
                             'target': 'image-generation'}, 409)
        self.assertEqual(error['error'], 'STALE_REVISION',
                         'composing from a superseded brief would present retired intent as current')

    def test_a_direction_from_another_brief_is_refused(self):
        project = self.project()
        first = self.brief(project, key='brief-a')
        second = self.brief(project, title='Other brief', key='brief-b')
        direction_id = self.direction(project, first)
        error = self.expect('POST', f'/api/projects/{project}/prompts',
                            {'brief_id': second, 'direction_id': direction_id,
                             'target': 'image-generation'}, 409)
        self.assertEqual(error['error'], 'DIRECTION_NOT_UNDER_BRIEF')

    def test_a_target_outside_the_radar_families_is_refused_by_name(self):
        project = self.project()
        brief_id = self.brief(project)
        error = self.expect('POST', f'/api/projects/{project}/prompts',
                            {'brief_id': brief_id, 'direction_id': None, 'target': 'audio'}, 400)
        self.assertEqual(error['error'], 'UNKNOWN_TARGET')
        self.assertIn('image-generation', error['detail'],
                      'the refusal must name what is acceptable, or the caller cannot recover')

    def test_a_missing_brief_keeps_its_own_code(self):
        project = self.project()
        error = self.expect('POST', f'/api/projects/{project}/prompts',
                            {'brief_id': 'brief-' + '0' * 32, 'direction_id': None,
                             'target': 'image-generation'}, 404)
        self.assertEqual(error['error'], 'BRIEF_NOT_FOUND')

    # -- reversal ---------------------------------------------------------------

    def test_a_reversal_restates_observations_and_names_what_it_never_saw(self):
        project = self.project()
        asset = self.asset(project)
        document = self.expect(
            'POST', f'/api/projects/{project}/assets/{asset["id"]}/prompt-reversal',
            {'module': 'ocr-fixture', 'detections': DETECTIONS, 'decomposition_id': None},
            201)['document']
        self.assertEqual(document['schemaVersion'], 'design-lab/prompt-reversal/v1')
        self.assertEqual(document['asset']['sha256'], asset['sha256'],
                         'the reversal is not bound to the bytes the import route verified')
        self.assertEqual(len(document['layers']), document['observation']['object_count'])
        for detection in DETECTIONS:
            self.assertIn(detection['text'], document['prompt_text'],
                          'an observed string was lowered into the IR but left out of the prompt')
        fields = {entry['field'] for entry in document['unknown']}
        self.assertTrue({'semantic content', 'colour', 'font'} <= fields, f'unknown: {fields}')
        self.assertEqual(document['model']['executed'], False)
        self.assertNotIn('raster', json.dumps(document).lower(),
                         'a reversal may not stage or claim an image region it did not materialise')

    def test_a_reversal_refuses_an_empty_observation_set(self):
        project = self.project()
        asset = self.asset(project)
        error = self.expect(
            'POST', f'/api/projects/{project}/assets/{asset["id"]}/prompt-reversal',
            {'module': 'ocr-fixture', 'detections': [], 'decomposition_id': None}, 400)
        self.assertEqual(error['error'], 'NO_OBSERVATIONS',
                         'an empty observation list must not lower into a prompt that looks described')

    def test_a_reversal_refuses_an_asset_that_is_not_in_the_project(self):
        project = self.project()
        other = self.project('Other project')
        asset = self.asset(other)
        status, payload = self.call(
            'POST', f'/api/projects/{project}/assets/{asset["id"]}/prompt-reversal',
            {'module': 'ocr-fixture', 'detections': DETECTIONS, 'decomposition_id': None})
        # 404 ASSET_NOT_FOUND, the same answer as for an id that was never imported: a reversal
        # must not distinguish "not yours" from "does not exist", or it becomes an existence oracle.
        self.assertEqual((status, payload.get('error')), (404, 'ASSET_NOT_FOUND'),
                         f'cross-project reversal answered {status}: {payload}')

    # -- the guard's teeth ------------------------------------------------------

    def test_the_contract_refuses_a_document_that_lost_its_unknown_list(self):
        """check_document has to fail on a doctored document, or the schema is decoration."""
        document = {
            'schemaVersion': 'design-lab/prompt-composition/v1',
            'composition_id': 'prompt-' + '0' * 32,
            'project_id': '0' * 32,
            'target': 'image-generation',
            'prompt_text': 'target: image-generation\nsubject: x',
            'sections': [
                {'kind': 'target', 'text': 'target: image-generation',
                 'source': {'kind': 'framing', 'rule': 'labelled by this module'}},
                {'kind': 'subject', 'text': 'x',
                 'source': {'kind': 'stored', 'brief_id': 'brief-' + '0' * 32, 'version': 1,
                            'spec_sha256': 'sha256:' + '0' * 64}}],
            'observed': [], 'framing': [],
            'unknown': [{'field': 'audience', 'reason': 'not modelled'}],
            'model': {'selected': None, 'selection_state': 'NEVER_ASKED', 'executed': False},
            'claims_not_made': ['a', 'b', 'c', 'd'],
        }
        self.assertEqual(check_document(document, COMPOSITION_SCHEMA_PATH,
                                                  'composition'), document)
        for field, mutate in (
                ('unknown', lambda doc: doc.__delitem__('unknown')),
                ('executed', lambda doc: doc['model'].__setitem__('executed', True)),
                ('section source', lambda doc: doc['sections'][1]['source'].__setitem__('kind', 'guessed')),
                ('minItems', lambda doc: doc.__setitem__('sections', doc['sections'][:1]))):
            doctored = json.loads(json.dumps(document))
            mutate(doctored)
            with self.assertRaises(PromptIntelligenceError) as caught:
                check_document(doctored, COMPOSITION_SCHEMA_PATH, 'composition')
            self.assertEqual(caught.exception.code, 'COMPOSITION_CONTRACT_VIOLATION',
                             f'a document with a broken {field} passed the contract check')
            self.assertEqual(caught.exception.status, 500)


if __name__ == '__main__':
    unittest.main()
