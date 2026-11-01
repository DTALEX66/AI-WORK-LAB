# SPDX-License-Identifier: MIT
"""DeliveryReceipt V2 on the real delivery path: emitted, persisted, read back.

Before this wiring, ``build_receipt`` had no caller in ``src/`` at all: the document
that is supposed to say *what shipped, from which host, with which hashes, and whether
the host read it back* was a library only tests could reach, so a real delivery carried
no receipt. These tests drive the product -- real SQLite, real published archive, real
service restart -- and double only the host/COM boundary.

The honesty rules under test, read out of ``delivery_receipt.py`` itself:

* ``axes.delivery`` is PASS only with a host readback for every deliverable, and no
  host opens a delivered artifact in this product, so every real delivery receipt is
  PARTIAL. A test that demanded a PASS document here would be demanding a lie.
* gate states the bundle records as NOT_REVIEWED / NOT_VERIFIED project to
  NOT_RUN / UNVERIFIED. The receipt may not upgrade them, and the archive's own
  manifest must still say NOT_REVIEWED after the receipt is written.
* a fact this mapping cannot derive from a recorded value stops the receipt instead
  of filling in a plausible one (``RefusesRatherThanInventsTest``).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch
import zipfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from design_lab.image_assets import ImageAssetError  # noqa: E402
from design_lab.interop import InteropError, delivery_receipt  # noqa: E402
from design_lab.interop import load_schema, schema_errors  # noqa: E402
from design_lab.interop.provenance import build_manifest, manifest_digest  # noqa: E402
from design_lab.native_delivery import NativeDelivery  # noqa: E402
from design_lab.native_tasks import NativeTasks  # noqa: E402
from design_lab.service import ProjectService  # noqa: E402


class DeliveryReceiptProductTest(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.project-local' / 'task-runtime' / 'delivery-receipt-tests'
        parent.mkdir(parents=True, exist_ok=True)
        self._tmp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / 'AGENTS.md').write_text('# synthetic delivery receipt fixture\n', encoding='utf-8')
        self._env = patch.dict(os.environ, {'PROJECT_LOCAL_ROOT': str(self.root / '.project-local')})
        self._env.start()
        self.addCleanup(self._env.stop)
        self.service = ProjectService(self.root)
        self.project = self.service.create_project('delivery receipt')['id']
        self.run = self.service.paths.category_dir('runtime', 'run')
        self.run.mkdir(parents=True)
        Image.new('RGB', (8, 6), 'blue').save(self.run / 'input.png')
        self.job = dict(schemaVersion='design-lab/photoshop-native-job/v1', jobId='receipt-job',
                        runRoot=str(self.run), width=8, height=6, outputName='output.psd',
                        previewName='output.png', assets=[dict(id='input', path=str(self.run / 'input.png'))],
                        layers=[dict(id='title', kind='text', font='ArialMT', text='Hi', size=10,
                                     position=[0, 0], color=[0, 0, 0])])

    # -- the product path ----------------------------------------------------- #

    def host(self, host, job, **kwargs):
        """The doubled COM boundary: it writes bytes, nothing re-opens them."""
        primary = self.run / job['outputName']
        preview = self.run / job['previewName']
        primary.write_bytes(b'8BPS\x00\x01 layered host output')
        Image.new('RGB', (8, 6), 'red').save(preview)

        def digest(path):
            return dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                        byte_size=path.stat().st_size)
        return dict(status='NATIVE_READBACK', job_id=job['jobId'], host_version='26.7.0',
                    bridge_sha256='b' * 64,
                    job_sha256=hashlib.sha256(json.dumps(job, sort_keys=True, ensure_ascii=True,
                                                         separators=(',', ':')).encode()).hexdigest(),
                    inputs={str(self.run / 'input.png'): digest(self.run / 'input.png')},
                    artifacts={'psd': digest(primary), 'png': digest(preview)},
                    documents_before=0, documents_after=0)

    def deliver(self, key='receipt-key'):
        with patch('design_lab.native_tasks._dispatch', side_effect=self.host):
            executed = NativeTasks(self.service).execute(self.project, 'photoshop', self.job,
                idempotency_key=key, approved_root=self.run,
                authorization=dict(actor='fixture', scope='project-native-test',
                                   receipt='controlled boundary'))
        created = NativeDelivery(self.service).create(self.project, executed['attempt']['job_id'])
        return executed, created

    def archive_of(self, asset_id, version_id):
        """The delivery bytes, read back through the product's own download path."""
        with NativeDelivery(self.service).content(self.project, asset_id, version_id) as streams:
            stream, size, digest = streams
            raw = stream.read()
        self.assertEqual(len(raw), size)
        return zipfile.ZipFile(io.BytesIO(raw))

    def member_digests(self, archive):
        return {info.filename: dict(sha256=hashlib.sha256(archive.read(info.filename)).hexdigest(),
                                    byte_size=info.file_size)
                for info in archive.infolist() if info.filename != 'bundle-manifest.json'}

    # -- (a) creating a delivery produces and persists a schema-valid receipt -- #

    def test_product_delivery_emits_a_receipt_that_validates_against_the_v2_schema(self):
        executed, created = self.deliver()
        receipt = created['bundle']['receipt']
        self.assertEqual(schema_errors(load_schema(delivery_receipt.SCHEMA_PATH), receipt), [])
        report = delivery_receipt.verify_receipt(receipt)
        self.assertTrue(report['verified'])
        self.assertEqual(report['job_id'], executed['attempt']['job_id'])
        # The receipt describes the archive the download path actually serves.
        archive = self.archive_of(created['bundle']['id'], created['bundle']['version_id'])
        manifest = json.loads(archive.read('bundle-manifest.json'))
        shipped = self.member_digests(archive)
        design_members = {name: record for name, record in manifest['files'].items()
                          if record['role'] in ('primary', 'preview')}
        self.assertEqual([entry['deliverable_id'] for entry in receipt['deliverables']],
                         sorted(design_members))
        for entry in receipt['deliverables']:
            record = shipped[entry['deliverable_id']]
            self.assertEqual(entry['artifact_sha256'], 'sha256:' + record['sha256'],
                             f"{entry['deliverable_id']}: the receipt names bytes the archive "
                             "does not contain")
            self.assertEqual(entry['byte_size'], record['byte_size'])
            self.assertEqual(entry['editable'],
                             manifest['files'][entry['deliverable_id']]['role'] == 'primary')
            # Provenance is recorded as a digest of the projection, and the digest
            # is reproducible from the delivery's own recorded facts.
            rebuilt = build_manifest(dict(
                deliverable_id=entry['deliverable_id'], artifact_sha256=entry['artifact_sha256'],
                asset_kind=delivery_receipt.BUNDLE_MEMBER_KINDS[
                    Path(entry['deliverable_id']).suffix.lower()],
                producer=dict(operation_id=manifest['metadata']['native_attempt_id'],
                              provider_id=manifest['metadata']['host'], model_id=None),
                inputs=[dict(version_id=item['id'],
                             sha256='sha256:' + manifest['files'][item['member']]['sha256'],
                             relationship='inputTo') for item in manifest['metadata']['input_assets']],
                actions=[dict(action='c2pa.created', when=self.ended_at(executed),
                              software_agent='photoshop ' + manifest['metadata']['host_version'])],
                rights_profile=delivery_receipt.BUNDLE_RIGHTS_PROFILE,
                created_at=self.ended_at(executed)))
            self.assertEqual(entry['provenance'], manifest_digest(rebuilt))
            self.assertNotIn('assertions', json.dumps(entry))
        self.assertEqual(report['readback_count'], 0)
        self.assertEqual(receipt['axes'], {'delivery': 'PARTIAL'})
        self.assertNotIn('rollback', receipt)
        # A receipt is a document about bytes, not a directory listing: it may not
        # leak the run root or the published archive path the way bundle['path'] did.
        self.assertNotIn(str(self.run), json.dumps(receipt))
        self.assertNotIn('path', created['bundle'])

    def ended_at(self, executed):
        with closing(sqlite3.connect(self.service.paths.database_path(self.service.database))) as conn:
            return conn.execute('SELECT ended_at FROM attempt_state WHERE attempt_id=?',
                                (executed['attempt']['attempt_id'],)).fetchone()[0]

    def test_the_receipt_records_gate_states_without_upgrading_rights_or_quality(self):
        executed, created = self.deliver()
        receipt = created['bundle']['receipt']
        requirements = {record['req_id']: record['status']
                        for record in receipt['deliverables'][0]['requirements']}
        self.assertEqual(requirements['req-rights-review'], 'NOT_RUN')
        self.assertEqual(requirements['req-quality-review'], 'NOT_RUN')
        self.assertEqual(requirements['req-font-rights'], 'NOT_RUN')
        self.assertEqual(requirements['req-link-relocation'], 'UNVERIFIED')
        self.assertNotIn('PASS', [requirements['req-rights-review'], requirements['req-quality-review']])
        # The bytes requirement is the one thing the delivery really proved, and it
        # proved it twice: the writer hashed the sources, verify_bundle re-reads members.
        self.assertEqual(requirements[delivery_receipt.BUNDLE_BYTES_REQUIREMENT], 'PASS')
        archive = self.archive_of(created['bundle']['id'], created['bundle']['version_id'])
        metadata = json.loads(archive.read('bundle-manifest.json'))['metadata']
        self.assertEqual(metadata['rights'], 'NOT_REVIEWED')
        self.assertEqual(metadata['quality'], 'NOT_REVIEWED')
        self.assertEqual(metadata['link_relocation'], 'NOT_VERIFIED')
        joined = '\n'.join(delivery_receipt.unsupported_claims(receipt))
        self.assertIn('requirement statuses are caller-declared', joined)

    # -- (b) the receipt survives a restart and reads back identical --------- #

    def test_receipt_survives_a_restart_and_reads_back_byte_identical(self):
        executed, created = self.deliver()
        emitted = created['bundle']['receipt']
        asset_id, version_id = created['bundle']['id'], created['bundle']['version_id']
        reopened = ProjectService(self.root)
        read_back = NativeDelivery(reopened).receipt(self.project, asset_id, version_id)
        self.assertEqual(read_back, emitted)
        self.assertEqual(read_back['receipt_sha256'], emitted['receipt_sha256'])
        self.assertEqual(delivery_receipt.dumps(read_back), delivery_receipt.dumps(emitted))
        # The persisted row is the canonical text, not a re-derived copy of it.
        with closing(sqlite3.connect(reopened.paths.database_path(reopened.database))) as conn:
            stored = conn.execute('SELECT receipt_json, receipt_id, receipt_sha256, project_id '
                                  'FROM delivery_receipt_v1 WHERE version_id=?', (version_id,)).fetchone()
        self.assertEqual(stored[0], delivery_receipt.dumps(emitted))
        self.assertEqual((stored[1], stored[2], stored[3]),
                         (emitted['receipt_id'], emitted['receipt_sha256'], self.project))
        # Re-delivering the same attempt cannot drift the document.
        again = NativeDelivery(ProjectService(self.root)).create(self.project, executed['attempt']['job_id'])
        self.assertEqual(again['bundle']['receipt'], emitted)

    def test_readback_refuses_a_stored_receipt_someone_edited(self):
        executed, created = self.deliver()
        receipt = created['bundle']['receipt']
        database = self.service.paths.database_path(self.service.database)
        tampered = json.loads(json.dumps(receipt))
        tampered['deliverables'][0]['byte_size'] += 1
        with closing(sqlite3.connect(database)) as conn:
            conn.execute('UPDATE delivery_receipt_v1 SET receipt_json=? WHERE version_id=?',
                         (delivery_receipt.dumps(tampered), created['bundle']['version_id']))
            conn.commit()
        with self.assertRaises(ImageAssetError) as caught:
            NativeDelivery(ProjectService(self.root)).receipt(self.project, created['bundle']['id'],
                                                              created['bundle']['version_id'])
        self.assertEqual(caught.exception.code, 'DELIVERY_RECEIPT_UNVERIFIED')

    def test_readback_refuses_a_stored_digest_that_describes_different_bytes(self):
        """The stored column is compared, not trusted: the parser cannot see it.

        ``delivery_receipt.loads`` re-verifies the document against the ``receipt_sha256`` *inside
        it*, so editing ``receipt_json`` is stopped by the parser before the comparison below is
        even reached -- that is the case just above. The column is a second copy of the same fact,
        written so a query can find a receipt by digest. A row whose column was rewritten to
        another delivery's digest still hands back a perfectly self-consistent document, and only
        ``_load``'s own comparison refuses it, so that line had to be exercised on its own.
        """
        executed, created = self.deliver()
        receipt = created['bundle']['receipt']
        asset_id, version_id = created['bundle']['id'], created['bundle']['version_id']
        database = self.service.paths.database_path(self.service.database)
        # Re-seal an edited copy so the forged column value is a genuine digest of a genuine
        # document: "this row now describes a different delivery", not "someone typed rubbish".
        edited = json.loads(json.dumps(receipt))
        edited['deliverables'][0]['byte_size'] += 1
        forged = delivery_receipt.rebuild_identity(edited)['receipt_sha256']
        self.assertNotEqual(forged, receipt['receipt_sha256'])
        with closing(sqlite3.connect(database)) as conn:
            conn.execute('UPDATE delivery_receipt_v1 SET receipt_sha256=? WHERE version_id=?',
                         (forged, version_id))
            conn.commit()
            stored = conn.execute('SELECT receipt_json FROM delivery_receipt_v1 '
                                  'WHERE version_id=?', (version_id,)).fetchone()[0]
        # The bytes the parser reads are untouched, and it accepts them -- which is the point:
        # nothing inside the document reports the mismatch, so a reader that only parsed would
        # answer with a receipt whose own digest row contradicts it.
        self.assertEqual(delivery_receipt.loads(stored), receipt)
        delivery = NativeDelivery(ProjectService(self.root))
        for name, read in (('receipt', delivery.receipt), ('readback', delivery.readback)):
            with self.subTest(reader=name):
                with self.assertRaises(ImageAssetError) as caught:
                    read(self.project, asset_id, version_id)
                self.assertEqual(caught.exception.status, 409)
                self.assertEqual(caught.exception.code, 'DELIVERY_RECEIPT_UNVERIFIED')

    # -- (c) no host readback may be claimed --------------------------------- #


    def test_a_delivery_the_host_never_reopened_claims_no_readback_and_is_not_a_pass(self):
        executed, created = self.deliver()
        receipt = created['bundle']['receipt']
        for entry in receipt['deliverables']:
            self.assertIsNone(entry['host_readback'],
                              f"{entry['deliverable_id']}: the delivery records a host readback "
                              "this product never performed")
            self.assertIsNone(entry['readback_matches_artifact'])
        self.assertEqual(receipt['axes'], {'delivery': 'PARTIAL'})
        claims = '\n'.join(delivery_receipt.unsupported_claims(receipt))
        for entry in receipt['deliverables']:
            self.assertIn(f"deliverable {entry['deliverable_id']!r}: no host readback was recorded",
                          claims)
        self.assertIn('axes.delivery is PARTIAL', claims)
        # The same body stamped PASS is refused: the document cannot be turned into an
        # acceptance by editing the one word that says it passed.
        overclaim = delivery_receipt.rebuild_identity({**receipt, 'axes': {'delivery': 'PASS'}})
        with self.assertRaises(InteropError) as caught:
            delivery_receipt.verify_receipt(overclaim)
        self.assertIn('must not claim PASS', str(caught.exception))

    def test_the_emitter_refuses_to_record_a_readback_it_was_not_given(self):
        executed, created = self.deliver()
        receipt = created['bundle']['receipt']
        name = receipt['deliverables'][0]['deliverable_id']
        fabricated = delivery_receipt.receipt_for_bundle(
            json.loads(json.dumps(self.bundle_manifest(created))), job_id=receipt['job_id'],
            created_at=receipt['created_at'],
            receipted_at=self.ended_at(executed),
            rollback=receipt['deliverables'][0]['rollback'], bundle_bytes_verified=True,
            host_readback={name: dict(host_id='photoshop', host_version='26.7.0',
                                      readback_sha256=receipt['deliverables'][0]['artifact_sha256'],
                                      opened_at=receipt['created_at'])})
        self.assertEqual(fabricated['axes'], {'delivery': 'PARTIAL'})
        self.assertIsNone(fabricated['deliverables'][1]['host_readback'])

    def bundle_manifest(self, created):
        archive = self.archive_of(created['bundle']['id'], created['bundle']['version_id'])
        return json.loads(archive.read('bundle-manifest.json'))

    # -- (d) a receipt is only readable by the project it belongs to --------- #

    def test_no_readback_path_can_report_another_projects_receipt(self):
        executed, created = self.deliver()
        asset_id, version_id = created['bundle']['id'], created['bundle']['version_id']
        other = self.service.create_project('other practice')['id']
        delivery = NativeDelivery(ProjectService(self.root))
        with self.assertRaises(ImageAssetError) as caught:
            delivery.receipt(other, asset_id, version_id)
        self.assertEqual(caught.exception.code, 'DELIVERY_RECEIPT_NOT_FOUND')
        # Asking another project for this job creates no delivery and no receipt.
        with self.assertRaises(ImageAssetError):
            delivery.create(other, executed['attempt']['job_id'])
        database = self.service.paths.database_path(self.service.database)
        with closing(sqlite3.connect(database)) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM delivery_receipt_v1 WHERE project_id=?',
                                          (other,)).fetchone()[0], 0)
            # A row that lies about its project must not become readable either: the
            # asset ledger, not the row's self-declared column, owns ownership.
            conn.execute('UPDATE delivery_receipt_v1 SET project_id=? WHERE version_id=?', (other, version_id))
            conn.commit()
        fresh = NativeDelivery(ProjectService(self.root))
        for project in (other, self.project):
            with self.subTest(project=project):
                with self.assertRaises(ImageAssetError) as caught:
                    fresh.receipt(project, asset_id, version_id)
                self.assertEqual(caught.exception.code, 'DELIVERY_RECEIPT_NOT_FOUND')

    def test_cli_reads_the_receipt_back_with_its_limitations_attached(self):
        executed, created = self.deliver()
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'), PYTHONDONTWRITEBYTECODE='1')
        command = [sys.executable, '-B', '-X', 'utf8', '-m', 'design_lab', '--project', str(self.root),
                   'delivery-receipt', '--project-id', self.project, '--bundle', created['bundle']['id'],
                   '--version', created['bundle']['version_id']]
        child = subprocess.run(command, cwd=str(self.root), env=env, capture_output=True,
                               text=True, encoding='utf-8', timeout=60)
        self.assertEqual(child.returncode, 0, child.stderr)
        data = json.loads(child.stdout)
        self.assertEqual(data['status'], 'DELIVERY_RECEIPT')
        self.assertEqual(data['receipt']['receipt_sha256'], created['bundle']['receipt']['receipt_sha256'])
        self.assertEqual(data['verification']['axes'], {'delivery': 'PARTIAL'})
        self.assertEqual(data['verification']['readback_count'], 0)
        self.assertIn('no host readback was recorded', '\n'.join(data['verification']['unsupported_claims']))
        wrong = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-m', 'design_lab',
                                '--project', str(self.root), 'delivery-receipt',
                                '--project-id', '0' * 32, '--bundle', created['bundle']['id'],
                                '--version', created['bundle']['version_id']],
                               cwd=str(self.root), env=env, capture_output=True,
                               text=True, encoding='utf-8', timeout=60)
        self.assertEqual(wrong.returncode, 2, wrong.stderr)
        self.assertEqual(json.loads(wrong.stdout)['error'], 'PROJECT_NOT_FOUND')

    # -- (h) the read-back resolves the rollback reference the receipt promises -- #
    def test_the_readback_envelope_carries_the_document_and_resolves_its_rollback(self):
        """The envelope must contain the stored document unchanged, and answer the promise.

        Two separate risks live here. The first is that adding a read-back field quietly
        re-derives the receipt, so ``receipt_sha256`` stops describing the bytes the client holds
        -- hence the identity and digest comparisons. The second is that the resolution always
        reports success because nothing was ever looked up -- hence the real version number and
        the deliberate missing-version case at the end, run over the same connection.
        """
        from design_lab import native_delivery as nd
        from design_lab.interop import resource_registry

        _executed, created = self.deliver()
        bundle = created['bundle']
        delivery = NativeDelivery(self.service)
        document = delivery.receipt(self.project, bundle['id'], bundle['version_id'])
        envelope = delivery.readback(self.project, bundle['id'], bundle['version_id'])

        self.assertEqual(envelope['schemaVersion'], nd.READBACK_SCHEMA_VERSION)
        self.assertEqual(envelope['receipt'], document,
                         'the envelope must answer with the stored document, not a rebuilt one')
        self.assertEqual(envelope['receipt']['receipt_sha256'], document['receipt_sha256'])
        self.assertEqual(envelope['rollback_state'], 'ALL_RESOLVED')
        proofs = envelope['rollback_proofs']
        self.assertEqual(len(proofs), len(document['deliverables']))
        for proof, entry in zip(proofs, document['deliverables']):
            self.assertEqual(proof['state'], 'RESOLVED', proof)
            self.assertEqual(proof['backup_ref'], entry['rollback']['backup_ref'])
            self.assertEqual(proof['deliverable_id'], entry['deliverable_id'])
            self.assertEqual(proof['source_state'], 'ACTIVE')
            self.assertIsInstance(proof['version_no'], int)
            self.assertIn('ACTIVE', proof['reason'])
        for word in nd.ROLLBACK_STATES + nd.ROLLBACK_SUMMARIES:
            self.assertIn(word, envelope['state_meaning'])
        self.assertEqual(envelope['rollback_state_vocabulary'], list(nd.ROLLBACK_SUMMARIES))

        # The payload the route sends is what its bound schema accepts, $ref included.
        schema = load_schema(ROOT / 'design-lab/schemas/delivery-receipt-readback.schema.json')
        inner = load_schema(delivery_receipt.SCHEMA_PATH)
        registry = resource_registry({schema['$id']: schema, inner['$id']: inner})
        self.assertEqual(schema_errors(schema, envelope, registry=registry), [])
        self.assertEqual(schema_errors(inner, envelope['receipt']), [])

        # A reference to a version this ledger does not hold is reported as missing, on the same
        # connection: without this the test above only proves the happy path returns something.
        absent = dict(deliverables=[dict(deliverable_id='ghost.png',
                                       rollback=dict(backup_ref=f'asset:{bundle["id"]}/version:'
                                                                 f'v-{"0" * 64}',
                                                     procedure='p'))])
        from contextlib import closing as _closing
        import sqlite3 as _sqlite3
        database = self.service.paths.database_path(self.service.database)
        with _closing(_sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as conn:
            summary, produced = nd.rollback_proofs(conn, absent, self.project)
        self.assertEqual(summary, 'NONE_RESOLVED')
        self.assertEqual(produced[0]['state'], 'SOURCE_MISSING')
        self.assertIsNone(produced[0]['version_no'])


class RefusesRatherThanInventsTest(unittest.TestCase):
    """``receipt_for_bundle`` may only restate what the bundle manifest records."""

    def manifest(self, **over):
        metadata = dict(native_attempt_id='att-' + 'a' * 32, source_asset_id='native-' + 'b' * 64,
                        host='photoshop', host_version='26.7.0', job_sha256='c' * 64,
                        rights='NOT_REVIEWED', quality='NOT_REVIEWED', link_relocation='NOT_VERIFIED',
                        font_inventory='REQUESTED_ONLY', requested_fonts=[],
                        font_observation='NOT_COLLECTED', font_rights='NOT_REVIEWED',
                        native_receipt_binding={}, input_assets=[])
        files = {'native.psd': dict(sha256='d' * 64, byte_size=4096, role='primary'),
                 'preview.png': dict(sha256='e' * 64, byte_size=1024, role='preview')}
        manifest = dict(schemaVersion='design-lab/asset-bundle/v1', primary='native.psd',
                        files=files, metadata=metadata)
        manifest.update(over)
        return manifest

    def call(self, manifest, **over):
        arguments = dict(job_id='job-1', created_at='2026-10-08T09:00:00+00:00',
                         receipted_at='2026-10-08T08:59:00+00:00',
                         rollback=dict(backup_ref='asset:native-x/version:v-x',
                                       procedure='drop the appended bundle version'),
                         bundle_bytes_verified=True)
        arguments.update(over)
        return delivery_receipt.receipt_for_bundle(manifest, **arguments)

    def test_a_receipted_bundle_projects_into_a_partial_document(self):
        receipt = self.call(self.manifest())
        self.assertEqual(receipt['axes'], {'delivery': 'PARTIAL'})
        self.assertEqual([entry['deliverable_id'] for entry in receipt['deliverables']],
                         ['native.psd', 'preview.png'])

    def test_unrecorded_facts_stop_the_receipt_instead_of_being_guessed(self):
        cases = {}
        approved = self.manifest()
        approved['metadata']['rights'] = 'APPROVED'
        cases['a rights state the bundle never records'] = (approved, {})
        foreign_host = self.manifest()
        foreign_host['metadata']['host'] = 'gimp'
        cases['a host this product cannot name as producer'] = (foreign_host, {})
        unknown_kind = self.manifest()
        unknown_kind['files']['preview.webp'] = dict(sha256='f' * 64, byte_size=8, role='preview')
        cases['a member suffix that maps to no asset kind'] = (unknown_kind, {})
        phantom_input = self.manifest()
        phantom_input['metadata']['input_assets'] = [dict(id='input', member='inputs/0000.png')]
        cases['an input the archive does not carry'] = (phantom_input, {})
        no_host_version = self.manifest()
        no_host_version['metadata']['host_version'] = ''
        cases['a host version the adapter never reported'] = (no_host_version, {})
        for label, (manifest, extra) in cases.items():
            with self.subTest(label):
                with self.assertRaises(InteropError):
                    self.call(manifest, **extra)
        without_time = self.manifest()
        for label, extra in (('no persisted publication time', {'created_at': None}),
                             ('no persisted host readback time', {'receipted_at': None}),
                             ('no job to bind', {'job_id': ''})):
            with self.subTest(label):
                with self.assertRaises(InteropError):
                    self.call(without_time, **extra)

    def test_inputs_ship_as_provenance_never_as_deliverables(self):
        manifest = self.manifest()
        member = 'inputs/0000.png'
        manifest['files'][member] = dict(sha256='e' * 64, byte_size=1024, role='input')
        manifest['metadata']['input_assets'] = [dict(id='input', member=member)]
        receipt = self.call(manifest)
        self.assertNotIn(member, [entry['deliverable_id'] for entry in receipt['deliverables']])
        self.assertEqual(self.call(manifest), receipt)
        digest = manifest_digest(build_manifest(dict(
            deliverable_id='native.psd', artifact_sha256='sha256:' + 'd' * 64, asset_kind='psd',
            producer=dict(operation_id=manifest['metadata']['native_attempt_id'],
                          provider_id='photoshop', model_id=None),
            inputs=[dict(version_id='input', sha256='sha256:' + 'e' * 64, relationship='inputTo')],
            actions=[dict(action='c2pa.created', when='2026-10-08T08:59:00+00:00',
                          software_agent='photoshop 26.7.0')],
            rights_profile=delivery_receipt.BUNDLE_RIGHTS_PROFILE,
            created_at='2026-10-08T08:59:00+00:00')))
        self.assertEqual(receipt['deliverables'][0]['provenance'], digest)

if __name__ == '__main__':
    unittest.main(verbosity=2)
