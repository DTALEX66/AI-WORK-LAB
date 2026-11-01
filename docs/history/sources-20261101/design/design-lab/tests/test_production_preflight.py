# SPDX-License-Identifier: MIT
"""Artifact preflight: measured checks, and a verdict that cannot inherit a green.

The profiles under design-lab/production/profiles/ declared pass|warning|fail long
before anything could emit them. These tests are written so the dishonest outcomes
are the ones that fail: an unmeasured check lifting the verdict to PASS, a missing
artifact passing, a digest mismatch passing, a check quietly disappearing.
"""
from __future__ import annotations

import hashlib
import json
import io
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))

from PIL import Image

from design_lab.assurance import production_preflight as pp   # noqa: E402
from design_lab.service import ProjectService                  # noqa: E402

GATE = REPO / 'design-lab' / 'scripts' / 'verify_artifact_preflight_contract.py'
ARTIFACT_SCHEMA = REPO / 'design-lab' / 'schemas' / 'artifact-preflight.schema.json'


def load_gate():
    """The gate is one implementation, used by the product path and the CLI."""
    spec = importlib.util.spec_from_file_location('verify_artifact_preflight_contract', GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_image(directory: Path, name: str, *, mode='RGB', size=(120, 90), dpi=None):
    stream = io.BytesIO()
    image = Image.new(mode, size, 'red' if mode == 'RGB' else 128)
    save = {'format': 'PNG'}
    if dpi:
        save['dpi'] = dpi
    image.save(stream, **save)
    path = directory / name
    path.write_bytes(stream.getvalue())
    return path


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))

    def _checks(self, result, check_id):
        return [item for item in result['findings'] if item['id'] == check_id]

    def _first(self, result, check_id):
        rows = self._checks(result, check_id)
        self.assertTrue(rows, f'no finding for {check_id}')
        return rows[0]['outcome']

    def test_digital_pixel_checks_are_measured_from_the_bytes(self):
        image = write_image(self.base, 'poster.png', dpi=(300, 300))
        result = pp.run_preflight([image], profile='digital')
        self.assertEqual(self._first(result, 'pixel-dimensions'), pp.PASS)
        self.assertEqual(self._checks(result, 'pixel-dimensions')[0]['measured']['width'], 120)
        self.assertEqual(self._first(result, 'color-profile'), pp.PASS)
        self.assertEqual(self._first(result, 'format'), pp.PASS)

    def test_a_print_job_still_in_rgb_is_blocked_not_warned(self):
        image = write_image(self.base, 'flyer.png', mode='RGB')
        result = pp.run_preflight([image], profile='print')
        colour = self._checks(result, 'color-mode-output-intent')[0]
        self.assertEqual(colour['outcome'], pp.FAIL)
        self.assertEqual(colour['severity'], 'blocker')
        self.assertEqual(result['verdict'], 'BLOCKED')

    def test_missing_dpi_is_reported_as_unmeasured_rather_than_zero(self):
        image = write_image(self.base, 'no-dpi.png')
        result = pp.run_preflight([image], profile='print')
        check = self._checks(result, 'resolution-effective-ppi')[0]
        self.assertEqual(check['outcome'], pp.NOT_MEASURED)
        self.assertEqual(check['measured'], {},
                         'an unmeasured check must not publish a number it did not read')
        self.assertIn('未记录 DPI', check['detail'])

    def test_an_absent_artifact_is_a_failure_not_a_silence(self):
        result = pp.run_preflight([self.base / 'never-written.png'], profile='digital')
        self.assertEqual(result['verdict'], 'BLOCKED')
        self.assertIn('不存在', self._checks(result, 'artifact-present')[0]['detail'])

    def test_a_zero_byte_artifact_cannot_pass(self):
        empty = self.base / 'empty.png'
        empty.write_bytes(b'')
        result = pp.run_preflight([empty], profile='digital')
        self.assertEqual(result['verdict'], 'BLOCKED')

    def test_links_are_checked_against_the_link_manifest(self):
        image = write_image(self.base, 'hero.png')
        other = write_image(self.base, 'logo.png')
        manifest = {'items': [{'id': 'logo', 'path': str(other),
                               'sha256': hashlib.sha256(other.read_bytes()).hexdigest()}]}
        good = pp.run_preflight([image], profile='print', link_manifest=manifest)
        self.assertEqual(self._first(good, 'missing-links'), pp.PASS)

        manifest['items'].append({'id': 'gone', 'path': str(self.base / 'gone.png')})
        broken = pp.run_preflight([image], profile='print', link_manifest=manifest)
        check = self._checks(broken, 'missing-links')[0]
        self.assertEqual(check['outcome'], pp.FAIL)
        self.assertIn('gone', check['detail'])

    def test_a_digest_that_does_not_match_the_bytes_is_a_failure(self):
        image = write_image(self.base, 'hero.png')
        other = write_image(self.base, 'logo.png')
        manifest = {'items': [{'id': 'logo', 'path': str(other), 'sha256': 'sha256:' + '0' * 64}]}
        result = pp.run_preflight([image], profile='print', link_manifest=manifest)
        self.assertIn('摘要与清单不符', self._checks(result, 'missing-links')[0]['detail'])

    def test_an_empty_link_manifest_fails_rather_than_passing_vacuously(self):
        image = write_image(self.base, 'hero.png')
        result = pp.run_preflight([image], profile='print', link_manifest={'items': []})
        self.assertEqual(self._first(result, 'missing-links'), pp.FAIL)

    def test_no_profile_can_reach_pass_while_anything_is_unmeasured(self):
        """The invariant that keeps a green honest across every shipped profile."""
        image = write_image(self.base, 'art.png', dpi=(300, 300))
        names = sorted(path.stem.replace('preflight-', '')
                       for path in pp.PROFILE_DIR.glob('preflight-*.json'))
        self.assertEqual(names, ['digital', 'print', 'video'])
        for profile in names:
            with self.subTest(profile=profile):
                result = pp.run_preflight([image], profile=profile)
                if result['counts'][pp.NOT_MEASURED]:
                    self.assertNotEqual(
                        result['verdict'], 'PASS',
                        f'{profile}: 有检查未量，结论却是 PASS')
                    if result['counts'][pp.FAIL] == 0:
                        self.assertEqual(result['verdict'], 'INCOMPLETE',
                                         '无阻塞失败时，未量项必须让结论停在 INCOMPLETE')

    def test_every_declared_check_appears_and_nothing_undeclared_is_invented(self):
        """A check dropped from the output is how a profile goes green by omission."""
        image = write_image(self.base, 'art.png')
        for name in ('print', 'digital', 'video'):
            declared = {check['id'] for check in pp.load_profile(name)['required_checks']}
            emitted = {item['id'] for item in pp.run_preflight([image], profile=name)['findings']}
            self.assertEqual(declared - emitted, set(), f'{name} dropped declared checks')
            self.assertEqual(emitted - declared - {'artifact-present'}, set(),
                             f'{name} reported checks its profile never declared')

    def test_every_finding_states_the_criterion_it_was_judged_against(self):
        image = write_image(self.base, 'art.png')
        for name in ('print', 'digital', 'video'):
            for item in pp.run_preflight([image], profile=name)['findings']:
                self.assertTrue(str(item.get('criterion', '')).strip(),
                                f'{name}/{item["id"]} gives a verdict with no stated criterion')

    def test_a_container_this_build_cannot_open_never_becomes_a_pass(self):
        fake = self.base / 'layout.psd'
        fake.write_bytes(b'not a real psd header')
        result = pp.run_preflight([fake], profile='print')
        self.assertTrue(any(item['outcome'] == pp.NOT_MEASURED
                            for item in self._checks(result, 'pixel-dimensions')),
                        'an unreadable container must not be reported as measured')
        self.assertNotEqual(result['verdict'], 'PASS')

    def test_the_verdict_and_outcome_vocabulary_is_closed(self):
        image = write_image(self.base, 'art.png')
        result = pp.run_preflight([image], profile='print')
        self.assertIn(result['verdict'], pp.VERDICTS)
        for item in result['findings']:
            self.assertIn(item['outcome'], (pp.PASS, pp.WARNING, pp.FAIL,
                                            pp.NOT_MEASURED, pp.NOT_APPLICABLE))


class ArchivePreflightTests(unittest.TestCase):
    """The route-facing entry: a registered delivery archive, resolved by id."""

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))

    def _archive(self, *, tamper=False, slip=False):
        import zipfile
        preview = write_image(self.base, 'preview.png', dpi=(300, 300))
        archive = self.base / 'delivery.zip'
        files = {'preview.png': {'sha256': hashlib.sha256(preview.read_bytes()).hexdigest()}}
        if tamper:
            files['preview.png']['sha256'] = '0' * 64
        with zipfile.ZipFile(archive, 'w') as out:
            out.writestr('preview.png', preview.read_bytes())
            if slip:
                out.writestr('../escaped.png', b'evil')
            out.writestr('bundle-manifest.json',
                         json.dumps({'files': files}, ensure_ascii=False))
        return archive, hashlib.sha256(archive.read_bytes()).hexdigest()

    def test_a_registered_archive_is_measured_and_says_what_it_could_not_measure(self):
        archive, digest = self._archive()
        result = pp.preflight_archive(archive, profile='print', expected_sha256=digest)
        self.assertEqual(result['archive']['sha256'], digest)
        links = [item for item in result['findings'] if item['id'] == 'missing-links']
        self.assertTrue(links, 'the print profile declares missing-links; it must be reported')
        self.assertEqual(links[0]['outcome'], pp.PASS,
                         f'link check reported: {links[0]["detail"]}')
        self.assertNotEqual(result['verdict'], pp.PASS,
                            'every shipped profile still carries checks this build cannot measure')

    def test_the_delivery_bill_is_reported_as_refused_rather_than_omitted(self):
        """bom.schema.json is a declared contract, so an archive has to answer for it."""
        archive, digest = self._archive()
        result = pp.preflight_archive(archive, profile='digital', expected_sha256=digest)
        bill = [item for item in result['findings'] if item['id'] == 'delivery-bom']
        self.assertEqual(1, len(bill), 'the archive path must state the BOM position')
        self.assertEqual(pp.NOT_MEASURED, bill[0]['outcome'],
                         'a bill nothing can write cannot be reported as written')
        self.assertEqual('DELIVERY_BOM_INCOMPLETE', bill[0]['measured']['status'])
        for field in ('handoff', 'repo_tree_sha', 'tool_version', 'generated_at'):
            self.assertIn(field, bill[0]['measured']['missing'])
        self.assertIn('无法写成', bill[0]['detail'])

    def test_every_emitted_finding_is_counted_in_the_aggregate(self):
        """`counts` must describe the findings the page renders, including the inserted two.

        Before this was checked, archive-digest and delivery-bom were appended after the recount, so
        a NOT_MEASURED bill could show on the page while the aggregate still reported the old number
        -- a decorative counter, which is the failure mode the shipped profile tests refuse on
        purpose.
        """
        archive, digest = self._archive()
        result = pp.preflight_archive(archive, profile='print', expected_sha256=digest)
        for outcome in (pp.PASS, pp.WARNING, pp.FAIL, pp.NOT_MEASURED, pp.NOT_APPLICABLE):
            self.assertEqual(
                result['counts'][outcome],
                sum(1 for item in result['findings'] if item['outcome'] == outcome),
                f'counts[{outcome}] disagrees with the findings')

    def test_a_digital_archive_reports_only_what_the_digital_profile_declares(self):
        # `missing-links` is declared by print only. Reporting it under digital would
        # be inventing a check; dropping it under print would be hiding one.
        archive, digest = self._archive()
        result = pp.preflight_archive(archive, profile='digital', expected_sha256=digest)
        declared = {check['id'] for check in pp.load_profile('digital')['required_checks']}
        self.assertNotIn('missing-links', declared)
        self.assertNotIn('missing-links',
                         {item['id'] for item in result['findings']},
                         'reporting an undeclared check is as wrong as dropping a declared one')

    def test_a_member_whose_bytes_differ_from_the_manifest_is_a_link_failure(self):
        archive, digest = self._archive(tamper=True)
        result = pp.preflight_archive(archive, profile='print', expected_sha256=digest)
        links = [item for item in result['findings'] if item['id'] == 'missing-links']
        self.assertEqual(links[0]['outcome'], pp.FAIL,
                         'the manifest and the bytes disagree, and that must be a finding')
        self.assertIn('摘要与清单不符', links[0]['detail'])
        self.assertEqual(result['verdict'], 'BLOCKED')

    def test_an_archive_that_does_not_match_its_registration_is_refused(self):
        archive, digest = self._archive()
        with self.assertRaisesRegex(pp.PreflightError, '摘要与登记不符'):
            pp.preflight_archive(archive, profile='digital',
                                 expected_sha256='sha256:' + '9' * 64)

    def test_a_zip_slip_member_is_refused_before_anything_is_written(self):
        archive, digest = self._archive(slip=True)
        with self.assertRaisesRegex(pp.PreflightError, '越界'):
            pp.preflight_archive(archive, profile='digital', expected_sha256=digest)

    def test_an_unregistered_bundle_is_reported_as_such(self):
        from design_lab.service import ProjectService
        import os
        os.environ.pop('PROJECT_LOCAL_ROOT', None)
        project = self.base / 'project'
        project.mkdir()
        (project / 'AGENTS.md').write_text('# preflight fixture', encoding='utf-8')
        service = ProjectService(project)
        project_id = service.create_project('Preflight Probe')['id']
        with self.assertRaises(pp.PreflightError) as caught:
            pp.preflight_bundle(service, project_id, 'bundle-missing', profile='digital')
        self.assertIn('bundle-missing', str(caught.exception))


class RegisteredArtifactScopeTests(unittest.TestCase):
    """Which bytes a registered delivery verdict is actually about.

    `preflight_bundle` used to run `fetchone()` over a join with no artifact ordering,
    so a version that registers a preview beside its deliverable could be certified on
    whichever row SQLite happened to yield first, with nothing saying the other bytes
    were never opened. These cases hold the selection to the deliverable and require
    the rest to be reported as unmeasured.
    """

    def setUp(self):
        import os
        os.environ.pop('PROJECT_LOCAL_ROOT', None)
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        self.project = self.base / 'project'
        self.project.mkdir()
        (self.project / 'AGENTS.md').write_text('# preflight fixture', encoding='utf-8')
        self.service = ProjectService(self.project)
        self.project_id = self.service.create_project('Artifact Scope')['id']

    def _publish(self, archive: Path, *, asset_id, artifact_name='deliverable.zip'):
        from contextlib import closing
        from design_lab.runtime import asset_store as assets
        store = self.service.paths.category_dir('projects', self.project_id, 'assets')
        digest = 'sha256:' + hashlib.sha256(archive.read_bytes()).hexdigest()
        with closing(assets.connect(self.service.database,
                                    project_root=self.service.paths.project_root)) as conn:
            if conn.execute('SELECT 1 FROM asset WHERE asset_id = ?', (asset_id,)).fetchone() is None:
                conn.execute('INSERT INTO asset VALUES (?, ?, "other", ?)',
                             (asset_id, self.project_id, '2026-10-08T00:00:00Z'))
            conn.commit()
            self.assertTrue(assets.acquire_writer(conn, f'asset:{asset_id}', 'attempt-pf'))
            generation = assets.writer_token(conn, f'asset:{asset_id}', 'attempt-pf')
            version_id = assets.publish_version(
                conn, asset_id, archive, store_root=store, artifact_name=artifact_name,
                expected_sha256=digest, holder_attempt_id='attempt-pf', generation=generation)
            assets.release_writer(conn, f'asset:{asset_id}', 'attempt-pf', generation=generation)
        return version_id

    def _add_sibling_artifact(self, version_id, sibling: Path, *, role='preview'):
        """Register a second file against the same version, as `create_version` may."""
        from contextlib import closing
        from design_lab.runtime import asset_store as assets
        with closing(assets.connect(self.service.database,
                                    project_root=self.service.paths.project_root)) as conn:
            conn.execute('INSERT INTO artifact (artifact_id, version_id, path, sha256,'
                         ' byte_size, role) VALUES (?,?,?,?,?,?)',
                         ('a-' + sibling.stem, version_id, str(sibling),
                          'sha256:' + hashlib.sha256(sibling.read_bytes()).hexdigest(),
                          sibling.stat().st_size, role))
            conn.commit()

    def _scope(self, result):
        return [item for item in result['findings'] if item['id'] == 'artifact-scope']

    def test_the_deliverable_is_what_gets_measured_even_when_a_sibling_is_listed_first(self):
        deliverable = self._archive_named('deliverable.zip')
        version_id = self._publish(deliverable, asset_id='bundle-scope-1')
        # Register a sibling BEFORE the query runs; role ordering, not row order, decides.
        self._add_sibling_artifact(version_id, self._archive_named('preview-sheet.zip'))
        result = pp.preflight_bundle(self.service, self.project_id, 'bundle-scope-1',
                                     profile='digital')
        self.assertEqual(result['archive']['name'], 'deliverable.zip',
                         'the verdict must be about the deliverable, not an arbitrary row')

    def test_bytes_registered_but_not_measured_are_reported_as_unmeasured(self):
        deliverable = self._archive_named('deliverable.zip')
        version_id = self._publish(deliverable, asset_id='bundle-scope-2')
        baseline = pp.preflight_bundle(self.service, self.project_id, 'bundle-scope-2',
                                       profile='digital')
        self.assertEqual(self._scope(baseline), [], 'one registered artifact leaves nothing unmeasured')

        self._add_sibling_artifact(version_id, self._archive_named('preview-sheet.zip'))
        after = pp.preflight_bundle(self.service, self.project_id, 'bundle-scope-2',
                                    profile='digital')
        scope = self._scope(after)
        self.assertEqual(len(scope), 1, 'the extra bytes have to be named, not silently ignored')
        self.assertEqual(scope[0]['outcome'], pp.NOT_MEASURED)
        self.assertEqual(scope[0]['measured']['unmeasured'], ['preview-sheet.zip'])
        self.assertEqual(scope[0]['measured']['measured'], ['deliverable.zip'])
        self.assertEqual(after['counts'][pp.NOT_MEASURED], baseline['counts'][pp.NOT_MEASURED] + 1,
                         'the count must move with the finding, or the aggregate is decorative')
        self.assertNotEqual(after['verdict'], pp.PASS)

    def test_a_newer_revision_is_preflighted_instead_of_the_one_it_replaced(self):
        old = self._archive_named('deliverable.zip', seed=b'first shipment')
        self._publish(old, asset_id='bundle-scope-3')
        newer = self._archive_named('deliverable.zip', seed=b'revised shipment')
        self._publish(newer, asset_id='bundle-scope-3')
        result = pp.preflight_bundle(self.service, self.project_id, 'bundle-scope-3',
                                     profile='digital')
        self.assertEqual(result['archive']['sha256'],
                         hashlib.sha256(newer.read_bytes()).hexdigest(),
                         'preflighting a revision nobody will deliver is a green about nothing')

    def _register(self, asset_id, rows):
        """Register one ACTIVE version with the given (path, role) artifacts, in order.

        `create_version` accepts a list of artifacts, so the preview really can be
        registered before the deliverable -- which is the case an unordered
        `fetchone()` used to certify the wrong bytes for.
        """
        from contextlib import closing
        from design_lab.runtime import asset_store as assets
        with closing(assets.connect(self.service.database,
                                    project_root=self.service.paths.project_root)) as conn:
            if conn.execute('SELECT 1 FROM asset WHERE asset_id = ?', (asset_id,)).fetchone() is None:
                conn.execute('INSERT INTO asset VALUES (?, ?, "other", ?)',
                             (asset_id, self.project_id, '2026-10-08T00:00:00Z'))
            conn.commit()
            artifacts = [(str(path), 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest(),
                          path.stat().st_size, role) for path, role in rows]
            content = next((item[1] for item in artifacts if item[3] == 'deliverable'),
                           artifacts[0][1])
            return assets.record_version(conn, asset_id, content, state='ACTIVE',
                                         artifacts=artifacts)

    def test_a_preview_registered_before_the_deliverable_does_not_become_the_verdict(self):
        deliverable = self._archive_named('deliverable.zip')
        preview = self._archive_named('preview-sheet.zip', seed=b'preview only')
        self._register('bundle-scope-0', [(preview, 'preview'), (deliverable, 'deliverable')])
        result = pp.preflight_bundle(self.service, self.project_id, 'bundle-scope-0',
                                     profile='digital')
        self.assertEqual(result['archive']['name'], 'deliverable.zip',
                         'the row that came first in the table is not the shipped artifact')
        self.assertEqual(result['archive']['sha256'],
                         hashlib.sha256(deliverable.read_bytes()).hexdigest())
        scope = self._scope(result)
        self.assertEqual(len(scope), 1)
        self.assertEqual(scope[0]['measured']['unmeasured'], ['preview-sheet.zip'])
        self.assertEqual(scope[0]['measured']['measured'], ['deliverable.zip'])

    def _archive_named(self, name, *, seed=None):
        """A real delivery archive: one member plus a manifest that matches its bytes."""
        import zipfile
        work = self.base / f'build-{name}-{len(seed or b"")}-{seed is not None}'
        work.mkdir(exist_ok=True)
        image = write_image(work, 'art.png', dpi=(300, 300))
        if seed is not None:
            # Different bytes -> a different digest, so two revisions stay distinguishable.
            image = work / 'revised.png'
            image.write_bytes((work / 'art.png').read_bytes() + seed)
        archive = work / name
        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        with zipfile.ZipFile(archive, 'w') as out:
            out.writestr('art.png', image.read_bytes())
            out.writestr('bundle-manifest.json',
                         json.dumps({'files': {'art.png': {'sha256': digest}}}, ensure_ascii=False))
        return archive


class PayloadContractGateTests(unittest.TestCase):
    """The emitted payload and its schema are held against each other, both ways.

    A 2026-10-08 audit reported that this payload's `verdict` disagreed with
    `schemas/preflight.schema.json`, which requires `status`. Reading the files, that schema
    is bound to the PROFILE documents (const `design-lab/preflight/v2`, requiring
    `preflight_id` + `required_checks`) and never required a top-level `status`; this payload
    declares its own version and has a schema of its own
    (`schemas/artifact-preflight.schema.json`). The false part is settled by reading; the
    true gap was that NOTHING validated this payload at all -- the only contract surface for
    it was a TypeScript interface in the page. These tests keep that gap shut, in the product
    test path, not only in a script someone has to remember to run.

    The weakened documents here are copies held in memory; no shipped file is edited.
    """

    @classmethod
    def setUpClass(cls):
        cls.gate = load_gate()
        cls.binding = cls.gate.BINDINGS[0]
        cls.real_cases = cls.gate.build_real_payloads()
        cls.schema = json.loads(ARTIFACT_SCHEMA.read_text(encoding='utf-8'))

    def _cases(self, mutate):
        """Re-run the real emitter and mutate the resulting COPY, never the product."""
        cases = json.loads(json.dumps(self.gate.build_real_payloads()))
        return [(label, mutate(payload)) for label, payload in cases]

    def _errors(self, schema=None, cases=None, emitter_text=None):
        return self.gate.check_binding(
            self.binding,
            cases=self.real_cases if cases is None else cases,
            schema_doc=schema,
            emitter_text=(self.binding['emitter'].read_text(encoding='utf-8')
                          if emitter_text is None else emitter_text))[0]

    def test_the_real_payload_satisfies_its_schema(self):
        errors = self._errors()
        self.assertEqual(errors, [], 'the shipped emitter and the shipped schema disagree:\n'
                         + '\n'.join(errors))

    def test_the_gate_itself_passes_end_to_end(self):
        errors, notes = self.gate.run()
        self.assertEqual(errors, [], '\n'.join(errors))
        self.assertTrue(notes, 'the gate reported nothing compared')

    def test_the_emitter_still_declares_the_version_the_schema_binds(self):
        const = self.schema['properties']['schemaVersion']['const']
        source = self.binding['emitter'].read_text(encoding='utf-8')
        self.assertIn(f"'{const}'", source,
                      'the schema binds a schemaVersion the emitter no longer produces')
        self.assertEqual(pp.run_preflight([], profile='digital')['schemaVersion'], const)

    def test_a_field_the_schema_requires_but_the_emitter_dropped_is_red(self):
        weakened = json.loads(json.dumps(self.schema))
        weakened['required'].append('status')      # the contract the audit believed existed
        errors = self._errors(schema=weakened)
        red = [e for e in errors if 'MISSING_FROM_EMITTER' in e]
        self.assertEqual(len(red), 2, f'one per real case, got {red}')
        for error in red:
            self.assertIn("'status'", error)

    def test_a_field_the_emitter_added_and_the_schema_forbids_is_red(self):
        def add_ghost(payload):
            payload['verdict_confidence'] = 0.9
            return payload
        errors = self._errors(cases=self._cases(add_ghost))
        red = [e for e in errors if 'UNDECLARED_BY_SCHEMA' in e]
        self.assertEqual(len(red), 2, f'one per real case, got {red}')
        for error in red:
            self.assertIn('verdict_confidence', error)

    def test_renaming_verdict_to_status_is_red_in_both_directions_at_once(self):
        """The exact mutation the audit's proposed "fix" would have made.

        Renaming the field the page reads is not a fix: the schema still demands `verdict`
        and the closed schema still forbids `status`, so the drift must be named twice.
        """
        def rename(payload):
            payload['status'] = payload.pop('verdict')
            return payload
        errors = self._errors(cases=self._cases(rename))
        missing = [e for e in errors if 'MISSING_FROM_EMITTER' in e and "'verdict'" in e]
        extra = [e for e in errors if 'UNDECLARED_BY_SCHEMA' in e and 'status' in e]
        self.assertEqual(len(missing), 2, f'`verdict` must still be required: {missing}')
        self.assertEqual(len(extra), 2, f'`status` must still be undeclared: {extra}')

    def test_nested_drift_is_red_too(self):
        """`findings[].criterion` is what the column renders; dropping it is the real risk."""
        def drop_criterion(payload):
            for finding in payload['findings']:
                finding.pop('criterion')
            return payload
        errors = self._errors(cases=self._cases(drop_criterion))
        red = [e for e in errors if 'MISSING_FROM_EMITTER' in e and 'criterion' in e]
        self.assertTrue(red, 'a nested field must not sail through')
        # One finding per declared check, in each case: the count is the payload's, but every
        # case has to be convicted, not just the first.
        convicted = {label for label, _ in self.real_cases
                     if any(label in error and 'criterion' in error for error in red)}
        self.assertEqual(convicted, {label for label, _ in self.real_cases},
                         f'a real case escaped the nested check: {convicted}')

    def test_a_vocabulary_change_is_red(self):
        """An outcome or verdict outside the declared enum is a contract break, not a colour."""
        def new_verdict(payload):
            payload['verdict'] = 'PARTIAL'
            return payload
        errors = self._errors(cases=self._cases(new_verdict))
        self.assertTrue(any('SCHEMA_VIOLATION' in e and 'PARTIAL' in e for e in errors),
                        f'an invented verdict must be named: {errors}')

    def test_nothing_to_compare_is_never_a_pass(self):
        empty_cases = self.gate.check_binding(self.binding, cases=[])
        self.assertTrue(any('NOTHING_TO_COMPARE' in e for e in empty_cases[0]), empty_cases[0])
        self.assertTrue(any('NOTHING_TO_COMPARE' in e
                            for e in self.gate.run(bindings=[])[0]),
                        'a gate with no binding cannot report a pass')
        # A schema that declares no fields would compare nothing against any payload.
        open_schema = {'$schema': 'https://json-schema.org/draft/2020-12/schema',
                       'type': 'object'}
        errors = self.gate.check_binding(self.binding, cases=self.real_cases,
                                         schema_doc=open_schema)[0]
        self.assertTrue(any('NOTHING_TO_COMPARE' in e for e in errors),
                        f'an empty schema must not read as coverage: {errors}')

    def test_the_profile_schema_is_not_the_artifact_report_binding(self):
        """Recorded so the two contracts cannot be quietly merged again.

        `schemas/preflight.schema.json` binds the profile documents; it requires fields no
        report emits and forbids every field a report does emit. Asserting that here is what
        makes a future "just align them" edit expensive.
        """
        import jsonschema
        profile_schema = json.loads((REPO / 'design-lab' / 'schemas' / 'preflight.schema.json')
                                    .read_text(encoding='utf-8'))
        self.assertEqual(profile_schema['properties']['schemaVersion']['const'],
                         'design-lab/preflight/v2')
        self.assertNotIn('verdict', profile_schema['properties'])
        self.assertNotIn('status', profile_schema['required'],
                         'the audit read a top-level `status` into this schema; it has none')
        for label, payload in self.real_cases:
            errors = list(jsonschema.Draft202012Validator(profile_schema)
                          .iter_errors(payload))
            self.assertTrue(errors, f'{label} is not a profile document and must not validate '
                                    'against the profile schema')
            messages = ' | '.join(error.message for error in errors)
            for field in ('preflight_id', 'required_checks'):
                self.assertIn(f"'{field}' is a required property", messages,
                              f'the profile schema should reject a report for lacking its own '
                              f'{field!r}; it did not: {messages}')


if __name__ == '__main__':
    unittest.main()
