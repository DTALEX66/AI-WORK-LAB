# SPDX-License-Identifier: MIT
"""Human Jury persistence: a verdict is bound to real bytes, then it cannot be edited.

Everything here is driven through the real asset publisher, because the point of
the store is that a judgement attaches to a version the project actually has. A
fixture that hand-inserted an `asset_version` row would let the binding checks pass
against a shape production never writes.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(REPO / 'src'))

from design_lab.assurance import human_jury, jury_store        # noqa: E402
from design_lab.assurance.jury_store import JuryStoreError     # noqa: E402
from design_lab.runtime import asset_store as assets           # noqa: E402

CRITERIA = [{'criterion_id': 'composition', 'weight': 0.4, 'score': 4.2,
             'note': 'hierarchy reads at thumbnail size'},
            {'criterion_id': 'typography', 'weight': 0.3, 'score': 3.8,
             'note': 'line length needs a second pass'},
            {'criterion_id': 'brand-fit', 'weight': 0.3, 'score': 4.0,
             'note': 'palette matches the locked system'}]


class JuryStoreTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        self.db = self.base / 'state.db'
        self.conn = jury_store.connect(self.db)
        self.conn.execute('INSERT INTO project VALUES ("p1","Jury Probe",'
                          '"2026-10-08T00:00:00Z")')
        self.conn.execute('INSERT INTO asset VALUES ("a1","p1","psd","2026-10-08T00:00:00Z")')
        self.conn.commit()
        self.version_id, self.digest = self._publish(b'first accepted artwork')

    def tearDown(self):
        self.conn.close()

    def _publish(self, payload: bytes):
        """Put a real ACTIVE version into the store and return (version_id, sha256)."""
        source = self.base / f'in-{len(payload)}.psd'
        source.write_bytes(payload)
        digest = 'sha256:' + hashlib.sha256(payload).hexdigest()
        store = self.base / 'projects/p1/assets'
        store.mkdir(parents=True, exist_ok=True)
        resource = 'asset:a1'
        attempt = 'attempt-' + hashlib.sha256(payload).hexdigest()[:12]
        if not assets.acquire_writer(self.conn, resource, attempt):
            self.fail('writer lease refused')
        generation = assets.writer_token(self.conn, resource, attempt)
        version_id = assets.publish_version(self.conn, 'a1', source, store_root=store,
                                           artifact_name='native.psd',
                                           expected_sha256=digest, holder_attempt_id=attempt,
                                           generation=generation)
        assets.release_writer(self.conn, resource, attempt, generation=generation)
        # The record schema pins the digest form to `sha256:<hex>` (and rejects the
        # all-zero digest), so the fixture keeps the canonical prefix rather than
        # storing bare hex and letting the store paper over the difference.
        return version_id, digest

    def _document(self, **overrides):
        base = {
            'schemaVersion': human_jury.REVIEW_VERSION,
            'jury_record_id': 'jury-1',
            'subject_ref': f'{jury_store.SUBJECT_PREFIX}{self.version_id}',
            'artifact_sha256': self.digest,
            'juror': {'juror_id': 'dtalex66', 'kind': 'HUMAN',
                      'attestation': 'reviewed at 100% on the production display'},
            'criteria': CRITERIA,
            'verdict': 'APPROVE',
            'decided_at': '2026-10-08T00:00:00Z',
            'supersedes': None,
            'evidence_refs': [],
        }
        base.update(overrides)
        return base

    def test_a_real_verdict_is_stored_and_read_back_from_a_new_connection(self):
        stored = jury_store.record(self.conn, project_id='p1',
                                   document=self._document())
        self.assertEqual(stored['jury_record_id'], 'jury-1')
        with closing(sqlite3.connect(self.db)) as reopened:
            reopened.row_factory = sqlite3.Row
            rows = jury_store.list_records(reopened, 'p1')
            current = jury_store.current_verdicts(reopened, 'p1')
        self.assertEqual([row['jury_record_id'] for row in rows], ['jury-1'])
        self.assertEqual(list(current), [self._document()['subject_ref']])
        self.assertEqual(current[list(current)[0]]['verdict'], 'APPROVE')

    def test_an_agent_cannot_sign_the_human_gate(self):
        document = self._document(juror={'juror_id': 'agent-1', 'kind': 'CODEX',
                                         'attestation': 'auto-accepted'})
        with self.assertRaises(JuryStoreError) as caught:
            jury_store.record(self.conn, project_id='p1', document=document)
        message = str(caught.exception)
        # The refusal has to name the actor kind it rejected. "not a valid juror"
        # would let an operator believe the document was malformed rather than
        # understanding that automation may not sign a human gate.
        self.assertIn('CODEX', message)
        self.assertIn('human', message.lower())

    def test_a_verdict_cannot_bind_to_a_version_that_does_not_exist(self):
        document = self._document(subject_ref=f'{jury_store.SUBJECT_PREFIX}v-nope')
        with self.assertRaisesRegex(JuryStoreError, 'not a version of this project'):
            jury_store.record(self.conn, project_id='p1', document=document)

    def test_a_verdict_cannot_certify_a_different_digest_than_it_names(self):
        other_version, other_digest = self._publish(b'second artwork')
        document = self._document(subject_ref=f'{jury_store.SUBJECT_PREFIX}{other_version}',
                                  artifact_sha256=self.digest)
        with self.assertRaisesRegex(JuryStoreError, 'does not match the version'):
            jury_store.record(self.conn, project_id='p1', document=document)

    def test_a_superseded_verdict_cannot_be_superseded_twice(self):
        jury_store.record(self.conn, project_id='p1', document=self._document())
        jury_store.record(self.conn, project_id='p1',
                          document=self._document(jury_record_id='jury-2', supersedes='jury-1'))
        with self.assertRaisesRegex(JuryStoreError, 'already been superseded'):
            jury_store.record(self.conn, project_id='p1',
                              document=self._document(jury_record_id='jury-3',
                                                      supersedes='jury-1'))
        current = jury_store.current_verdicts(self.conn, 'p1')
        self.assertEqual([row['jury_record_id'] for row in current.values()], ['jury-2'])

    def test_superseding_a_record_from_another_project_is_refused(self):
        with self.assertRaisesRegex(JuryStoreError, 'not a record of this project'):
            jury_store.record(self.conn, project_id='p1',
                              document=self._document(supersedes='jury-elsewhere'))

    def test_a_rejection_without_evidence_is_refused(self):
        document = self._document(verdict='REJECT', evidence_refs=[])
        with self.assertRaisesRegex(JuryStoreError, 'evidence_ref'):
            jury_store.record(self.conn, project_id='p1', document=document)

    def test_a_proposal_never_becomes_the_current_judgement(self):
        proposal = human_jury.agent_may_propose(
            proposal_id='prop-1', subject_ref=self._document()['subject_ref'],
            artifact_sha256=self.digest, proposer='review-agent', criteria=CRITERIA,
            suggested_verdict='APPROVE', rationale='weighted score above the floor',
            created_at='2026-10-08T00:00:00Z')
        document = proposal if isinstance(proposal, dict) else proposal.as_dict()
        stored = jury_store.record(self.conn, project_id='p1', document=document,
                                   kind=human_jury.KIND_PROPOSAL)
        self.assertEqual(stored['kind'], human_jury.KIND_PROPOSAL)
        self.assertEqual(jury_store.current_verdicts(self.conn, 'p1'), {},
                         'a proposal is listed evidence, not a gate outcome')
        listed = jury_store.list_records(self.conn, 'p1')
        self.assertEqual([row.get('jury_record_id') or row.get('proposal_id')
                          for row in listed],
                         [stored.get('jury_record_id') or stored.get('proposal_id')],
                         'a proposal must be listed under the id it actually carries')

    def _proposal(self, **overrides):
        """A proposal document built by the contract itself, so a mutation below is the
        only thing wrong with it."""
        document = human_jury.agent_may_propose(
            proposal_id='prop-9', subject_ref=self._document()['subject_ref'],
            artifact_sha256=self.digest, proposer='review-agent', criteria=CRITERIA,
            suggested_verdict='APPROVE', rationale='weighted score above the floor',
            created_at='2026-10-08T00:00:00Z').as_dict()
        document.update(overrides)
        return document

    def test_a_proposal_is_stored_only_if_the_contract_accepts_its_values(self):
        """The route pins the proposal's KEY SET; only human_jury judges the values.

        Before this check the store wrote whatever the endpoint accepted, so a proposal
        with a non-digest artifact, a verdict word that does not exist, an empty rationale
        or a timestamp that is not RFC 3339 became a permanent row -- in an append-only
        table whose whole purpose is that a later reader can trust what the agent said.
        """
        cases = {
            'artifact_sha256': ('not-a-digest',),
            'suggested_verdict': ('MAYBE',),
            'rationale': ('',),
            'created_at': ('last tuesday',),
            'proposer': ('',),
        }
        for index, (field, values) in enumerate(sorted(cases.items())):
            for value in values:
                with self.subTest(field=field, value=value):
                    before = len(jury_store.list_records(self.conn, 'p1'))
                    # A distinct id per case: if the guard is missing, the colliding id would
                    # surface as an IntegrityError and mask which refusal actually failed.
                    with self.assertRaises(JuryStoreError) as refused:
                        jury_store.record(self.conn, project_id='p1',
                                          document=self._proposal(proposal_id=f'prop-{index}',
                                                                   **{field: value}),
                                          kind=human_jury.KIND_PROPOSAL)
                    self.assertTrue(str(refused.exception).strip(),
                                    'a refusal has to say why it refused')
                    self.assertEqual(len(jury_store.list_records(self.conn, 'p1')), before,
                                     'a refused proposal must not leave a row behind')
        # and the unmutated document still lands, or the loop above proves nothing
        stored = jury_store.record(self.conn, project_id='p1',
                                   document=self._proposal(proposal_id='prop-valid'),
                                   kind=human_jury.KIND_PROPOSAL)
        self.assertEqual(stored['kind'], human_jury.KIND_PROPOSAL)

    def test_a_proposal_carrying_a_verdict_is_refused(self):
        smuggled = self._document()
        smuggled.pop('jury_record_id')
        smuggled['proposal_id'] = 'prop-2'
        with self.assertRaises(JuryStoreError):
            jury_store.record(self.conn, project_id='p1',
                              document={'proposal_id': 'prop-2',
                                        'subject_ref': self._document()['subject_ref'],
                                        'artifact_sha256': self.digest,
                                        'proposer': 'review-agent',
                                        'criteria': CRITERIA,
                                        'verdict': 'APPROVE',
                                        'decided_at': '2026-10-08T00:00:00Z'},
                              kind=human_jury.KIND_PROPOSAL)

    def test_a_signed_record_cannot_be_edited_or_deleted(self):
        jury_store.record(self.conn, project_id='p1', document=self._document())
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE jury_record SET verdict='REJECT' WHERE jury_record_id='jury-1'")
        self.conn.rollback()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("DELETE FROM jury_record WHERE jury_record_id='jury-1'")
        self.conn.rollback()
        self.assertEqual(len(jury_store.list_records(self.conn, 'p1')), 1)

    def test_the_stored_document_is_the_validated_one_not_the_request(self):
        jury_store.record(self.conn, project_id='p1', document=self._document())
        stored = json.loads(self.conn.execute(
            'SELECT document_json FROM jury_record').fetchone()[0])
        self.assertEqual(stored['kind'], human_jury.KIND_VERDICT)
        self.assertEqual(stored['schemaVersion'], human_jury.REVIEW_VERSION)

    def test_a_verdict_on_a_superseded_version_is_refused(self):
        """Only the currently readable version can be accepted."""
        self.conn.execute("UPDATE asset_version SET state='SUPERSEDED'"
                          ' WHERE state="ACTIVE"')
        self.conn.commit()
        with self.assertRaisesRegex(JuryStoreError, 'SUPERSEDED'):
            jury_store.record(self.conn, project_id='p1', document=self._document())


if __name__ == '__main__':
    unittest.main()
