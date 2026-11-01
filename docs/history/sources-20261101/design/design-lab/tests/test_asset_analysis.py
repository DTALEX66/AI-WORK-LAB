# SPDX-License-Identifier: MIT
"""The asset -> observation -> IR seam, driven through the real asset store.

`Plan.from_ocr` and `plan_to_rir` were already tested in isolation, and both were reported as "no
production caller" — which is the same thing as saying the analysis leg of the loop could not be run at
all outside a test file. These tests pin the caller: bytes that were imported through the product's own
asset route, lowered through the existing bridge, and read back as a schema-valid IR whose raster node
points at the registered img-ID rather than at a filesystem path.

Nothing here claims a model ran. The observations are supplied, because no local OCR backend is
qualified (`readiness/model-radar.json`: QUALIFIED_LOCAL=0, every entry default_enabled:false), and the
empty-input case is asserted to refuse rather than to emit an empty document that would read like an
analysis that found nothing.
"""
import base64
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from design_lab.asset_analysis import AssetAnalysis, AssetAnalysisError   # noqa: E402
from design_lab.image_assets import ImageAssets                            # noqa: E402
from design_lab.service import ProjectService                              # noqa: E402

CANVAS = (400, 300)


def _png():
    from PIL import Image
    stream = io.BytesIO()
    Image.new('RGB', CANVAS, 'white').save(stream, format='PNG')
    return stream.getvalue()


def _detections():
    return [{'text': 'SUNRISE', 'confidence': 0.83,
             'polygon': [[20, 30], [220, 30], [220, 90], [20, 90]]},
            {'text': 'FESTIVAL', 'confidence': 0.61,
             'polygon': [[20, 120], [180, 120], [180, 170], [20, 170]]}]


class AssetAnalysisTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.project-local/task-runtime/asset-analysis'
        parent.mkdir(parents=True, exist_ok=True)
        os.environ.pop('PROJECT_LOCAL_ROOT', None)
        self._temp = tempfile.TemporaryDirectory(dir=parent)
        root = Path(self._temp.name)
        (root / 'AGENTS.md').write_text('# asset analysis fixture', encoding='utf-8')
        self.service = ProjectService(root)
        self.project = self.service.create_project('Analysis round')['id']
        imported = ImageAssets(self.service).import_image(
            self.project, base64.b64encode(_png()).decode('ascii'), 'analysis-1')
        self.asset_id = imported['asset']['id']
        self.analysis = AssetAnalysis(self.service)

    def tearDown(self):
        self._temp.cleanup()

    def test_imported_bytes_lower_to_a_schema_valid_ir(self):
        result = self.analysis.derive(self.project, self.asset_id,
                                      module='ocr-fixture', detections=_detections())
        self.assertEqual(result['status'], 'ASSET_ANALYSIS')
        self.assertEqual(result['object_count'], 3,
                         'two observations plus the unrecovered remainder — the bridge keeps the '
                         f'rest as a group rather than inventing a background: {result["object_count"]}')
        texts = [node for node in result['rir']['layers'] if node.get('type') == 'text']
        self.assertEqual([node['text']['content'] for node in texts], ['SUNRISE', 'FESTIVAL'],
                         f'both observations must reach the IR: {json.dumps(texts)[:300]}')
        rir = result['rir']
        self.assertEqual(rir['schemaVersion'], 'design-lab/reconstruction-ir/v1')
        self.assertEqual(rir['canvas']['width'], CANVAS[0],
                         'the canvas comes from the stored bytes, not from the caller')
        self.assertEqual(rir['canvas']['height'], CANVAS[1])
        # Measured shape of the bridge's output: the observations plus one `unknown` group for the
        # unrecovered remainder, every node inferred, and no raster node unless regions were
        # materialised. Asserting the absence is the point — a fabricated background layer would
        # turn "we did not recover this" into a claim about the artwork.
        self.assertEqual([node['type'] for node in rir['layers']], ['text', 'text', 'group'],
                         f'unexpected layer inventory: {json.dumps(rir["layers"])[:300]}')
        self.assertTrue(all(node['inferred'] for node in rir['layers']),
                        'nothing here is observed structure; the IR must not claim otherwise')
        self.assertEqual(rir['provenance']['evidence'], [self.asset_id],
                         'the IR is bound to the bytes the asset store verified, by img-ID')
        self.assertEqual(rir['provenance']['sourceId'], result['decomposition_id'])
        self.assertTrue(result['rir_sha256'].startswith('sha256:'),
                        'the document must be re-computable by whoever reads it back')

    def test_the_document_is_the_one_the_bridge_validates(self):
        from design_lab.reconstruction.contracts import validate_rir
        result = self.analysis.derive(self.project, self.asset_id,
                                      module='ocr-fixture', detections=_detections())
        validate_rir(result['rir'], project_root=ROOT)   # raises on any contract violation

    def test_no_observation_is_a_refusal_not_an_empty_analysis(self):
        for bad in ([], None, 'SUNRISE'):
            with self.assertRaises(AssetAnalysisError) as caught:
                self.analysis.derive(self.project, self.asset_id,
                                     module='ocr-fixture', detections=bad)
            self.assertEqual(caught.exception.code, 'NO_OBSERVATIONS',
                             f'an empty observation set must refuse, not emit: {bad!r}')

    def test_host_claims_inside_an_observation_are_refused(self):
        """The bridge accepts only {text, confidence, polygon}; invented fields must not pass."""
        polluted = [dict(_detections()[0], host_layer='background')]
        with self.assertRaises(AssetAnalysisError) as caught:
            self.analysis.derive(self.project, self.asset_id,
                                 module='ocr-fixture', detections=polluted)
        self.assertEqual(caught.exception.code, 'INVALID_OBSERVATION')

    def test_an_asset_that_does_not_exist_stays_an_error(self):
        from design_lab.image_assets import ImageAssetError
        with self.assertRaises(ImageAssetError):
            self.analysis.derive(self.project, 'img-' + '0' * 64,
                                 module='ocr-fixture', detections=_detections())

    def test_identity_is_reproducible_and_the_digest_only_with_a_pinned_timestamp(self):
        """The id comes from stored bytes; the document digest needs a pinned clock.

        Asserting byte-stability without a timestamp would be a false claim about the bridge — and
        worse, a timing-dependent one: it stamps each node with the moment of lowering at one-second
        granularity, so two quick calls agree by accident and two slow ones do not.
        """
        free = self.analysis.derive(self.project, self.asset_id,
                                    module='ocr-fixture', detections=_detections())
        pinned_a = self.analysis.derive(self.project, self.asset_id, module='ocr-fixture',
                                        detections=_detections(), timestamp='2026-10-20T00:00:00Z')
        pinned_b = self.analysis.derive(self.project, self.asset_id, module='ocr-fixture',
                                        detections=_detections(), timestamp='2026-10-20T00:00:00Z')
        self.assertEqual(free['decomposition_id'], pinned_a['decomposition_id'],
                         'the identity is derived from the bytes and the observation, not the clock')
        self.assertEqual(pinned_a['rir_sha256'], pinned_b['rir_sha256'],
                         'a pinned timestamp must make the artefact re-computable')
        self.assertNotEqual(pinned_a['rir_sha256'], free['rir_sha256'],
                            'the unpinned document carries this call clock; it is not a stable digest')


class AssetAnalysisHttpTests(unittest.TestCase):
    """The same seam over the real loopback service, because a page can only call a route.

    `verify_workbench_route_calls.py` demands that a dispatched route is either called by the
    Workbench or explained as backend-only; this class is part of that explanation being true rather
    than merely asserted.
    """

    def setUp(self):
        parent = ROOT / '.project-local/task-runtime/asset-analysis-http'
        parent.mkdir(parents=True, exist_ok=True)
        os.environ.pop('PROJECT_LOCAL_ROOT', None)
        self._temp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self._temp.name)
        (self.root / 'AGENTS.md').write_text('# asset analysis http fixture', encoding='utf-8')
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
        self.project = self.service.create_project('Analysis http')['id']
        stream = io.BytesIO()
        from PIL import Image
        Image.new('RGB', CANVAS, 'white').save(stream, format='PNG')
        self.asset = ImageAssets(self.service).import_image(
            self.project, base64.b64encode(stream.getvalue()).decode('ascii'), 'http-1')['asset']

    def request(self, method, path, body=None):
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
            resp = conn.getresponse()
            return resp.status, json.loads(resp.read())
        finally:
            conn.close()

    def test_the_route_answers_with_the_bridge_document(self):
        status, payload = self.request(
            'POST', f'/api/projects/{self.project}/assets/{self.asset["id"]}/analysis',
            {'module': 'ocr-fixture', 'detections': _detections(), 'decomposition_id': None})
        self.assertEqual(status, 201, f'the analysis route must answer 201: {payload}')
        self.assertEqual(payload['rir']['schemaVersion'], 'design-lab/reconstruction-ir/v1')
        self.assertEqual(payload['rir']['provenance']['evidence'], [self.asset['id']])
        self.assertEqual(payload['asset']['sha256'], self.asset['sha256'],
                         'the response must bind to the bytes the store verified')

    def test_an_empty_observation_set_is_a_400_not_an_empty_document(self):
        status, payload = self.request(
            'POST', f'/api/projects/{self.project}/assets/{self.asset["id"]}/analysis',
            {'module': 'ocr-fixture', 'detections': [], 'decomposition_id': None})
        self.assertEqual(status, 400, f'an empty observation set must be refused: {payload}')
        self.assertEqual(payload['error'], 'NO_OBSERVATIONS')

    def test_a_foreign_asset_is_not_analysed(self):
        status, payload = self.request(
            'POST', f'/api/projects/{self.project}/assets/img-{"0" * 64}/analysis',
            {'module': 'ocr-fixture', 'detections': _detections(), 'decomposition_id': None})
        self.assertEqual(status, 404, f'unknown asset must not be analysed: {payload}')


if __name__ == '__main__':
    unittest.main()
