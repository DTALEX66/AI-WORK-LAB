# SPDX-License-Identifier: MIT
"""Service façade for the Human RIGHTS decisions of one project.

``assurance/rights_ledger.py`` is storage; this is the layer a route and a verb call. It
checks the project exists, maps storage refusals to HTTP-meaningful status and codes, and
owns the one word a reader can be misled by: ``rights_clearance``.

The clearance rule, and why it is written the way it is:

* ``CLEARED`` requires at least one use scope on file **and** a current ``APPROVED`` for
  every scope that is currently on file. ``0 of 0`` is vacuously "all approved", and a
  project nobody has filed anything for has not been cleared by anybody -- the same
  mistake ``jury_review.py`` and ``quality_store.py`` each had to close.
* everything else is ``NOT_REVIEWED``, including a project whose filed decision is
  ``DENIED`` or ``BLOCKED_BY_LICENSE``. That is not sloppiness: ``NOT_REVIEWED`` is the
  word this vocabulary has for "the gate does not read as cleared", and the read-back
  publishes ``approved_scope_count`` / ``filed_scope_count`` / ``unapproved_scopes`` next
  to it, so a reader can tell "nobody filed anything" from "a human refused it" instead of
  being asked to trust one word for both. ``PENDING_REVIEW`` is **not** emitted here at
  all: it is a word a human may file (the contract allows it), never a word the façade may
  infer, because "somebody has been asked and owes an answer" is a claim about a request
  that may not have been made. An untouched gate reads NOT_REVIEWED -- the load-bearing
  rule ``creative/approval.py`` states for the projected gates.
* the clearance covers the scopes this project filed, not every subject that needs a
  decision. This ledger holds no requirements list and does not read
  ``design-lab/config/rights-registry.json``; ``does_not_prove`` says so on every response.
"""
from __future__ import annotations

from contextlib import closing
import json
import sqlite3

from .assurance import rights_ledger

#: The two words this façade can produce for a project. They are module constants, not
#: inline literals, because design-lab/scripts/verify_state_vocabularies.py reads them back
#: out of this file and compares them with design-lab/config/state-vocabularies.json -- the
#: UI is allowed to show a clearance word only if an emitter really produces it.
CLEARED = 'CLEARED'
NOT_REVIEWED = 'NOT_REVIEWED'
CLEARANCE_STATES = (CLEARED, NOT_REVIEWED)

#: The one contract word that clears a scope. Named here so "approved" is a decision this
#: module is held to, not a comparison against a string that drifted in from a copy.
APPROVED = 'APPROVED'

_READBACK_VERSION = 'design-lab/rights-readback/v1'


class RightsReviewError(ValueError):
    """A rights read or write was refused at the boundary.

    ``status`` is the HTTP status and ``code`` the stable word a caller branches on;
    ``detail`` carries the reason. The code and the reason are kept apart on purpose: a
    collapsed "invalid request" cannot tell an operator whether they mistyped a scope,
    filed against a project that does not exist, or tried to sign a human gate as a model.
    """

    def __init__(self, status, code, detail=None):
        self.status, self.code, self.detail = status, code, detail


def write_fields() -> frozenset:
    """The exact key set a submission may carry: the contract's own property names.

    Read from the loaded schema rather than restated, so http_service.py cannot become a
    second list that outlives the contract it claims to enforce.
    """
    return frozenset(rights_ledger.field_names())


def readback(conn, project_id: str) -> dict:
    """The rights read-back for one project, computed from what is actually stored."""
    if rights_ledger.project_row(conn, project_id) is None:
        raise rights_ledger.RightsLedgerError(
            f'project {project_id!r} is not recorded in this state database',
            code='RIGHTS_PROJECT_NOT_RECORDED')
    vocabulary = rights_ledger.decision_vocabulary()
    if APPROVED not in vocabulary:
        raise rights_ledger.RightsLedgerError(
            f'{rights_ledger.CONTRACT_PATH.name} no longer allows {APPROVED!r}, so nothing in '
            f'its vocabulary {list(vocabulary)} can clear a scope; refusing rather than '
            'reading a different word as approval', code='RIGHTS_CONTRACT_UNBOUND')
    decisions = rights_ledger.list_decisions(conn, project_id=project_id)
    current = rights_ledger.current_decisions(conn, project_id=project_id)
    scopes = sorted(current)
    approved = [scope for scope in scopes if current[scope]['decision'] == APPROVED]
    unapproved = [{'use_scope': scope,
                   'decision': current[scope]['decision'],
                   'decision_id': current[scope]['decision_id'],
                   'decided_by': current[scope]['decided_by']} for scope in scopes
                  if scope not in approved]
    # 'CLEARED' is a sentence about the PROJECT, so it may not be carried by one approved
    # scope out of several, and it may not be carried by an empty set at all.
    cleared = bool(scopes) and len(approved) == len(scopes)
    states = {word: 0 for word in vocabulary}
    for scope in scopes:
        states[current[scope]['decision']] += 1
    return {
        'schemaVersion': _READBACK_VERSION,
        'project_id': project_id,
        'decisions': decisions,
        'decision_count': len(decisions),
        # What stands now, per use scope. A scope nobody filed is absent, never defaulted.
        'current_decisions': current,
        'decision_states': states,
        'filed_scope_count': len(scopes),
        'approved_scope_count': len(approved),
        'unapproved_scopes': unapproved,
        'ever_filed_scopes': rights_ledger.filed_scopes(conn, project_id=project_id),
        'scope_conflicts': rights_ledger.unlinked_scope_conflicts(conn, project_id=project_id),
        'name_checked_only': rights_ledger.name_checked_only(conn, project_id=project_id),
        'rights_clearance': CLEARED if cleared else NOT_REVIEWED,
        'clearance_vocabulary': list(CLEARANCE_STATES),
        'decision_vocabulary': list(vocabulary),
        'does_not_prove': list(rights_ledger.DOES_NOT_PROVE),
    }


class RightsReview:
    def __init__(self, service):
        self.service = service
        self.paths = service.paths

    def _connect(self):
        return rights_ledger.connect(self.paths.database_path(self.service.database),
                                     project_root=self.paths.project_root)

    def _check_project(self, project_id):
        if self.service.get_project(project_id) is None:
            raise RightsReviewError(404, 'PROJECT_NOT_FOUND')

    def list(self, project_id) -> dict:
        """Read back every filed decision and the clearance the project actually holds."""
        self._check_project(project_id)
        with closing(self._connect()) as conn:
            try:
                return readback(conn, project_id)
            except rights_ledger.RightsLedgerError as exc:
                raise self._map(exc) from None

    def record(self, project_id, document, *, supersedes=None):
        """File one human rights decision, or replay the identical submission."""
        self._check_project(project_id)
        if not isinstance(document, dict):
            raise RightsReviewError(400, 'RIGHTS_DOCUMENT_MALFORMED',
                                    'the body must be one rights decision object')
        decision_id = document.get('decision_id')
        if not isinstance(decision_id, str) or not decision_id.strip():
            raise RightsReviewError(400, 'RIGHTS_DECISION_ID_REQUIRED',
                                    'a rights decision needs a decision_id, so a retry can be '
                                    'recognised as a retry instead of filed as a second '
                                    'decision')
        try:
            rounded = json.loads(json.dumps(document, ensure_ascii=False, sort_keys=True))
        except (TypeError, ValueError):
            raise RightsReviewError(400, 'INVALID_JSON',
                                    'the body is not JSON that can be stored') from None
        # Optional contract fields may be sent as null at the boundary -- "not stated" -- and
        # absence is what the contract allows, never a null value for them. The clean-up
        # happens BEFORE the replay comparison: the stored row is the normalized document, so
        # comparing the raw body against it would turn an identical resend into a 409 and
        # make a human re-file a decision they already signed.
        document = {name: value for name, value in rounded.items()
                    if not (value is None and name in rights_ledger.optional_field_names())}
        payload = json.dumps(document, ensure_ascii=False, sort_keys=True)
        with closing(self._connect()) as conn:
            existing = conn.execute('SELECT document_json FROM rights_decision'
                                    ' WHERE decision_id = ?', (decision_id,)).fetchone()
            if existing is not None:
                if existing['document_json'] == payload:
                    # A retry of the same submission is a replay, not a second decision:
                    # the browser may resend after a lost response, and duplicating an
                    # attestation would misreport what the human signed.
                    return json.loads(existing['document_json'])
                raise RightsReviewError(
                    409, 'RIGHTS_DECISION_ID_TAKEN',
                    f'{decision_id} is already filed with different content; a rights decision '
                    'is append-only, so the correction is a new decision_id that supersedes it')
            try:
                return rights_ledger.record(conn, project_id=project_id, document=document,
                                            supersedes=supersedes)
            except rights_ledger.RightsLedgerError as exc:
                raise self._map(exc) from None
            except sqlite3.IntegrityError as exc:
                raise RightsReviewError(409, 'RIGHTS_DATABASE_REFUSED',
                                        f'the state database refused the decision: {exc}') from None

    @staticmethod
    def _map(exc: rights_ledger.RightsLedgerError) -> RightsReviewError:
        """Store refusal -> boundary refusal. One rule decides the status everywhere.

        'Nothing was recorded' and 'what was recorded contradicts itself' are different
        facts and must not arrive under one status: the first is a normal empty read (the
        read-back answers 200 with NOT_REVIEWED), the second means a stored row no longer
        satisfies the contract it was written under, which no client can fix by retrying.
        """
        if exc.code == 'RIGHTS_PROJECT_NOT_RECORDED':
            return RightsReviewError(404, exc.code, str(exc))
        if exc.code == 'RIGHTS_STORED_RECORD_INVALID':
            return RightsReviewError(409, exc.code, str(exc))
        if exc.code in ('RIGHTS_CONTRACT_UNREADABLE', 'RIGHTS_CONTRACT_UNBOUND'):
            # Not the caller's mistake: the gate's own contract moved or is unreadable.
            return RightsReviewError(500, exc.code, str(exc))
        return RightsReviewError(400, exc.code, str(exc))
