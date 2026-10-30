# SPDX-License-Identifier: MIT
"""Service façade for the Human Jury review records of one project.

`jury_store` is storage; this is the layer a route can call: it checks the project
exists, maps storage failures to HTTP-meaningful codes, and keeps a retry honest.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing

from .assurance import jury_store
from .assurance.human_jury import KIND_PROPOSAL, KIND_VERDICT


class JuryReviewError(ValueError):
    def __init__(self, status, code):
        self.status, self.code = status, code


class JuryReview:
    def __init__(self, service):
        self.service = service
        self.paths = service.paths

    def _connect(self):
        return jury_store.connect(self.paths.database_path(self.service.database),
                                  project_root=self.paths.project_root)

    def _check_project(self, project_id):
        if self.service.get_project(project_id) is None:
            raise JuryReviewError(404, 'PROJECT_NOT_FOUND')

    def list(self, project_id) -> dict:
        """Read back every record and the current verdict per subject."""
        self._check_project(project_id)
        with closing(self._connect()) as conn:
            records = jury_store.list_records(conn, project_id)
            current = jury_store.current_verdicts(conn, project_id)
            reviewable = jury_store.reviewable_versions(conn, project_id)
        verdicts = [item for item in records if item.get('kind') == KIND_VERDICT]
        proposals = [item for item in records if item.get('kind') == KIND_PROPOSAL]
        # 'ACCEPTED' is a sentence about the PROJECT, so it may not be satisfied by one
        # approved version out of ten: every reviewable version -- the current one per
        # asset -- has to carry a current APPROVE. An empty reviewable set is
        # NOT_ACCEPTED on purpose: "all zero of zero passed" is vacuously true, and a
        # project with nothing published yet has not been accepted by anyone.
        active_refs = {item['subject_ref'] for item in reviewable}
        accepted_refs = {ref for ref in active_refs
                         if (current.get(ref) or {}).get('verdict') == 'APPROVE'}
        every_version_approved = bool(active_refs) and accepted_refs == active_refs
        return {
            'schemaVersion': 'design-lab/jury-readback/v1',
            'project_id': project_id,
            'records': records,
            'verdict_count': len(verdicts),
            'proposal_count': len(proposals),
            # Counts are of what is stored, never of what is "expected": an empty
            # review list here means nobody signed anything, not that work is fine.
            'current_verdicts': current,
            'reviewable_versions': reviewable,
            'accepted_versions': len(accepted_refs),
            'reviewable_active_versions': len(active_refs),
            'human_acceptance': 'ACCEPTED' if every_version_approved else 'NOT_ACCEPTED',
        }

    def record_verdict(self, project_id, document):
        return self._record(project_id, document, KIND_VERDICT)

    def record_proposal(self, project_id, document):
        return self._record(project_id, document, KIND_PROPOSAL)

    def _record(self, project_id, document, kind):
        self._check_project(project_id)
        if not isinstance(document, dict):
            raise JuryReviewError(400, 'INVALID_JURY_DOCUMENT')
        record_id = document.get('jury_record_id') or document.get('proposal_id')
        if not isinstance(record_id, str) or not record_id.strip():
            raise JuryReviewError(400, 'JURY_RECORD_ID_REQUIRED')
        try:
            payload = json.dumps(document, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError):
            raise JuryReviewError(400, 'INVALID_JSON') from None
        with closing(self._connect()) as conn:
            existing = conn.execute('SELECT document_json FROM jury_record'
                                    ' WHERE jury_record_id = ?', (record_id,)).fetchone()
            if existing is not None:
                if existing['document_json'] == payload:
                    # A retry of the same submission is a replay, not a second
                    # verdict: the browser may resend after a lost response, and
                    # duplicating an attestation would misreport who decided.
                    return json.loads(existing['document_json'])
                raise JuryReviewError(409, 'JURY_RECORD_ID_TAKEN')
            try:
                return jury_store.record(conn, project_id=project_id,
                                        document=document, kind=kind)
            except jury_store.JuryStoreError as exc:
                raise JuryReviewError(400, str(exc)) from None
            except sqlite3.IntegrityError as exc:
                raise JuryReviewError(409, f'JURY_RECORD_REJECTED: {exc}') from None
