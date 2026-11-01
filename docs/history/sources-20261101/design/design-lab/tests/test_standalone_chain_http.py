# SPDX-License-Identifier: MIT
"""Walk the standalone chain over live HTTP and record where it actually reaches.

Every other test in this area proves one seam. That is how "the chain works" came to be a claim
assembled from hop-by-hop greenness while nothing had ever driven the hops in order against one
service and one project. This class does exactly that: one server, one project, each hop fed by
the real identifier the previous hop returned, over HTTP rather than in-process, because a page
can only ever call a route.

It is deliberately not a happy path. The last case asserts what the chain still CANNOT do, so the
file records the break as measured fact instead of leaving it in prose.
"""
from __future__ import annotations

import base64
import http.client
import io
import json
import os
import re
import secrets
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# The clean-install CI job sets DL_LAUNCH_INSTALLED=1 so the chain is walked against the INSTALLED
# package -- the same convention design-lab/tests/test_workbench_launch.py already uses. Without it
# this module puts the checkout on the path, which is correct for a source run and wrong for a
# packaged one: `PROJECT_ROOT` is `parents[3]` of the module, the repository here but the
# interpreter's own `Lib` in a wheel, so every contract a route opens through it is unopenable
# there. Only the installed run can see that class of defect.
INSTALLED_MODE = os.environ.get('DL_LAUNCH_INSTALLED') == '1'
for candidate in (ROOT / 'src', ROOT / 'design-lab' / 'tests'):
    if INSTALLED_MODE and candidate == ROOT / 'src':
        # Only the package resolution changes under the flag. The tests directory still has to be
        # importable: this module borrows fixtures from a sibling test file, and dropping that path
        # would turn an installed run into a ModuleNotFoundError -- a red for the wrong reason.
        continue
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from design_lab.image_assets import ImageAssets  # noqa: E402
from design_lab.service import ProjectService  # noqa: E402

CANVAS = (8, 6)


def _values_under(document, *keys):
    """Every string stored under any of `keys`, anywhere in a JSON document.

    Used where the chain used to assert `id in json.dumps(doc)`. A substring match also passes if
    the id shows up in a message, a cursor or a log line; membership of an identity field is the
    claim the aggregate actually makes -- that it names these entities as entities.
    """
    found = []
    stack = [document]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for key, value in node.items():
                if key in keys:
                    if isinstance(value, str):
                        found.append(value)
                    elif isinstance(value, list):
                        # `reference_asset_ids` is a list of identities, not a single one, so the
                        # strings inside it are just as much "this document names the entity".
                        found.extend(item for item in value if isinstance(item, str))
                if isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(node, list):
            stack.extend(item for item in node if isinstance(item, (dict, list)))
    return found


def _paths_holding(document, value, prefix=''):
    """Where a value actually sits in a JSON document, as `a.b[0].c` paths."""
    hits = []
    if isinstance(document, dict):
        for key, child in document.items():
            hits.extend(_paths_holding(child, value, f'{prefix}.{key}' if prefix else key))
    elif isinstance(document, list):
        for index, child in enumerate(document):
            hits.extend(_paths_holding(child, value, f'{prefix}[{index}]'))
    elif isinstance(document, str) and value in document:
        hits.append(prefix or '$')
    return hits


def _png_bytes() -> bytes:
    stream = io.BytesIO()
    from PIL import Image
    Image.new('RGB', CANVAS, 'white').save(stream, format='PNG')
    return stream.getvalue()


class StandaloneChainTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.project-local/task-runtime/standalone-chain-http'
        parent.mkdir(parents=True, exist_ok=True)
        os.environ.pop('PROJECT_LOCAL_ROOT', None)
        self._temp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self._temp.name)
        (self.root / 'AGENTS.md').write_text('# standalone chain fixture', encoding='utf-8')
        from design_lab.http_service import make_server
        self.service = ProjectService(str(self.root))
        self.token = secrets.token_hex(32)
        self.server = make_server(self.service, self.token, port=0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        if INSTALLED_MODE:
            # Name the layout before spending 20 hops on it. A run that silently imported the
            # checkout would answer every route from the source tree and report the packaged
            # layout as healthy -- the failure mode test_workbench_launch refuses for the same
            # reason, so the guard belongs here too, not in prose.
            import design_lab
            resolved = Path(design_lab.__file__).resolve()
            self.assertIn('site-packages', resolved.parts,
                          f'DL_LAUNCH_INSTALLED=1 but this process imports design_lab from '
                          f'{resolved}: the packaged layout is not being exercised')
            status, health = self.call('GET', '/api/health')
            self.assertEqual(status, 200, health)
            self.assertEqual(health.get('bundleOrigin'), 'packaged',
                             'the served UI came from the checkout, not from the wheel')

        def _stop(self=self):
            self.server.shutdown()
            self.thread.join()
            self.server.server_close()
        self.addCleanup(_stop)
        self.addCleanup(self._temp.cleanup)
        self.hops = []

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

    def hop(self, name, method, path, body, expected):
        status, payload = self.call(method, path, body)
        self.hops.append(f'{name}={status}')
        self.assertEqual(status, expected,
                         f'chain broke at {name} ({method} {path}) -> {status}: '
                         f'{json.dumps(payload, ensure_ascii=False)[:400]}')
        return payload

    def test_the_chain_walks_from_project_to_a_reviewed_candidate(self):
        project = self.hop('project', 'POST', '/api/projects',
                           {'name': 'Chain walk'}, 201)['project']['id']

        imported = self.hop(
            'asset', 'POST', f'/api/projects/{project}/assets',
            {'content_base64': base64.b64encode(_png_bytes()).decode('ascii'),
             'idempotency_key': 'chain-asset'},
            201)['asset']
        asset, asset_version, asset_sha256 = (imported['id'], imported['version_id'],
                                              imported['sha256'])

        brief = self.hop(
            'brief', 'POST', f'/api/projects/{project}/briefs',
            {'title': 'Chain brief', 'goals': ['standalone'], 'constraints': None,
             'reference_asset_ids': [asset], 'idempotency_key': 'chain-brief'},
            201)['brief']['brief_id']

        direction = self.hop(
            'direction', 'POST', f'/api/projects/{project}/directions',
            {'brief_id': brief, 'title': 'Chain direction', 'style_notes': ['measured'],
             'color_mood': 'warm', 'typography_mood': 'sans',
             'idempotency_key': 'chain-direction'},
            201)['direction']['direction_id']

        # The aggregate read is what the workbench actually renders, so the chain is only
        # connected if the earlier writes come back through it.
        layer = self.hop('design-layer', 'GET', f'/api/projects/{project}/design-layer',
                         None, 200)
        self.assertIn(brief, _values_under(layer, 'brief_id'),
                      'the aggregate never names the brief as an entity')
        self.assertIn(direction, _values_under(layer, 'direction_id'),
                      'the aggregate never names the direction as an entity')
        self.assertIn(asset, _values_under(layer, 'reference_asset_ids'),
                      'the aggregate reaches the imported asset only through the brief that '
                      f'references it; it occurs at {_paths_holding(layer, asset)}')

        analysis = self.hop(
            'analysis', 'POST', f'/api/projects/{project}/assets/{asset}/analysis',
            {'module': 'ocr-fixture',
             'detections': [{'text': 'CHAIN', 'confidence': 0.83,
                             'polygon': [[1, 1], [4, 1], [4, 3], [1, 3]]},
                            {'text': 'WALK', 'confidence': 0.61,
                             'polygon': [[1, 4], [4, 4], [4, 6], [1, 6]]}],
             'decomposition_id': None},
            201)
        self.assertEqual(analysis['status'], 'ASSET_ANALYSIS')
        self.assertEqual(analysis['rir']['schemaVersion'], 'design-lab/reconstruction-ir/v1')
        self.assertTrue(analysis['rir']['layers'], 'the derived document carried no layers')
        # `proves` is the document's own statement of its evidence scope; a chain that dropped
        # it would let a derived IR be read as native truth downstream.
        self.assertIn('proves', analysis)

        # Prompt Intelligence, both directions, over the identifiers the earlier hops returned.
        # This is the segment that had no entry point at all before 2026-10-20, so the chain could
        # not reach it: a composition is only proof if it carries the brief and direction the chain
        # just wrote, and a reversal is only proof if it restates the observations this hop supplied.
        # The operator's model choice, walked between the records and the prompt that must carry
        # it: the catalogue is read, one of its own rows is chosen, and the composition has to
        # echo that revision -- otherwise "the user chose" would be a UI claim with no chain behind
        # it, and the prompt could name a model nobody recorded a decision about.
        catalogue = self.hop('catalog', 'GET', '/api/models', None, 200)
        chosen_model = catalogue['models'][0]['model_id']
        self.assertEqual('design-lab/model-catalog/v1', catalogue['schemaVersion'])
        self.assertEqual(0, catalogue['counts']['default_enabled_true'],
                         'the chain now walks a catalogue whose defaults are enabled; that is a '
                         'qualification claim the radar has not made, so re-read this hop on purpose')
        choice = self.hop('model-choose', 'POST',
                          f'/api/projects/{project}/model-selection/choose',
                          {'model_id': chosen_model, 'declared_unused': False,
                           'actor': 'chain-operator', 'actor_kind': 'human'}, 201)
        self.assertEqual('CHOSEN', choice['state'])

        composed = self.hop(
            'prompt-compose', 'POST', f'/api/projects/{project}/prompts',
            {'brief_id': brief, 'direction_id': direction, 'target': 'image-generation'}, 201)
        prompt_document = composed['document']
        self.assertEqual('design-lab/prompt-composition/v1', prompt_document['schemaVersion'])
        self.assertEqual('CHOSEN', prompt_document['model']['selection_state'])
        self.assertEqual(chosen_model, prompt_document['model']['selected']['model_id'],
                         'the composition did not carry the choice the chain just recorded')
        self.assertEqual(choice['selection']['revision'],
                         prompt_document['model']['selected']['revision'])
        self.assertIn('Chain brief', prompt_document['prompt_text'],
                      'the composition did not carry the brief the chain wrote one hop earlier')
        self.assertIn('Chain direction', json.dumps(prompt_document, ensure_ascii=False),
                      'no direction section reached the prompt, so the brief/direction seam is not '
                      'the one the chain established')
        self.assertEqual(False, prompt_document['model']['executed'],
                         'a chain document may not claim a model ran')

        reversal = self.hop(
            'prompt-reverse', 'POST',
            f'/api/projects/{project}/assets/{asset}/prompt-reversal',
            {'module': 'ocr-fixture',
             'detections': [{'text': 'CHAIN', 'confidence': 0.83,
                             'polygon': [[1, 1], [4, 1], [4, 3], [1, 3]]}],
             'decomposition_id': None}, 201)
        self.assertEqual('design-lab/prompt-reversal/v1', reversal['document']['schemaVersion'])
        self.assertEqual(asset_sha256, reversal['document']['asset']['sha256'],
                         'the reversal is not bound to the bytes the asset hop imported')
        self.assertIn('CHAIN', reversal['document']['prompt_text'],
                      'the supplied observation never reached the reversal text')

        # The segment the audit called 缺关键一段: both prompt documents used to exist only in the
        # response body. Reading the store back is now a hop in the chain, and it is asserted against
        # the digests the producing hops published -- so this test no longer proves merely that
        # several routes answered on one server, but that one artifact travelled.
        stored = self.hop('prompt-results', 'GET',
                          f'/api/projects/{project}/prompt-results', None, 200)
        by_id = {item['result_id']: item for item in stored['results']}
        self.assertEqual(2, stored['result_count'],
                         'both produced documents must be kept, not just the last one')
        composition_row = by_id[prompt_document['composition_id']]
        self.assertEqual(composed['document_sha256'], composition_row['content_sha256'],
                         'the stored digest is not the digest the composing route published')
        self.assertEqual(composition_row['review_state'], 'UNREVIEWED',
                         'a result nobody signed must not arrive pre-accepted')
        self.assertEqual(by_id[reversal['document']['reversal_id']]['content_sha256'],
                         reversal['document_sha256'])
        self.assertEqual('image-generation', composition_row['document']['target'])

        # A named human accepts the composition. This is the local acceptance record; it is not the
        # outbound candidate approval further down, and it is not a jury verdict on artwork.
        accepted = self.hop(
            'prompt-accept', 'POST',
            f'/api/projects/{project}/prompt-results'
            f'/{prompt_document["composition_id"]}/review',
            {'decision': 'ACCEPTED', 'reviewer': 'dtalex66', 'reviewer_kind': 'human',
             'reviewed_at': '2026-10-19T00:00:00Z',
             'note': 'every sentence in the text is a field I filed for this project'}, 201)
        self.assertEqual(composition_row['content_sha256'],
                         accepted['review']['content_sha256'],
                         'the signature does not quote the bytes it says it judged')

        # The acceptance seam: a human verdict filed against the version the ASSET hop just
        # returned, over HTTP. This is the connection that previously existed only inside two
        # separate fixtures -- the jury test published its own version straight into the
        # database, so nothing had ever proved that an imported asset yields something a
        # verdict can be recorded against.
        from test_jury_http import CRITERIA
        verdict = self.hop(
            'jury-verdict', 'POST', f'/api/projects/{project}/jury/verdict',
            {'schemaVersion': 'design-lab/assurance-jury-record/v2', 'kind': 'JURY_VERDICT',
             'jury_record_id': 'jury-chain-1',
             'subject_ref': f'version:{asset_version}', 'artifact_sha256': asset_sha256,
             'juror': {'juror_id': 'dtalex66', 'kind': 'HUMAN', 'members': [],
                       'attestation': 'reviewed the imported artwork'},
             'criteria': CRITERIA, 'verdict': 'APPROVE',
             'decided_at': '2026-10-19T00:00:00Z', 'supersedes': None, 'evidence_refs': []},
            201)
        self.assertEqual(verdict['subject_ref'], f'version:{asset_version}')
        jury = self.hop('jury-readback', 'GET', f'/api/projects/{project}/jury', None, 200)
        self.assertEqual(1, jury['verdict_count'])
        self.assertEqual('ACCEPTED', jury['human_acceptance'])

        from test_rights_http import decision
        self.hop('rights', 'POST', f'/api/projects/{project}/rights',
                 decision(decision_id='rd-chain-1'), 201)
        rights = self.hop('rights-readback', 'GET', f'/api/projects/{project}/rights',
                          None, 200)
        self.assertEqual(1, rights['decision_count'])
        self.assertEqual('CLEARED', rights['rights_clearance'],
                         'an approved scope must clear rights, and NOT_REVIEWED here would '
                         'mean the write never landed')

        # The candidate is derived from what this chain actually accepted rather than imported from
        # an unrelated fixture: its `evidence_sha256` is the digest of the composition the human hop
        # signed, and its statement is about that signature. The rights and provenance *shape* still
        # comes from the closed contract helper, because restating that shape here would create a
        # second authority able to drift from the write path. Two provenance ids stay the literal
        # UNUSED: the owner fills those, a proxy may not mint them, and this chain now shows the
        # export echoing that choice instead of a fabricated job number. `design_lab_sha` remains
        # the fixture's obvious placeholder on purpose -- a test must not smuggle a live commit into
        # a record that could later be read as a citation of one.
        from test_knowledge_http import candidate
        created = self.hop(
            'candidate', 'POST', f'/api/projects/{project}/knowledge-candidates',
            candidate(candidate_id='kc-chain-1',
                      source={'design_lab_sha': 'a' * 40, 'job_id': 'UNUSED',
                              'operation_id': 'UNUSED',
                              'evidence_sha256': composition_row['content_sha256']},
                      payload={'title': 'compose from filed fields, then sign the bytes',
                               'statement': 'a prompt assembled only from stored fields is '
                                            're-checkable: the accepted result '
                                            f'{prompt_document["composition_id"]} was signed by a '
                                            'named human against its own content digest',
                               'applies_to': ['editorial', 'brand']}), 201)
        self.assertEqual('PENDING_HUMAN_APPROVAL', created['review']['state'],
                         'a fresh candidate must not arrive pre-approved')
        self.assertEqual(composition_row['content_sha256'],
                         created['source']['evidence_sha256'],
                         'the candidate does not cite the artifact this chain produced and accepted')
        candidate_id = created['candidate_id']

        reviewed = self.hop(
            'review', 'POST',
            f'/api/projects/{project}/knowledge-candidates/{candidate_id}/review',
            {'decision': 'APPROVE', 'reviewer_id': 'dtalex66', 'reviewer_kind': 'human',
             'reviewed_at': '2026-10-19T00:00:00Z', 'note': None, 'reason': None},
            200)
        self.assertEqual('APPROVED', reviewed['review']['state'])

        readback = self.hop(
            'candidate-readback', 'GET',
            f'/api/projects/{project}/knowledge-candidates', None, 200)
        self.assertEqual(1, readback['candidate_count'])
        row = next((item for item in readback['candidates']
                    if item['candidate_id'] == candidate_id), None)
        self.assertIsNotNone(row, f'the reviewed candidate is not in the readback: {self.hops}')
        self.assertEqual('APPROVED', row['review_state'])

        # The exit the segment never had: the approved candidate the review hop just decided is
        # now addressable as an export. Answering 200 is only "assembled and contract-valid" --
        # the envelope has to keep saying nothing left the machine, or the chain would end in a
        # delivery claim the service cannot make.
        exported = self.hop(
            'export', 'GET',
            f'/api/projects/{project}/knowledge-candidates/{candidate_id}/export', None, 200)
        self.assertEqual('design-lab/assurance-knowledge-candidate-export/v1',
                         exported['export']['schemaVersion'])
        self.assertEqual('NOT_CONNECTED', exported['outbound']['transport'])
        self.assertEqual(0, exported['outbound']['sent_count'])
        self.assertEqual('UNUSED', exported['provenance']['job_id'],
                         'the export did not echo the provenance ids the candidate hop stored')
        self.assertEqual('EXPLICITLY_UNUSED', exported['provenance']['job_id_state'],
                         'an explicit "not used" must be distinguishable from a blank field')
        self.assertEqual('UNUSED:UNUSED',
                         exported['v1_projection']['source_id'],
                         'the v1 projection rebuilt source_id from something other than the stored ids')
        self.assertEqual(composition_row['content_sha256'],
                         exported['export']['source']['evidence_sha256'],
                         'the exported candidate cites something other than the artifact this chain '
                         'produced and a human accepted')
        print('CHAIN_HOPS ' + ' '.join(self.hops))

    def test_the_jury_readback_offers_an_imported_asset_version_as_a_verdict_target(self):
        """What the desktop's jury panel actually reads.

        The panel never goes looking for versions of its own: `apps/workbench/shell.ts` renders
        `reviewable_versions` from GET /projects/<id>/jury straight into the version select, and
        posts the verdict against whatever that read offered. So "a person can judge an imported
        asset from the UI" rests on that one field. The chain walk above proves a verdict can be
        posted against a version id taken from the *import* response, which is not the same claim.
        """
        project = self.hop('project', 'POST', '/api/projects',
                           {'name': 'Jury target read'}, 201)['project']['id']
        imported = self.hop(
            'asset', 'POST', f'/api/projects/{project}/assets',
            {'content_base64': base64.b64encode(_png_bytes()).decode('ascii'),
             'idempotency_key': 'jury-target-asset'},
            201)['asset']

        offered = self.hop('jury-targets', 'GET', f'/api/projects/{project}/jury', None, 200)
        rows = offered['reviewable_versions']
        want = f"version:{imported['version_id']}"
        self.assertIn(want, [row['subject_ref'] for row in rows],
                      f'the read side never offers the imported version as reviewable: '
                      f'{[row["subject_ref"] for row in rows]}')
        self.assertEqual(imported['sha256'],
                         next(row['artifact_sha256'] for row in rows if row['subject_ref'] == want),
                         'the panel is offered a label for the version but not the bytes the '
                         'verdict is actually about')

    def test_the_delivery_leg_reaches_a_preflight_verdict_on_one_project(self):
        """The last reachable segment, on the SAME project the service already owns.

        `test_service_http` seeds a native export into its own fixture project, so nothing had
        shown that a project can go from a native attempt through a registered bundle to a
        preflight verdict in one pass. The native dispatch is patched because no host is
        launched here -- that is the controlled-runtime boundary, not a simulated success: the
        bundle is real bytes, registered by id, and the preflight verdict is computed from them.
        """
        outcome = self._deliver_to_preflight()
        report = outcome['report']
        from design_lab.assurance import production_preflight as pp
        self.assertIn(report['verdict'], pp.VERDICTS)
        self.assertEqual(sum(report['counts'].values()), len(report['findings']))
        # Whatever the verdict, it must be about the bytes that were actually registered:
        # the digest the bundle published is the one the checker was handed.
        self.assertTrue(any(item.get('measured') for item in report['findings']),
                        'no finding reports a measurement, so the verdict is not evidence')
        print('DELIVERY_HOPS ' + ' '.join(self.hops))

    def test_the_native_asset_verify_route_re_reads_the_stored_bytes(self):
        """What `…/native-assets/<id>/verify` measures, proved by moving the bytes.

        The list route answers `verification: METADATA_ONLY` for the same row, so the only
        difference a caller can act on is this route's own re-hash. A label that would also come back
        `HASH_VERIFIED` if the file were tampered with would be decoration, so the control is the
        tamper: the ledger's stored artifact is rewritten with bytes of the SAME length (a size
        check alone would still pass), the verdict must move to `NATIVE_ARTIFACT_UNVERIFIED`, and
        restoring the original bytes must bring `HASH_VERIFIED` back. The unknown-id half is the
        other boundary: an id shaped like a native asset but never registered is 404, not a
        verification of nothing.
        """
        from contextlib import closing
        import sqlite3
        delivered = self._deliver_to_preflight()
        project = delivered['project']
        listed = self.call('GET', f'/api/projects/{project}/native-assets')[1]['assets']
        self.assertTrue(listed, 'the delivery leg registered no native asset to verify')
        row = listed[0]
        self.assertEqual('METADATA_ONLY', row['verification'],
                         'the list route started claiming byte verification it does not perform')

        with closing(sqlite3.connect(self.service.database)) as conn:
            stored = conn.execute(
                'SELECT f.path FROM artifact f JOIN asset_version v ON f.version_id=v.version_id '
                'WHERE v.version_id=?', (row['version_id'],)).fetchone()[0]
        artifact = Path(stored)
        self.assertTrue(artifact.is_file(),
                        f'the ledger points at a missing artifact: {stored}')
        original = artifact.read_bytes()
        self.addCleanup(artifact.write_bytes, original)

        status, answer = self.call('GET',
                                   f'/api/projects/{project}/native-assets/{row["id"]}/verify')
        self.assertEqual(status, 200, answer)
        checked = answer['asset']
        self.assertEqual('HASH_VERIFIED', checked['verification'])
        # The verdict must be about the row the list route published, not a re-derived one.
        self.assertEqual((row['id'], row['version_id'], row['sha256'], row['byte_size']),
                         (checked['id'], checked['version_id'], checked['sha256'],
                          checked['byte_size']))
        self.assertEqual(original, artifact.read_bytes(),
                         'verify rewrote the artifact it was only supposed to read')

        artifact.write_bytes(b'X' * len(original))
        tampered = self.call('GET', f'/api/projects/{project}/native-assets/{row["id"]}/verify')
        self.assertEqual(409, tampered[0], tampered[1])
        self.assertEqual('NATIVE_ARTIFACT_UNVERIFIED', tampered[1]['error'],
                         'a same-length rewrite of the stored bytes slipped past the check')
        artifact.write_bytes(original)
        again = self.call('GET', f'/api/projects/{project}/native-assets/{row["id"]}/verify')
        self.assertEqual((200, 'HASH_VERIFIED'), (again[0], again[1]['asset']['verification']),
                         'the verdict did not come back when the bytes were restored')

        ghost = 'native-' + '0' * 64
        missing = self.call('GET', f'/api/projects/{project}/native-assets/{ghost}/verify')
        self.assertEqual(404, missing[0], missing[1])
        self.assertEqual('NATIVE_ASSET_NOT_FOUND', missing[1]['error'])
        print('NATIVE_VERIFY layout=' + ('installed' if INSTALLED_MODE else 'source')
              + ' clean=HASH_VERIFIED tampered=NATIVE_ARTIFACT_UNVERIFIED'
              ' unknown=NATIVE_ASSET_NOT_FOUND')

    def _deliver_to_preflight(self):
        """Run the native leg under the controlled scope, bundle it, and preflight that bundle.

        Extracted because two cases need the same delivered bundle: the leg's own verdict
        assertions, and the layout sweep that calls every ledger route, which cannot name a
        bundle-version id without it. Nothing about the boundary changed by moving it -- the
        dispatch is still patched, so this stays a controlled runtime, not a host run.
        """
        import hashlib
        from unittest.mock import patch
        from design_lab.native_tasks import NativeTasks

        project = self.hop('project', 'POST', '/api/projects',
                           {'name': 'Delivery leg'}, 201)['project']['id']
        run = self.service.paths.category_dir('runtime', 'chain-delivery')
        run.mkdir(parents=True, exist_ok=True)
        job = dict(schemaVersion='design-lab/photoshop-native-job/v1', jobId='chain-export',
                   runRoot=str(run), width=8, height=6, assets=[], outputName='native.psd',
                   previewName='preview.png',
                   layers=[dict(id='background', kind='fill', bounds=[0, 0, 8, 6],
                                color=[0, 0, 0])])

        def native(_host, payload, **_kwargs):
            output = {}
            for kind, name in (('psd', 'native.psd'), ('png', 'preview.png')):
                data = ('chain controlled ' + kind).encode()
                (run / name).write_bytes(data)
                output[kind] = dict(sha256=hashlib.sha256(data).hexdigest(),
                                    byte_size=len(data))
            raw = json.dumps(payload, sort_keys=True, ensure_ascii=True,
                             separators=(',', ':')).encode()
            return dict(status='NATIVE_READBACK', job_id=payload['jobId'],
                        job_sha256=hashlib.sha256(raw).hexdigest(), host_version='fixture',
                        bridge_sha256='b' * 64, inputs={}, artifacts=output,
                        documents_before=0, documents_after=0)

        with patch('design_lab.native_tasks._dispatch', side_effect=native):
            attempt = NativeTasks(self.service).execute(
                project, 'photoshop', job, idempotency_key='chain-export',
                approved_root=run,
                # `native_tasks.execute` refuses any scope other than this literal
                # (`native_tasks.py:94`), which is itself a chain fact: the native leg is
                # reachable under a controlled test scope, not from an unattended production
                # caller. Recording it here keeps the delivery hop from reading as E3.
                authorization=dict(actor='fixture', scope='project-native-test',
                                   receipt='controlled boundary'))
        job_id = attempt['attempt']['job_id']
        self.hops.append('native=READBACK')

        bundle = self.hop(
            'bundle', 'POST', f'/api/projects/{project}/tasks/{job_id}/bundle', {}, 201)
        report = self.hop(
            'preflight', 'POST',
            f"/api/projects/{project}/bundles/{bundle['bundle']['id']}/preflight", {}, 200)
        return dict(project=project, job_id=job_id, bundle=bundle['bundle'], report=report)

    #: Every GET row the ledger declares, as the concrete paths this sweep performs against it.
    #: The mapping is asserted in both directions, so a route added to the ledger cannot be quietly
    #: dropped from the sweep: it fails until someone names a read for it or records why no id can
    #: be constructed here. `{token}` slots are filled from objects this service wrote.
    GET_READS = {
        '/api/health': ['/api/health'],
        '/api/environment': ['/api/environment'],
        '/api/local-session': ['/api/local-session'],
        '/api/capabilities': ['/api/capabilities'],
        '/api/domains': ['/api/domains'],
        '/api/models': ['/api/models'],
        # owner 2026-10-28 unfroze the automation capability class. The read is the registered
        # roster: no id to construct, nothing launched, and the sweep asserts the served body
        # answers NOT_PROBED with enabled:false rather than letting a page invent either.
        '/api/automation-connectors': ['/api/automation-connectors'],
        # DL-KB-02/04 (batch K). Two reads of the search route on purpose: the bare path is the
        # browse branch, and the query is a two-character Chinese word the trigram index cannot
        # answer, so this sweep measures the fallback the product actually ships.
        '/api/knowledge-entries/search': ['/api/knowledge-entries/search',
                                          '/api/knowledge-entries/search?q=%E5%88%86%E9%95%9C'],
        '/api/knowledge-entries/(kentry-[0-9a-f]{32})': ['/api/knowledge-entries/{kentry}'],
        '/api/design-systems': ['/api/design-systems'],
        '/api/evidence-projection': ['/api/evidence-projection'],
        '/api/task-preflight': ['/api/task-preflight?task=image-import:{project}'],
        '/api/projects/([0-9a-f]{32})': ['/api/projects/{project}'],
        '/api/projects/([0-9a-f]{32})/design-layer': ['/api/projects/{project}/design-layer'],
        '/api/projects/([0-9a-f]{32})/jury': ['/api/projects/{project}/jury'],
        '/api/projects/([0-9a-f]{32})/rights': ['/api/projects/{project}/rights'],
        '/api/projects/([0-9a-f]{32})/research': ['/api/projects/{project}/research'],
        '/api/projects/([0-9a-f]{32})/native-runtime':
            ['/api/projects/{project}/native-runtime'],
        '/api/projects/([0-9a-f]{32})/model-selection':
            ['/api/projects/{project}/model-selection'],
        '/api/projects/([0-9a-f]{32})/prompt-results': ['/api/projects/{project}/prompt-results'],
        '/api/projects/([0-9a-f]{32})/knowledge-candidates':
            ['/api/projects/{project}/knowledge-candidates'],
        # DL-KB-08. The output-type vocabulary is read before any workspace exists, which is the
        # reason it is not part of the project-scoped collection below.
        '/api/assistance-plan-output-types': ['/api/assistance-plan-output-types'],
        # DL-KB-07 (batch K). The collection and one plan's readback. The plan is created by this
        # sweep before the reads, so the detail route is measured on bytes the service stored.
        '/api/projects/([0-9a-f]{32})/assistance-plans(?:\\?[^#]*)?':
            ['/api/projects/{project}/assistance-plans'],
        '/api/projects/([0-9a-f]{32})/assistance-plans/(aplan-[0-9a-f]{32})':
            ['/api/projects/{project}/assistance-plans/{aplan}'],
        # DL-KB-12: one stored revision, read by number. The plan this sweep files has exactly one
        # revision, so r1 is both the row asked for and the newest -- the honest read the comparison
        # page depends on, reached over a real socket here. The two-revision case, where r1's bytes
        # are NOT the current ones, is measured by design-lab/tests/test_assistance_plan.py and by
        # the live payload gate, which reads both rows of a plan that carries a second revision.
        '/api/projects/([0-9a-f]{32})/assistance-plans/(aplan-[0-9a-f]{32})/revisions/([1-9][0-9]{0,8})':
            ['/api/projects/{project}/assistance-plans/{aplan}/revisions/1'],
        # DL-KB-11: the handoff material, one read per format. Three of them answer 200 for the plan
        # this sweep files; the 分镜 CSV answers 409 PLAN_EXPORT_NO_SHOTS, because that plan is a
        # poster with no shot rows and the route will not render a storyboard out of an empty table.
        # That refusal is therefore reached in the real chain rather than only asserted, and the
        # CSV's 200 branch is measured on a shot-bearing plan by
        # design-lab/tests/test_plan_export.py and by the live payload contract gate.
        '/api/projects/([0-9a-f]{32})/assistance-plans/(aplan-[0-9a-f]{32})/export(?:\\?[^#]*)?':
            ['/api/projects/{project}/assistance-plans/{aplan}/export?format=markdown',
             '/api/projects/{project}/assistance-plans/{aplan}/export?format=txt',
             '/api/projects/{project}/assistance-plans/{aplan}/export?format=json',
             '/api/projects/{project}/assistance-plans/{aplan}/export?format=storyboard_csv'],
        # DL-KB-16: the voluntary external-use history of the plan this sweep just filed. Nothing
        # here records a report, so the honest answer is an empty history that still carries the
        # outcome words the store enforces -- a page reading it gets its vocabulary from the
        # service, not from a list someone copied into TypeScript.
        '/api/projects/([0-9a-f]{32})/assistance-plans/(aplan-[0-9a-f]{32})/feedback(?:\\?[^#]*)?':
            ['/api/projects/{project}/assistance-plans/{aplan}/feedback'],
        # DL-KB-09: the three target-profile reads. These are project-free (the profiles are the
        # tracked config's rows, not per-project state), so they are called before the slots that
        # belong to a project would matter; the detail route is called with an id the list itself
        # served rather than one assembled by this test.
        '/api/target-profile-axes': ['/api/target-profile-axes'],
        '/api/target-profiles(?:\\?[^#]*)?': ['/api/target-profiles'],
        '/api/target-profiles/(tprof-[0-9a-f]{32})': ['/api/target-profiles/{tprof}'],
        '/api/projects/([0-9a-f]{32})/briefs(?:\\?after=(brief-[0-9a-f]{32}))?':
            ['/api/projects/{project}/briefs'],
        '/api/projects/([0-9a-f]{32})/briefs/(brief-[0-9a-f]{32})':
            ['/api/projects/{project}/briefs/{brief}'],
        '/api/projects/([0-9a-f]{32})/briefs/(brief-[0-9a-f]{32})/lineage':
            ['/api/projects/{project}/briefs/{brief}/lineage'],
        '/api/projects/([0-9a-f]{32})/directions(?:\\?after=(direction-[0-9a-f]{32}))?':
            ['/api/projects/{project}/directions'],
        '/api/projects/([0-9a-f]{32})/directions/(direction-[0-9a-f]{32})':
            ['/api/projects/{project}/directions/{direction}'],
        '/api/projects/([0-9a-f]{32})/directions/(direction-[0-9a-f]{32})/lineage':
            ['/api/projects/{project}/directions/{direction}/lineage'],
        '/api/design-briefs/(brief-[0-9a-f]{32})/lineage':
            ['/api/design-briefs/{brief}/lineage'],
        '/api/design-directions/(direction-[0-9a-f]{32})/lineage':
            ['/api/design-directions/{direction}/lineage'],
        '/api/projects/([0-9a-f]{32})/design-system-tokens':
            ['/api/projects/{project}/design-system-tokens'],
        '/api/projects/([0-9a-f]{32})/design-system-tokens/(<DESIGN_SYSTEM_NAME_PATTERN>)(/lineage)?':
            ['/api/projects/{project}/design-system-tokens/{design_system}',
             '/api/projects/{project}/design-system-tokens/{design_system}/lineage'],
        '/api/projects/([0-9a-f]{32})/assets(?:/(img-[0-9a-f]{64})/content)?':
            ['/api/projects/{project}/assets', '/api/projects/{project}/assets/{asset}/content'],
        '/api/projects/([0-9a-f]{32})/tasks(?:\\?after=((?:native-)?job-[0-9a-f]{64}))?':
            ['/api/projects/{delivery_project}/tasks'],
        '/api/projects/([0-9a-f]{32})/tasks/((?:native-)?job-[0-9a-f]{64})(/events)?'
        '(?:\\?after=([0-9]{1,16}))?':
            ['/api/projects/{delivery_project}/tasks/{job}',
             '/api/projects/{delivery_project}/tasks/{job}/events'],
        '/api/projects/([0-9a-f]{32})/bundles': ['/api/projects/{delivery_project}/bundles'],
        '/api/projects/([0-9a-f]{32})/bundles/(bundle-native-[0-9a-f]{64})/versions/'
        '(v-[0-9a-f]{32})/content':
            ['/api/projects/{delivery_project}/bundles/{bundle}/versions/{version}/content'],
        '/api/projects/([0-9a-f]{32})/bundles/(bundle-native-[0-9a-f]{64})/versions/'
        '(v-[0-9a-f]{32})/receipt':
            ['/api/projects/{delivery_project}/bundles/{bundle}/versions/{version}/receipt'],
        '/api/projects/([0-9a-f]{32})/native-assets(?:\\?after=(native-[0-9a-f]{64}))?':
            ['/api/projects/{delivery_project}/native-assets'],
        '/api/projects/([0-9a-f]{32})/native-assets/(native-[0-9a-f]{64})/verify':
            ['/api/projects/{delivery_project}/native-assets/{native_asset}/verify'],
        '/api/projects/([0-9a-f]{32})/knowledge-candidates/([A-Za-z0-9_.:-]{1,80})/export':
            ['COVERED-ELSEWHERE: the acceptance walk above creates, reviews and exports one '
             'candidate in this same layout (export=200), so the read is measured -- just not by '
             'this sweep'],
        'workbench.ROUTES': ['NOT-A-PATH: a ledger row naming the module table, not a URL'],
        '/workbench': ['/workbench'],
    }

    #: 5xx the sweep may see, per layout, and what each one actually asserts. There is one entry:
    #: an installed wheel has no governance checkout to project, so the evidence projection answers
    #: 503 naming the ledger file it cannot find rather than issuing a clean bill -- a verdict about
    #: the install, not a packaged contract it failed to open. The same route answers 200 in a
    #: source checkout, which is what makes the empty set there meaningful rather than lucky.
    EXPECTED_REFUSALS = {
        'source': {},
        'installed': {'/api/evidence-projection': (503, 'EVIDENCE_LEDGER_ABSENT')},
    }

    def test_every_ledger_get_route_is_answered_in_this_layout(self):
        """Call every GET boundary the ledger declares against objects this service really wrote.

        The claim this retires is the one §5.24 had to leave open: 14 GET rows were 'not called'
        because they need a real asset, brief, direction, bundle or version id. Here the same
        objects the acceptance chain writes are used to construct them, and the reading is printed
        as a denominator (constructed / answered / named-verdict / not-constructible) so the next
        reader can see what was measured and what was not. A 5xx that is not a documented refusal is
        a finding: inside an installed wheel it is the same class of defect this batch paid -- a
        contract file the route could not open, answering as if it were a verdict.
        """
        ledger = json.loads((ROOT / 'design-lab' / 'config' / 'contract-bindings.json')
                            .read_text(encoding='utf-8'))
        rows = [row['route'] for row in ledger['routes'] if row['method'] == 'GET']
        self.assertEqual(sorted(set(rows) - set(self.GET_READS)), [],
                         'these ledger GET routes have no entry in this sweep, so they would be '
                         'silently unmeasured: ' + str(sorted(set(rows) - set(self.GET_READS))))
        self.assertEqual(sorted(set(self.GET_READS) - set(rows)), [],
                         'this sweep names routes the ledger no longer declares: '
                         + str(sorted(set(self.GET_READS) - set(rows))))

        project = self.hop('project', 'POST', '/api/projects', {'name': 'GET sweep'}, 201
                           )['project']['id']
        imported = self.hop(
            'asset', 'POST', f'/api/projects/{project}/assets',
            {'content_base64': base64.b64encode(_png_bytes()).decode('ascii'),
             'idempotency_key': 'sweep-asset'}, 201)['asset']
        brief = self.hop(
            'brief', 'POST', f'/api/projects/{project}/briefs',
            {'title': 'Sweep brief', 'goals': ['sweep'], 'constraints': None,
             'reference_asset_ids': [imported['id']], 'idempotency_key': 'sweep-brief'},
            201)['brief']['brief_id']
        direction = self.hop(
            'direction', 'POST', f'/api/projects/{project}/directions',
            {'brief_id': brief, 'title': 'Sweep direction', 'style_notes': ['measured'],
             'color_mood': 'cool', 'typography_mood': 'sans',
             'idempotency_key': 'sweep-direction'}, 201)['direction']['direction_id']
        delivered = self._deliver_to_preflight()
        # The knowledge library is global (like /api/capabilities), so the entry this sweep reads
        # back is written through the create route with no project id: the read is measured on an
        # object this service really stored, not on an id assembled by hand.
        knowledge = self.hop('knowledge', 'POST', '/api/knowledge-entries', {
            'entry_type': 'METHOD', 'title': '分镜拆解三步法',
            'summary': '把一段脚本拆成镜头表：先定节拍，再定景别，最后定转场。',
            'domain_tags': ['film'], 'task_tags': ['storyboard'],
            'target_tools': ['storyboarder'],
            'body': '第一步按段落切节拍。第二步给每个节拍选景别。第三步只标必要的转场。',
            'applicability': 'UNKNOWN', 'limits': 'UNKNOWN',
            'source': {'sourceId': 'get-sweep', 'origin': 'UNKNOWN', 'author': 'sweep',
                       'license': 'UNKNOWN', 'licenseStatus': 'unknown',
                       'allowedUsage': 'UNKNOWN', 'citationScope': 'UNKNOWN', 'version': '1',
                       'observedAt': '2026-10-23T00:00:00Z', 'contentHash': 'UNKNOWN',
                       'verification': 'UNVERIFIED'},
            'related_capability_ids': [], 'recommended': True, 'created_by': 'sweep',
            'supersedes': None}, 201)['entry']['knowledge_entry_id']
        # DL-KB-07: a neutral plan over the asset and brief this sweep already wrote, so both
        # assistance reads below answer about a stored document rather than a fabricated id.
        plan = self.hop(
            'assistance-plan', 'POST', f'/api/projects/{project}/assistance-plans',
            {'objective': '为秋季新品做一张克制的主视觉海报', 'output_type': 'IMAGE',
             'neutral_creative': '一束侧光穿过纸纤维，留出大面积空白承载标题。',
             'brand_constraints': ['只用两种油墨'], 'role_constraints': [],
             'lens': None, 'sound': None,
             'references': [{'kind': 'ASSET', 'id': imported['id']}],
             'external_steps': [{'step': '手动导出印刷 PDF', 'tool': 'Illustrator',
                                 'job_id': None, 'operation_id': 'op-get-sweep'}],
             'known_gaps': ['目标纸张未定'], 'limits': ['未包含多语言排版'],
             'created_by': 'sweep'}, 201)['plan']['plan_id']
        systems = self.call('GET', '/api/design-systems')[1]
        names = _values_under(systems, 'name', 'id')
        self.assertTrue(names, 'the design-system catalog named no entry to build a token route')
        # DL-KB-09: the profile detail route is called with an id the list itself served. The
        # profiles are the tracked config's rows, so this sweep writes nothing to reach them -- a
        # draft would give two owners of the same byte.
        profiles = self.call('GET', '/api/target-profiles')[1]
        self.assertTrue(profiles['profiles'],
                        'the profile list served no row, so …/target-profiles/<id> would go '
                        'unmeasured rather than be read')

        # The delivery leg registers a native asset row (the primary artifact the host read back),
        # so `…/native-assets/<id>/verify` is constructible here -- it was filed UNCONSTRUCTED on the
        # claim that the leg "registers a bundle, not an asset row", and that claim is false: the same
        # leg's own GET /native-assets answers this id.
        native_assets = self.call('GET', f"/api/projects/{delivered['project']}/native-assets")[1]
        self.assertTrue(native_assets['assets'],
                        'the delivery leg produced no native asset row to verify, so the verify '
                        'route would silently go unmeasured again')
        slots = {'project': project, 'asset': imported['id'], 'brief': brief,
                 'direction': direction, 'design_system': names[0],
                 'delivery_project': delivered['project'], 'bundle': delivered['bundle']['id'],
                 'version': delivered['bundle']['version_id'], 'job': delivered['job_id'],
                 'native_asset': native_assets['assets'][0]['id'], 'kentry': knowledge,
                 'aplan': plan, 'tprof': profiles['profiles'][0]['profile_id']}

        layout = 'installed' if INSTALLED_MODE else 'source'
        answered, verdicts, unmeasured, refused = [], [], [], {}
        for route, reads in self.GET_READS.items():
            for read in reads:
                if read.startswith(('UNCONSTRUCTED:', 'COVERED-ELSEWHERE:', 'NOT-A-PATH:')):
                    unmeasured.append((route, read.split(':', 1)[0], read.split(':', 1)[1][:60]))
                    continue
                path = re.sub(r'\{(\w+)\}', lambda match: slots.get(match.group(1), ''), read)
                missing = sorted(name for name in ('project', 'asset', 'brief', 'direction',
                                                   'design_system', 'delivery_project', 'bundle',
                                                   'version', 'job', 'native_asset', 'kentry',
                                                   'aplan')
                                 if '{' + name + '}' in read and not slots.get(name))
                self.assertEqual(missing, [],
                                 f'{read} needs a slot this sweep has no value for: {missing}')
                status, payload = self.status_and_code(path)
                label = f'{read} -> {status}' + (f' {payload}' if status >= 400 else '')
                if status < 300:
                    answered.append(label)
                elif status < 500:
                    verdicts.append(label)
                else:
                    allowed = self.EXPECTED_REFUSALS[layout].get(path)
                    if allowed != (status, payload):
                        self.fail(f'{route} answered {label}: an unearned 5xx is either a contract '
                                  'file the service could not open or a refusal nobody read yet -- '
                                  'inspect it before naming it in EXPECTED_REFUSALS')
                    refused[path] = (status, payload)
        # Checked in both directions: a named refusal that stops happening is as stale as a new one
        # that appears without being earned, and an unused entry would excuse the next 5xx.
        self.assertEqual(refused, self.EXPECTED_REFUSALS[layout],
                         f'the {layout} layout answered a different set of permitted 5xx: '
                         f'{sorted(refused)} vs {sorted(self.EXPECTED_REFUSALS[layout])}')
        self.assertGreaterEqual(len(answered), 30,
                                'the sweep stopped reaching real reads: ' + str(len(answered)))
        print('GET_SWEEP layout=' + ('installed' if INSTALLED_MODE else 'source')
              + ' routes=' + str(len(rows)) + ' reads='
              + str(len(answered) + len(verdicts)) + ' answered=' + str(len(answered))
              + ' verdicts=' + str(len(verdicts)) + ' unmeasured=' + str(len(unmeasured)))
        for route, kind, reason in unmeasured:
            print('GET_SWEEP_UNMEASURED ' + kind + ' ' + route + ' :: ' + reason)

    def test_the_automation_projection_answers_from_the_records_it_ships(self):
        """The connector table must come from bytes the artefact itself carries.

        This route answers 200 either way, so the status code cannot separate "the package ships the
        registry" from "the package found nothing and said so". Measured before pyproject gained the
        two force-include lines, an installed wheel returned
        `registry_state=MISSING pack_state=MISSING connectors=0`, because the module derived the
        repository root from its own location and three levels above an installed package is the
        interpreter's `Lib`. An empty connector table is not a mild degradation here: it reads as
        "no connector is registered", which is a false statement about the repository. CI's
        clean-wheel job runs this module under `DL_LAUNCH_INSTALLED=1`, so the assertion is made
        against the installed package and the layout is printed with it.

        The id comparison is a real cross-check only in the installed layout, where the answer comes
        from the packaged copy while this test reads the committed one; in a source checkout both
        sides are the same file, which is why the layout rides on the printed line.
        """
        import json as _json
        status, answer = self.call('GET', '/api/automation-connectors')
        self.assertEqual(status, 200, f'the connector projection refused: {answer}')
        self.assertEqual(answer['registry_state'], 'READ',
                         'the projection could not open the adapter registry from where it is '
                         'running -- a packaged record is missing, not a verdict about hosts')
        self.assertEqual(answer['pack_state'], 'READ',
                         'the projection could not open the delivery pack manifest')
        served = sorted(row['id'] for row in answer['connectors'])
        self.assertEqual(len(served), 11,
                         'the registered connector population moved from 11 without this test '
                         'being told: ' + str(served))
        self.assertEqual(answer['counts']['connectors'], len(served),
                         'the count and the table disagree about the same payload')
        committed = _json.loads(
            (ROOT / 'docs/history/record-archive-2026-10-28-design-automation'
             / 'ARCHIVE-MANIFEST.json').read_text(encoding='utf-8'))
        self.assertEqual(served, sorted(r['id'] for r in committed['connectors']['rows']),
                         'the answer is not the committed roster: a row was dropped, added or '
                         'renamed between the record and the route')
        # Nothing about this is allowed to read as capability, in either layout.
        self.assertEqual(answer['counts']['probed_by_design_lab'], 0)
        self.assertEqual(answer['counts']['enabled'], 0)
        self.assertEqual(answer['counts']['native_tool_calls_executed'], 0)
        self.assertFalse([row for row in answer['connectors'] if row['design_lab_enabled']],
                         'an installed package offered a connector as enabled')
        print('AUTOMATION_READBACK layout=' + ('installed' if INSTALLED_MODE else 'source')
              + ' registry=' + answer['registry_state']
              + ' pack=' + answer['pack_state']
              + ' connectors=' + str(len(served))
              + ' adapters=' + str(answer['counts']['project_adapters']))

    def status_and_code(self, path):
        """Status plus the error code (or byte count), without assuming the body is JSON.

        A bundle's content route answers a ZIP, and the previous habit of parsing every body meant
        a real 200 could crash the sweep -- which is a worse report than a refusal.
        """
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=20)
        try:
            conn.request('GET', path, headers={'Authorization': 'Bearer ' + self.token,
                                               'Host': f'127.0.0.1:{self.port}',
                                               'Origin': f'http://127.0.0.1:{self.port}',
                                               'Sec-Fetch-Site': 'same-origin'})
            response = conn.getresponse()
            raw = response.read()
        finally:
            conn.close()
        try:
            return response.status, json.loads(raw).get('error', '')
        except (ValueError, AttributeError):
            return response.status, 'bytes:' + str(len(raw))

    def test_the_export_hop_exists_but_still_sends_nothing(self):
        """The chain now reaches the exit; it still does not reach outside the repository.

        This case used to assert that NO export route existed, so that anyone wiring the exit would
        have to re-earn the entry-point claim on purpose rather than by accident. The exit landed on
        owner authorisation (2026-10-20), so the boundary moved one notch and is pinned here in its
        new place: an export route exists and is walked by the acceptance chain above, while the
        transport it would need remains absent. Those are different facts, and the envelope has to
        keep saying so -- `outbound.transport` stays NOT_CONNECTED and `sent_count` stays 0, which is
        what stops a green export from being read as a delivery.
        """
        from design_lab.http_service import ROUTES
        export_routes = sorted(route.pattern for route in ROUTES if 'export' in route.pattern)
        self.assertEqual(
            ['/api/projects/([0-9a-f]{32})/assistance-plans/(aplan-[0-9a-f]{32})/export'
             '(?:\\?[^#]*)?',
             '/api/projects/([0-9a-f]{32})/knowledge-candidates'
             '/([A-Za-z0-9_.:-]{1,80})/export'], export_routes,
            'an export route moved or multiplied; the acceptance chain walks exactly one candidate '
            'exit hop, and the plan-material read is a second, different claim -- see the sentence '
            'below')
        # The second one appeared on purpose (DL-KB-11, owner 2026-10-23 batch K4). It is not a
        # transport: it renders the stored revision as markdown/txt/json/分镜 CSV and answers
        # `sent: false`. Because the two words mean different things, this file keeps them apart in
        # both directions: the candidate exit is still the only hop that could be read as an
        # outbound delivery, and the material read is measured on its own four calls in the GET
        # sweep above -- a route that only existed in the table would not be reached there.
        self.assertIn('/api/projects/([0-9a-f]{32})/assistance-plans/(aplan-[0-9a-f]{32})/export'
                      '(?:\\?[^#]*)?', self.GET_READS,
                      'the plan-material export route is declared but not called by this layout; '
                      'then no evidence says a real stored plan can be handed over')
        # Nothing in the route table can put the document on a wire.
        self.assertEqual([], [route.pattern for route in ROUTES
                              if 'send' in route.pattern or 'deliver-to' in route.pattern],
                         'a transport route appeared; then the chain claim, the readback text and '
                         'this file all need to change together')
        source = (ROOT / 'src/design_lab/knowledge_review.py').read_text(encoding='utf-8')
        self.assertIn('"transport": "NOT_CONNECTED"', source,
                      'the outbound transport no longer says NOT_CONNECTED; if a real transport '
                      'was added, update the chain claim in the same change')
        self.assertEqual(2, source.count('"transport": "NOT_CONNECTED"'),
                         'the readback and the export envelope are two different answers and both '
                         'must keep saying nothing was sent')


if __name__ == '__main__':
    unittest.main(verbosity=2)
