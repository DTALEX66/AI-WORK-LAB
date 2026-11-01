# SPDX-License-Identifier: MIT
"""The Quality gate made reachable: a sealed assessment is stored, read back, un-rewritable.

Everything here runs through real product machinery -- ``ProjectService`` for the owner
root, ``asset_store.publish_version`` for the bytes being judged, ``quality_store.connect``
(which is ``asset_store.connect`` plus this store's DDL) for the database, and
``design-lab/cli.py`` in a subprocess for the verb. A fixture that hand-inserted an
``asset_version`` row or a hand-built record document would let the binding checks pass
against a shape production never writes.

The suite is about the four things a quality store can lie about -- a subject that is not
this project's bytes, a digest that is not the version it judges, bytes that are no longer
there, and an automated judge filed as a human acceptance -- and about the one thing it
cannot lie about at all, because the database refuses it: rewriting or deleting a record
that was sealed.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))

from design_lab.assurance import human_jury, quality_record, quality_store   # noqa: E402
from design_lab.assurance.quality_store import QualityStoreError            # noqa: E402
from design_lab.runtime import asset_store as assets                        # noqa: E402
from design_lab.service import ProjectService                              # noqa: E402

CRITERIA = [{'criterion_id': 'anti-slop', 'weight': 0.6, 'score': 4.0, 'note': None},
            {'criterion_id': 'brand-fit', 'weight': 0.4, 'score': 3.5, 'note': None}]
ATTESTATION = 'reviewed the exported poster at 100% on the production display'


def det_finding(finding_id, digest, subject_ref, **overrides):
    """A valid deterministic-plane finding document."""
    base = {'finding_id': finding_id, 'layer_id': 'qa-deterministic',
            'check_id': 'check_anti_slop', 'subject_ref': subject_ref, 'outcome': 'PASS',
            'severity': 'INFO', 'evidence': {'artifact_sha256': digest}}
    base.update(overrides)
    return base


def judge_finding(finding_id, digest, subject_ref, **overrides):
    """A valid model-assisted-plane finding document."""
    base = {'finding_id': finding_id, 'layer_id': 'qa-model-assisted',
            'check_id': 'provider:aesthetic/laion', 'subject_ref': subject_ref,
            'outcome': 'REVIEW_REQUIRED', 'severity': 'MINOR',
            'evidence': {'artifact_sha256': digest},
            'recommendation': 'composition reads as default; escalate to the human jury'}
    base.update(overrides)
    return base


class StoreFixture(unittest.TestCase):
    """Real owner root, real publisher, real SQLite, through the product's own connect.

    Nothing here hand-inserts a state row: the point of the store is that an
    assessment attaches to bytes the project actually published, so the fixture puts
    them there with ``asset_store.publish_version``.
    """

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        (self.base / 'AGENTS.md').write_text('# quality store fixture', encoding='utf-8')
        self.service = ProjectService(self.base)
        self.project = self.service.create_project('Poster round one')['id']
        self.other = self.service.create_project('Poster round two')['id']
        self.conn = quality_store.connect(self.service.database,
                                          project_root=self.service.paths.project_root)
        assets.register_asset(self.conn, self.project, 'a1', 'psd')
        assets.register_asset(self.conn, self.other, 'a9', 'psd')
        self.version, self.digest = self._publish(b'first sealed artwork')
        self.subject = f'{quality_store.SUBJECT_PREFIX}{self.version}'
        self.other_version, self.other_digest = self._publish(
            b'second artwork, different bytes', project=self.other, asset_id='a9')

    def tearDown(self):
        self.conn.close()

    def _publish(self, payload: bytes, *, project=None, asset_id='a1'):
        """Put a real ACTIVE version into the store through the product publisher."""
        project_id = project or self.project
        source = self.base / f'in-{project_id[:6]}-{len(payload)}.psd'
        source.write_bytes(payload)
        digest = 'sha256:' + hashlib.sha256(payload).hexdigest()
        store = self.service.paths.projects_root / project_id / 'assets'
        store.mkdir(parents=True, exist_ok=True)
        resource = f'asset:{asset_id}'
        attempt = f'attempt-{asset_id}-{hashlib.sha256(payload).hexdigest()[:12]}'
        self.assertTrue(assets.acquire_writer(self.conn, resource, attempt),
                        'writer lease refused')
        generation = assets.writer_token(self.conn, resource, attempt)
        version_id = assets.publish_version(self.conn, asset_id, source, store_root=store,
                                           artifact_name='native.psd', expected_sha256=digest,
                                           holder_attempt_id=attempt, generation=generation)
        assets.release_writer(self.conn, resource, attempt, generation=generation)
        return version_id, digest

    def _claim(self, **overrides):
        """The human acceptance a record seals, built only from stated inputs."""
        inputs = {'actor': 'dtalex66', 'actor_kind': 'HUMAN', 'attestation': ATTESTATION,
                  'verdict': 'APPROVE', 'subject_ref': self.subject,
                  'artifact_sha256': self.digest, 'criteria': [dict(item) for item in CRITERIA]}
        inputs.update(overrides)
        return quality_store.human_acceptance(**inputs)

    def _verdict_doc(self, **overrides):
        """A verdict document as it arrives from outside, not through the builder.

        Built by hand on purpose: a document that came from ``human_acceptance`` would
        already have been refused by the builder's own guards, and the test would stop
        being about the store's.
        """
        document = {'schemaVersion': human_jury.REVIEW_VERSION, 'kind': 'JURY_VERDICT',
                    'jury_record_id': 'jury-1', 'subject_ref': self.subject,
                    'artifact_sha256': self.digest,
                    'juror': {'juror_id': 'dtalex66', 'kind': 'HUMAN',
                              'attestation': ATTESTATION},
                    'criteria': [dict(item) for item in CRITERIA], 'verdict': 'APPROVE',
                    'decided_at': '2026-10-08T00:00:00Z', 'supersedes': None,
                    'evidence_refs': []}
        document.update(overrides)
        return document

    def _record(self, **overrides):
        inputs = {'project_id': self.project, 'subject_ref': self.subject,
                  'artifact_sha256': self.digest,
                  'deterministic': [det_finding('f-det-1', self.digest, self.subject)]}
        inputs.update(overrides)
        return quality_store.record(self.conn, **inputs)

    def _rows(self):
        return self.conn.execute('SELECT COUNT(*) FROM quality_record').fetchone()[0]

    def _refused(self, code, *, fragment=None, **overrides):
        before = self._rows()
        with self.assertRaises(QualityStoreError) as caught:
            self._record(**overrides)
        exception = caught.exception
        self.assertEqual(exception.code, code,
                         f'refused with {exception.code!r}, not {code!r}: {exception}')
        detail = str(exception)
        self.assertTrue(detail.strip(), 'a refusal has to say why it refused')
        if fragment:
            self.assertIn(fragment, detail)
        self.assertEqual(self._rows(), before,
                         'a refused assessment must not leave a row behind')
        return detail


class QualityStoreTests(StoreFixture):
    def test_a_sealed_assessment_is_recorded_and_read_back_after_a_restart(self):
        stored = self._record(human_verdict=self._claim())
        self.assertEqual(stored['final_gate'], 'PASS')
        self.assertEqual(quality_record.final_gate_of(stored), 'PASS')
        self.conn.close()

        # A NEW service instance over the same owner root: nothing in-memory is left to
        # read from, so this is the only answer the store can give.
        restarted = ProjectService(self.base)
        with closing(quality_store.connect(restarted.database,
                                          project_root=restarted.paths.project_root)) as conn:
            records = quality_store.list_records(conn, self.project)
            self.assertEqual([item['quality_record_id'] for item in records],
                             [stored['quality_record_id']])
            self.assertEqual(records[0]['artifact_sha256'], self.digest)
            self.assertEqual(list(quality_store.current_assessments(conn, self.project)),
                             [self.subject])
            view = quality_store.summary(conn, self.project)
        self.assertEqual(view['human_acceptance'], 'ACCEPTED')
        self.assertEqual(view['gates']['PASS'], 1)
        self.assertEqual(view['human_accepted_subjects'], [self.subject])

    def test_read_back_says_what_none_of_it_proves(self):
        # Before anyone signs, the read-back has to be legible as "nobody accepted
        # this", not as an empty panel a later reader can over-read.
        self._record(automated_judge=[judge_finding('f-judge-1', self.digest, self.subject)])
        view = quality_store.summary(self.conn, self.project)
        self.assertEqual(view['record_count'], 1)
        self.assertEqual(view['human_acceptance'], 'NOT_ACCEPTED')
        self.assertEqual(view['gates']['NEEDS_HUMAN_VERDICT'], 1)
        self.assertIs(view['automated_judge_is_acceptance'], False)
        self.assertTrue(view['does_not_prove'], 'a read back with no limits stated is a lie')
        self.assertTrue(any('E3' in line for line in view['does_not_prove']),
                        'a stored record must not be allowed to read as real-workflow proof')
        self.assertTrue(any('attestation' in line for line in view['does_not_prove']))

    def test_the_read_back_offers_the_digest_so_nobody_has_to_type_one(self):
        entries = quality_store.assessable_versions(self.conn, self.project)
        self.assertEqual([item['subject_ref'] for item in entries], [self.subject])
        self.assertEqual(entries[0]['artifact_sha256'], self.digest)
        self.assertTrue(entries[0]['source_present'])

    # -- refusals, each with its own code -----------------------------------------

    def test_an_unrecorded_project_is_refused(self):
        self._refused('QUALITY_PROJECT_NOT_RECORDED', fragment='not recorded',
                      project_id='f' * 32)

    def test_a_version_that_does_not_exist_is_refused(self):
        self._refused('QUALITY_SUBJECT_UNKNOWN', fragment='not a version',
                      subject_ref=f'{quality_store.SUBJECT_PREFIX}v-nope')

    def test_a_version_of_another_project_is_refused(self):
        # The strongest shape of the case: the version exists, is ACTIVE and the digest
        # is right -- it simply is not this project's.
        self._refused('QUALITY_SUBJECT_UNKNOWN', fragment=self.other, project_id=self.other,
                      subject_ref=self.subject)

    def test_a_subject_that_names_no_version_at_all_is_refused(self):
        self._refused('QUALITY_SUBJECT_REF_MALFORMED', fragment='version:',
                      subject_ref='deliverable/42')

    def test_a_superseded_version_is_refused(self):
        self.conn.execute("UPDATE asset_version SET state='SUPERSEDED' WHERE version_id=?",
                          (self.version,))
        self.conn.commit()
        self._refused('QUALITY_VERSION_NOT_ACTIVE', fragment='SUPERSEDED')

    def test_a_digest_that_is_not_the_version_being_judged_is_refused(self):
        detail = self._refused('QUALITY_DIGEST_MISMATCH', fragment='does not match',
                               artifact_sha256=self.other_digest)
        self.assertIn(self.digest, detail)
        self.assertIn(self.other_digest, detail)

    def test_a_version_whose_bytes_are_gone_is_refused(self):
        """The source has to be there: metadata alone is nothing to certify."""
        gone = self.service.paths.projects_root / self.project / 'assets' / 'ghost.psd'
        digest = 'sha256:' + hashlib.sha256(b'never written to disk').hexdigest()
        version_id = assets.record_version(
            self.conn, 'a1', digest, state='ACTIVE',
            artifacts=[(str(gone), digest, 20, 'deliverable')])
        self.assertFalse(gone.exists(), 'the fixture must really have no source bytes')
        self._refused('QUALITY_SOURCE_MISSING', fragment='no artifact source',
                      subject_ref=f'{quality_store.SUBJECT_PREFIX}{version_id}',
                      artifact_sha256=digest)

    def test_an_automated_judge_is_refused_as_human_acceptance(self):
        # A verdict whose actor declares itself a model, as a document and as inputs.
        model = self._verdict_doc(juror={'juror_id': 'aesthetic-scoring', 'kind': 'MODEL',
                                         'attestation': 'model self-score, 8.4/10'})
        detail = self._refused('QUALITY_NOT_HUMAN', fragment='MODEL', human_verdict=model)
        self.assertIn('human', detail.lower())
        self.assertIn('automated judge', detail.lower())
        with self.assertRaises(QualityStoreError) as direct:
            self._claim(actor_kind='AUTO')
        self.assertEqual(direct.exception.code, 'QUALITY_NOT_HUMAN')
        self.assertIn('AUTO', str(direct.exception))
        self.assertEqual(self._rows(), 0, 'an automated acceptance may not leave a row')

    def test_a_retaged_agent_proposal_is_refused_as_human_acceptance(self):
        proposal = human_jury.agent_may_propose(
            proposal_id='prop-1', subject_ref=self.subject, artifact_sha256=self.digest,
            proposer='review-agent', criteria=CRITERIA, suggested_verdict='APPROVE',
            rationale='weighted score above the floor',
            created_at='2026-10-08T00:00:00Z').as_dict()
        detail = self._refused('QUALITY_NOT_HUMAN', fragment='proposal',
                              human_verdict=dict(proposal, kind='JURY_VERDICT'))
        self.assertIn('automated judge', detail.lower(),
                      'a re-tagged suggestion has to be named as agent-produced')

    def test_a_missing_attestation_is_refused(self):
        blank = self._verdict_doc(juror={'juror_id': 'dtalex66', 'kind': 'HUMAN',
                                         'attestation': '  '})
        self._refused('QUALITY_ATTESTATION_MISSING', fragment='attestation', human_verdict=blank)
        with self.assertRaises(QualityStoreError) as builder:
            self._claim(attestation='')
        self.assertEqual(builder.exception.code, 'QUALITY_ATTESTATION_MISSING')
        self.assertIn('attestation', str(builder.exception).lower())

    def test_a_missing_actor_is_refused_rather_than_assumed(self):
        with self.assertRaises(QualityStoreError) as caught:
            self._claim(actor='')
        self.assertEqual(caught.exception.code, 'QUALITY_ACTOR_MISSING')
        with self.assertRaises(QualityStoreError) as kind:
            self._claim(actor_kind=None)
        self.assertEqual(kind.exception.code, 'QUALITY_ACTOR_MISSING')

    def test_the_contract_is_applied_before_anything_is_written(self):
        # A model-plane finding filed in the deterministic field is refused by the frozen
        # policy, and no row may exist for it afterwards.
        self._refused('QUALITY_RECORD_INVALID', fragment='refused by its own contract',
                      deterministic=[judge_finding('f-smuggled', self.digest, self.subject)])

    def test_a_human_verdict_for_other_bytes_is_refused(self):
        self._refused('QUALITY_DIGEST_MISMATCH', fragment='different digest',
                      human_verdict=self._verdict_doc(artifact_sha256=self.other_digest))

    # -- append-only at the database level ---------------------------------------

    def test_a_sealed_record_cannot_be_edited_in_the_database(self):
        stored = self._record(human_verdict=self._claim())
        with self.assertRaises(sqlite3.IntegrityError) as edited:
            self.conn.execute('UPDATE quality_record SET final_gate="BLOCKED"')
        self.assertIn('immutable', str(edited.exception))
        self.conn.rollback()
        self.assertEqual(self._rows(), 1)
        self.assertEqual(quality_store.list_records(self.conn, self.project)[0]['final_gate'],
                         stored['final_gate'])

    def test_a_sealed_record_cannot_be_deleted_in_the_database(self):
        self._record(human_verdict=self._claim())
        with self.assertRaises(sqlite3.IntegrityError) as deleted:
            self.conn.execute('DELETE FROM quality_record')
        self.assertIn('cannot be deleted', str(deleted.exception))
        self.conn.rollback()
        self.assertEqual(self._rows(), 1, 'a sealed assessment is not something to drop')

    def test_the_database_refuses_a_pass_row_with_no_human_verdict(self):
        # Not a module rule: a hand-written row cannot claim acceptance either, even
        # with every column the store fills filled.
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                'INSERT INTO quality_record (quality_record_id, project_id, subject_ref,'
                ' artifact_sha256, final_gate, human_verdict, juror_id, juror_kind,'
                ' attestation, document_json, created_at, supersedes)'
                " VALUES ('qr-forged', ?, ?, ?, 'PASS', NULL, NULL, NULL, NULL,"
                " '{}', '2026-10-08T00:00:00Z', NULL)",
                (self.project, self.subject, self.digest))
        self.conn.rollback()
        self.assertEqual(self._rows(), 0)

    def test_a_signed_rejection_is_reported_as_a_rejection_not_an_acceptance(self):
        self._record(human_verdict=self._verdict_doc(
            verdict='REJECT', evidence_refs=['reports/current/qa-summary.json']))
        view = quality_store.summary(self.conn, self.project)
        self.assertEqual(view['gates']['BLOCKED'], 1)
        self.assertEqual(view['human_acceptance'], 'NOT_ACCEPTED',
                         'a human REJECT is a signature, never an acceptance')
        self.assertEqual(view['human_rejected_subjects'], [self.subject])

    def test_a_reassessment_is_a_new_row_and_the_chain_stays_readable(self):
        first = self._record(human_verdict=self._claim())
        second = self._record(quality_record_id='qr-second',
                              human_verdict=self._verdict_doc(jury_record_id='jury-2'),
                              supersedes=first['quality_record_id'])
        self.assertEqual(second['final_gate'], 'PASS')
        current = quality_store.current_assessments(self.conn, self.project)
        self.assertEqual(current[self.subject]['quality_record_id'], 'qr-second')
        self.assertEqual([item['quality_record_id']
                          for item in quality_store.list_records(self.conn, self.project)],
                         [first['quality_record_id'], 'qr-second'],
                         'the superseded record stays readable; append-only is not overwrite')

    def test_a_record_cannot_be_superseded_twice(self):
        first = self._record(human_verdict=self._claim())
        self._record(quality_record_id='qr-second', supersedes=first['quality_record_id'],
                     human_verdict=self._verdict_doc(jury_record_id='jury-2'))
        self._refused('QUALITY_ALREADY_SUPERSEDED', fragment='fork',
                      quality_record_id='qr-third', supersedes=first['quality_record_id'],
                      human_verdict=self._verdict_doc(jury_record_id='jury-3'))

    def test_supersedes_naming_another_projects_record_is_refused(self):
        self._record(human_verdict=self._claim())
        self._refused('QUALITY_SUPERSEDES_UNKNOWN', fragment='not a quality record',
                      supersedes='qr-not-here')


    def test_one_accepted_subject_does_not_accept_a_project_with_two(self):
        """'ACCEPTED' describes the project, so partial acceptance must read partial."""
        assets.register_asset(self.conn, self.project, 'a2', 'psd')
        second, second_digest = self._publish(b'another artwork in the same project',
                                             asset_id='a2')
        before = quality_store.summary(self.conn, self.project)
        self.assertEqual(before['assessable_subject_count'], 2)
        self.assertEqual(before['accepted_assessable_subjects'], 0)
        self.assertEqual(before['human_acceptance'], 'NOT_ACCEPTED')

        self._record(human_verdict=self._claim())
        half = quality_store.summary(self.conn, self.project)
        self.assertEqual(half['accepted_assessable_subjects'], 1)
        self.assertEqual(half['human_acceptance'], 'NOT_ACCEPTED',
                         'a signature on one of two live subjects is not the project accepted')

        second_subject = f'{quality_store.SUBJECT_PREFIX}{second}'
        self._record(quality_record_id='qr-second',
                     subject_ref=second_subject,
                     artifact_sha256=second_digest,
                     deterministic=[det_finding('f-det-2', second_digest, second_subject)],
                     human_verdict=self._claim(subject_ref=second_subject,
                                               artifact_sha256=second_digest))
        whole = quality_store.summary(self.conn, self.project)
        self.assertEqual(whole['accepted_assessable_subjects'], 2)
        self.assertEqual(whole['human_acceptance'], 'ACCEPTED')

    def test_a_project_with_nothing_to_assess_is_not_accepted_by_default(self):
        """0 of 0 would be vacuously 'all accepted'; the honest word is NOT_ACCEPTED."""
        empty_project = self.service.create_project('Nothing published')['id']
        view = quality_store.summary(self.conn, empty_project)
        self.assertEqual(view['assessable_versions'], [])
        self.assertEqual(view['assessable_subject_count'], 0)
        self.assertEqual(view['accepted_assessable_subjects'], 0)
        self.assertEqual(view['human_acceptance'], 'NOT_ACCEPTED')

    def test_a_replaced_revision_leaves_the_assessable_list(self):
        """The list offers the current version per asset, not the whole revision history."""
        newer, newer_digest = self._publish(b'revised artwork replaces the first')
        view = quality_store.summary(self.conn, self.project)
        self.assertEqual([item['version_id'] for item in view['assessable_versions']],
                         [newer], 'a draft that was replaced may not be offered for sealing')
        self.assertEqual(view['assessable_subject_count'], 1)
        self.assertNotIn(self.subject,
                         [item['subject_ref'] for item in view['assessable_versions']])


class QualityCliTests(StoreFixture):
    """The `quality` verb: it reads back, it records for a named human, and it refuses
    to do either of the second kind without one."""

    def cli(self, *arguments, project_root=None):
        env = dict(os.environ)
        env.pop('PROJECT_LOCAL_ROOT', None)
        env['PYTHONPATH'] = str(REPO / 'src')
        root = str(project_root or self.base)
        return subprocess.run([sys.executable, '-B', '-m', 'design_lab', '--project', root,
                               *arguments], cwd=root, env=env, capture_output=True,
                              text=True, encoding='utf-8', errors='replace')

    def read_back(self):
        result = self.cli('quality', '--project-id', self.project)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return json.loads(result.stdout)

    def test_the_verb_without_record_reads_back_and_writes_nothing(self):
        view = self.read_back()
        self.assertEqual(view['status'], 'QUALITY_READBACK')
        self.assertEqual(view['project_id'], self.project)
        self.assertEqual(view['record_count'], 0)
        self.assertEqual(view['human_acceptance'], 'NOT_ACCEPTED',
                         'an empty store must read as nobody signed, never as a pass')
        self.assertTrue(view['does_not_prove'])
        self.assertEqual(view['assessable_versions'][0]['artifact_sha256'], self.digest)
        self.assertEqual(self._rows(), 0)

    def test_recording_without_an_actor_is_refused_and_nothing_is_written(self):
        refused = self.cli('quality', '--project-id', self.project, '--record',
                           '--subject', self.subject, '--digest', self.digest,
                           '--verdict', 'APPROVE', '--actor-kind', 'HUMAN',
                           '--attestation', ATTESTATION,
                           '--criterion', 'anti-slop:0.6:4.0',
                           '--criterion', 'brand-fit:0.4:3.5')
        self.assertEqual(refused.returncode, 2, refused.stderr + refused.stdout)
        payload = json.loads(refused.stdout)
        self.assertEqual(payload['status'], 'ERROR')
        self.assertEqual(payload['error'], 'QUALITY_RECORD_INPUTS_REQUIRED')
        self.assertIn('--actor', payload['detail'])
        self.assertEqual(self._rows(), 0, 'a refusal may not leave a record behind')
        self.assertEqual(self.read_back()['record_count'], 0)

    def test_recording_for_a_named_human_then_reading_it_back_from_a_new_process(self):
        recorded = self.cli('quality', '--project-id', self.project, '--record',
                            '--subject', self.subject, '--digest', self.digest,
                            '--actor', 'dtalex66', '--actor-kind', 'HUMAN',
                            '--verdict', 'APPROVE', '--attestation', ATTESTATION,
                            '--criterion', 'anti-slop:0.6:4.0',
                            '--criterion', 'brand-fit:0.4:3.5')
        self.assertEqual(recorded.returncode, 0, recorded.stderr + recorded.stdout)
        payload = json.loads(recorded.stdout)
        self.assertEqual(payload['status'], 'QUALITY_RECORDED')
        self.assertEqual(payload['final_gate'], 'PASS')
        self.assertTrue(payload['does_not_prove'])

        # A second process and a second service instance over the same owner root.
        view = self.read_back()
        self.assertEqual(view['status'], 'QUALITY_READBACK')
        self.assertEqual(view['record_count'], 1)
        self.assertEqual(view['human_acceptance'], 'ACCEPTED')
        self.assertEqual(view['current_assessments'][self.subject]['final_gate'], 'PASS')

    def test_the_cli_refuses_an_automated_acceptance_without_writing(self):
        # Which rule refused is the store suite's assertion to make (it names
        # QUALITY_NOT_HUMAN there); here the property is that the verb turns the refusal
        # into a labelled JSON error and writes nothing, instead of recording an
        # acceptance or tracing back.
        refused = self.cli('quality', '--project-id', self.project, '--record',
                           '--subject', self.subject, '--digest', self.digest,
                           '--actor', 'aesthetic-scoring', '--actor-kind', 'MODEL',
                           '--verdict', 'APPROVE', '--attestation', 'model self-score 8.4',
                           '--criterion', 'anti-slop:1.0:4.0')
        self.assertEqual(refused.returncode, 2, refused.stderr + refused.stdout)
        self.assertNotIn('Traceback', refused.stderr)
        payload = json.loads(refused.stdout)
        self.assertEqual(payload['status'], 'ERROR')
        self.assertTrue(payload['error'].startswith('QUALITY_'), payload['error'])
        self.assertEqual(self._rows(), 0)

    def test_an_unknown_project_id_is_refused_without_creating_state(self):
        stranger = self.base / 'second-owner'
        stranger.mkdir()
        (stranger / 'AGENTS.md').write_text('# second fixture', encoding='utf-8')
        refused = self.cli('quality', '--project-id', 'deadbeef', project_root=stranger)
        self.assertEqual(refused.returncode, 2, refused.stderr + refused.stdout)
        payload = json.loads(refused.stdout)
        self.assertEqual(payload['error'], 'QUALITY_PROJECT_UNKNOWN')
        self.assertFalse((stranger / '.project-local').exists(),
                         'a refused read must not create runtime state')


if __name__ == '__main__':
    unittest.main()
