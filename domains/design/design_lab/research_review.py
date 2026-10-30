# SPDX-License-Identifier: MIT
"""Service façade for the research findings of one project.

``assurance/research_store.py`` is storage; this is the layer a route and a verb call. It
checks the project exists, maps store refusals to HTTP-meaningful status and codes, and owns
the one thing a reader is most likely to over-read: a populated research panel.

The honesty rule, and it is the load-bearing one here. Rights has ``rights_clearance`` and
Jury has ``ACCEPTED``/``NOT_ACCEPTED``, and both had to be written carefully because a
project-level verdict word is a claim about a gate. **Research has no such word, and this
façade invents none.** There is no ``RESEARCH_COMPLETE``, no ``CLEARED``, no
``PENDING_REVIEW``: "how many findings exist" and "is the research finished" are unrelated
questions, and AGENTS.md puts no human gate at this surface -- the Direction, Quality, Rights,
Production and Release gates are elsewhere, and a finding is working input to them, not one of
them. So the read-back publishes numbers and three explicit non-claims instead of a verdict:

* ``finding_count`` / ``current_finding_count`` / ``superseded_finding_count`` -- what is
  stored, what nothing has replaced, and what a correction left readable;
* ``sourced_finding_count`` / ``unsourced_finding_count`` -- re-derived from the stored bytes,
  never read off the count column. The store refuses a finding with no source, so the second
  number is 0 for every project that ever passed through it; it is published anyway, because
  the sentence a reader needs is "every one of these cites something", and a 0 computed from
  the bytes is the only version of that sentence worth printing;
* ``proves_design_quality`` / ``is_knowledge_export`` are ``False``, and ``research_verdict``
  is ``None`` with the reason attached, so a page that wanted a "done" badge has to say where
  the word came from instead of taking one from here.

Attribution is reported, never inferred: the closed contract has no author field, so anything
filed over HTTP is listed in ``unattributed_findings`` and only a caller that stated a kind
(the CLI, which asks the operator) is distinguishable from one that did not.
"""
from __future__ import annotations

from contextlib import closing
import json
import sqlite3

from .assurance import research_store

_READBACK_VERSION = 'design-lab/research-readback/v1'

#: Stated as text because a reader looking for a verdict needs the reason, not just a null.
_NO_VERDICT_NOTE = (
    'this surface publishes no completion or clearance word: a count of findings is not a '
    'statement that research is finished, and no such word exists in '
    'design-lab/config/state-vocabularies.json for it to come from')


class ResearchReviewError(ValueError):
    """A research read or write was refused at the boundary.

    ``status`` is the HTTP status and ``code`` the stable word a caller branches on;
    ``detail`` carries the reason. Kept apart on purpose: a collapsed "invalid request"
    cannot tell an operator whether they cited no source, filed against a project that does
    not exist here, retired another project's finding, or signed a human claim as a machine.
    """

    def __init__(self, status, code, detail=None):
        self.status, self.code, self.detail = status, code, detail


def write_fields() -> frozenset:
    """The exact key set a submission may carry: the contract's own property names.

    Read from the loaded schema rather than restated, so http_service.py cannot become a
    second list that outlives the contract it claims to enforce. Note this set contains no
    ``schemaVersion``: unlike the rights and jury contracts, the research-finding schema
    closes its properties without declaring one, so a submission that sent the field it was
    conditioned on is refused rather than quietly accepted.
    """
    return frozenset(research_store.field_names())


def readback(conn, project_id: str) -> dict:
    """The research read-back for one project, computed from what is actually stored."""
    if research_store.project_row(conn, project_id) is None:
        raise research_store.ResearchStoreError(
            f'project {project_id!r} is not recorded in this state database',
            code='RESEARCH_PROJECT_NOT_RECORDED')
    vocabulary = research_store.confidence_vocabulary()
    findings = research_store.list_findings(conn, project_id=project_id)
    current = research_store.current_findings(conn, project_id=project_id)
    counts = research_store.source_counts(conn, project_id=project_id)
    kinds = research_store.actor_kinds(conn, project_id=project_id)
    sourced = sum(1 for count in counts.values() if count > 0)
    confidences = {word: 0 for word in vocabulary}
    # Every declared category carries a number, including 0: an absent key reads as "not
    # applicable" to a page, which is how a vocabulary loses a member in plain sight.
    for document in current.values():
        stated = document.get('confidence')
        if stated is not None:
            confidences[stated] += 1
    return {
        'schemaVersion': _READBACK_VERSION,
        'project_id': project_id,
        'findings': findings,
        'finding_count': len(findings),
        'current_findings': current,
        'current_finding_count': len(current),
        'superseded_finding_count': len(findings) - len(current),
        # Re-derived from the stored bytes, not read off the column.
        'sourced_finding_count': sourced,
        'unsourced_finding_count': len(counts) - sourced,
        'source_ref_total': sum(counts.values()),
        'source_ref_field': research_store.source_ref_field(),
        'confidence_counts': confidences,
        'confidence_vocabulary': list(vocabulary),
        'stated_confidence_count': sum(1 for document in current.values()
                                       if document.get('confidence') is not None),
        'unattributed_findings': research_store.unattributed_findings(conn,
                                                                     project_id=project_id),
        'actor_kinds': kinds,
        'undeclared_disclaimer': research_store.undeclared_disclaimer(conn,
                                                                     project_id=project_id),
        'proves_design_quality': False,
        'is_knowledge_export': False,
        'research_verdict': None,
        'research_verdict_note': _NO_VERDICT_NOTE,
        'does_not_prove': list(research_store.DOES_NOT_PROVE),
    }


class ResearchReview:
    def __init__(self, service):
        self.service = service
        self.paths = service.paths

    def _connect(self):
        return research_store.connect(self.paths.database_path(self.service.database),
                                      project_root=self.paths.project_root)

    def _check_project(self, project_id):
        if self.service.get_project(project_id) is None:
            raise ResearchReviewError(404, 'PROJECT_NOT_FOUND')

    def list(self, project_id) -> dict:
        """Read back every filed finding and the counts the stored rows actually support."""
        self._check_project(project_id)
        with closing(self._connect()) as conn:
            try:
                return readback(conn, project_id)
            except research_store.ResearchStoreError as exc:
                raise self._map(exc) from None

    def record(self, project_id, document, *, supersedes=None):
        """File one research finding, or replay the identical submission."""
        self._check_project(project_id)
        if not isinstance(document, dict):
            raise ResearchReviewError(400, 'RESEARCH_DOCUMENT_MALFORMED',
                                      'the body must be one research finding object')
        finding_id = document.get('finding_id')
        if not isinstance(finding_id, str) or not finding_id.strip():
            raise ResearchReviewError(
                400, 'RESEARCH_FINDING_ID_REQUIRED',
                'a research finding needs a finding_id, so a retry can be recognised as a '
                'retry instead of filed as a second finding')
        try:
            rounded = json.loads(json.dumps(document, ensure_ascii=False, sort_keys=True))
        except (TypeError, ValueError):
            raise ResearchReviewError(400, 'INVALID_JSON',
                                      'the body is not JSON that can be stored') from None
        # Optional contract fields may be sent as null at the boundary -- "not stated" -- and
        # absence is what the contract allows, not a null value for them. The clean-up happens
        # BEFORE the replay comparison: the stored row is the normalized document, so comparing
        # the raw body against it would turn an identical resend into a 409 and force a caller
        # to file a second finding for one claim. (`sourceRefs` is required, so a null there is
        # a refusal the store makes by name, not something to clean away here.)
        document = {name: value for name, value in rounded.items()
                    if not (value is None and name in research_store.optional_field_names())}
        payload = json.dumps(document, ensure_ascii=False, sort_keys=True)
        with closing(self._connect()) as conn:
            existing = conn.execute('SELECT document_json FROM research_finding'
                                    ' WHERE finding_id = ?', (finding_id,)).fetchone()
            if existing is not None:
                if existing['document_json'] == payload:
                    # A retry of the same submission is a replay, not a second filing: the
                    # browser may resend after a lost response, and duplicating a finding would
                    # misreport how many claims a project holds.
                    return json.loads(existing['document_json'])
                raise ResearchReviewError(
                    409, 'RESEARCH_FINDING_ID_TAKEN',
                    f'{finding_id} is already filed with different content; a research finding '
                    'is append-only, so the correction is a new finding_id that supersedes it')
            try:
                return research_store.record(conn, project_id=project_id, document=document,
                                             supersedes=supersedes)
            except research_store.ResearchStoreError as exc:
                raise self._map(exc) from None
            except sqlite3.IntegrityError as exc:
                raise ResearchReviewError(409, 'RESEARCH_DATABASE_REFUSED',
                                          f'the state database refused the finding: {exc}') from None

    @staticmethod
    def _map(exc: research_store.ResearchStoreError) -> ResearchReviewError:
        """Store refusal -> boundary refusal. One rule decides the status everywhere.

        'Nothing was recorded' and 'what was recorded contradicts itself' are different facts
        and must not arrive under one status: the first is a normal empty read (the read-back
        answers 200 with zero findings), the second means a stored row no longer satisfies the
        contract it was written under, which no client can fix by retrying.
        """
        if exc.code == 'RESEARCH_PROJECT_NOT_RECORDED':
            return ResearchReviewError(404, exc.code, str(exc))
        if exc.code == 'RESEARCH_STORED_RECORD_INVALID':
            return ResearchReviewError(409, exc.code, str(exc))
        # A supersede link reaching into another project's history is the caller's mistake, not
        # a conflict a client cannot resolve: it is refused as 400 with both project ids named,
        # exactly as the rights façade treats a supersede across two use scopes.
        if exc.code in ('RESEARCH_CONTRACT_UNREADABLE', 'RESEARCH_CONTRACT_UNBOUND'):
            # Not the caller's mistake: the contract this surface validates against moved or
            # cannot be read, so nothing can be trusted to conform to it.
            return ResearchReviewError(500, exc.code, str(exc))
        return ResearchReviewError(400, exc.code, str(exc))
