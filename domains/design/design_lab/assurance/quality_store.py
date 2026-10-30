# SPDX-License-Identifier: MIT
"""Persist sealed QualityRecords against the state database.

The Quality gate existed as a contract long before it existed as a product
capability: ``quality_record.py`` could seal a record and refuse an automated judge,
``qa_plane.py`` owned the policy, and nothing in the tree could store the result. An
unstored assessment is an assessment no verb, no route and no release decision can
cite, so this module is what makes the gate reachable at all.

It deliberately owns *storage* only. Every structural rule stays with the contract
that already had it -- ``schemas/assurance-quality-record.schema.json``,
``quality_record.py`` and ``human_jury.py`` -- and this module runs a document
through them BEFORE it is written, so the database can never hold a record the
policy would refuse. What is enforced here instead is the part a JSON schema cannot
see:

* the subject must be a version this project actually has, currently readable, and
  the digest being judged must be that version's own digest -- a judgement about
  bytes the project does not hold is not a judgement;
* the bytes must still be there: a recorded version whose artifact file has gone is
  refused rather than certified from metadata alone;
* an automated judge may not be filed as a human acceptance. The actor kind
  vocabulary is ``human_jury``'s own; the refusal is labelled here so an operator is
  told "automation cannot sign" instead of "your JSON is wrong";
* history is append-only. A re-assessment is a NEW row carrying ``supersedes``, and
  one record cannot be superseded twice, or "the current assessment" stops being
  defined. The immutability itself is the database's (the triggers in
  ``design-lab-state-quality-v1.sql``), not a convention of this module.

Every refusal is a :class:`QualityStoreError` with a distinct ``code``, because a
single "invalid record" message cannot tell an operator whether they mistyped a
digest, pointed at another project's version, or tried to file a model score as a
human signature.

Boundary: this module runs no check, calls no provider, opens no host and invents no
human identity. It stores what a human or a pipeline sealed, and fails closed
otherwise.
"""
from __future__ import annotations

from typing import Mapping
import json
import sqlite3
from pathlib import Path
import uuid

from . import AssuranceError, human_jury, quality_record, utc_now_rfc3339
from .jury_store import SUBJECT_PREFIX
from ..runtime.state_resources import state_schema

_QUALITY = state_schema('design-lab-state-quality-v1.sql')

#: The read-back statements this store is allowed to make. They live here so the CLI
#: and the later HTTP/UI slice cannot each invent a friendlier claim about the same
#: rows: a recorded attestation is a *claim*, and the gate this table proves is the
#: one the sealed document derives, nothing more.
DOES_NOT_PROVE = (
    'a recorded attestation is a named person stating they judged these bytes; it is not '
    'proof that a human looked at the artifact, which needs the out-of-band E4 Human Gate '
    'record (human_jury.py states the same limit)',
    'no deterministic check was re-run by recording: final_gate=PASS reports the sealed '
    'record, not a fresh scan of the artifact',
    'no host, no re-open and no editable delivery is observed here, so a stored record is '
    'not E3 REAL_WORKFLOW evidence',
    'an automated_judge finding attached to a subject never moves final_gate and is never '
    'acceptance; it is advisory by construction (quality_record.final_gate_of)',
    'rights, production preflight and release acceptance are separate gates; a quality '
    'record proves none of them',
)

_READBACK_VERSION = 'design-lab/quality-readback/v1'

#: The closed vocabulary of refusal codes this store may raise. Declared here so a
#: route or a table can show an operator every way the gate says no, and so a new
#: refusal cannot quietly invent a code nobody reads: an unlisted code is a bug in
#: this module, not something the caller has to guess at.
REFUSAL_CODES = frozenset({
    'QUALITY_PROJECT_NOT_RECORDED',
    'QUALITY_SUBJECT_REF_MALFORMED',
    'QUALITY_SUBJECT_UNKNOWN',
    'QUALITY_VERSION_NOT_ACTIVE',
    'QUALITY_DIGEST_MISMATCH',
    'QUALITY_SOURCE_MISSING',
    'QUALITY_NOT_HUMAN',
    'QUALITY_ATTESTATION_MISSING',
    'QUALITY_ACTOR_MISSING',
    'QUALITY_VERDICT_UNKNOWN',
    'QUALITY_CRITERION_MISSING',
    'QUALITY_HUMAN_CLAIM_MALFORMED',
    'QUALITY_HUMAN_CLAIM_INVALID',
    'QUALITY_VERDICT_INVALID',
    'QUALITY_RECORD_INVALID',
    'QUALITY_SUPERSEDES_UNKNOWN',
    'QUALITY_ALREADY_SUPERSEDED',
    'QUALITY_RECORD_ID_TAKEN',
    'QUALITY_DATABASE_REFUSED',
    'QUALITY_STORED_RECORD_INVALID',
})


class QualityStoreError(RuntimeError):
    """A quality assessment was refused; ``code`` names which rule refused it."""

    def __init__(self, message: str, *, code: str):
        super().__init__(message)
        if code not in REFUSAL_CODES:
            # Never let a refusal go out under a label nothing documents.
            raise AssertionError(f'undocumented quality refusal code {code!r}')
        self.code = code


def connect(db_path, *, project_root=None) -> sqlite3.Connection:
    """Open the state database with the quality tables present.

    The asset store is asked to open its own database rather than this module
    re-applying schema files: ``asset_store.connect`` carries the path policy, the
    foreign-key pragma and the assets-v2 migration with its pre-migration backup.
    Doing it twice here would be a second implementation of the same migration, and
    the two would drift. (``jury_store.connect`` is the precedent.)
    """
    from ..runtime.asset_store import connect as connect_assets
    connection = connect_assets(db_path, project_root=project_root)
    connection.row_factory = sqlite3.Row
    connection.executescript(_QUALITY.read_text(encoding='utf-8'))
    connection.commit()
    return connection


def new_record_id() -> str:
    return 'qr-' + uuid.uuid4().hex


def _normalise(value):
    if not isinstance(value, str):
        return None
    return value.strip().removeprefix('sha256:').lower()


def _project_row(conn, project_id):
    return conn.execute('SELECT project_id, display_name FROM project WHERE project_id = ?',
                        (project_id,)).fetchone()


def _version_row(conn, subject_ref):
    """The published version an assessment is about, or None.

    ``subject_ref`` names a version id, the only stable handle for "these exact
    bytes" in this state -- a filename or a project id can be re-pointed at
    different bytes after a verdict was signed. The prefix is jury_store's, so both
    assurance stores mean the same thing by a subject.
    """
    if not isinstance(subject_ref, str) or not subject_ref.startswith(SUBJECT_PREFIX):
        raise QualityStoreError(
            f'subject_ref must be "{SUBJECT_PREFIX}<version_id>"; an assessment bound to '
            'nothing cannot be reviewed, reverted or cited', code='QUALITY_SUBJECT_REF_MALFORMED')
    return conn.execute(
        'SELECT v.version_id, v.asset_id, v.content_sha256, v.state, v.created_at, a.project_id'
        ' FROM asset_version v JOIN asset a ON a.asset_id = v.asset_id'
        ' WHERE v.version_id = ?', (subject_ref[len(SUBJECT_PREFIX):],)).fetchone()


def _source_state(conn, version_id, digest) -> tuple:
    """(present, detail) -- does the judged version's bytes still exist on disk?

    The database records paths; the bytes are the thing being judged. A metadata row
    whose file is gone would otherwise let a "sealed" record certify nothing.
    """
    rows = conn.execute('SELECT path, sha256, role FROM artifact WHERE version_id = ?',
                        (version_id,)).fetchall()
    if not rows:
        return False, 'the version records no artifact bytes at all'
    bound = [row for row in rows if _normalise(row['sha256']) == _normalise(digest)]
    if not bound:
        return False, ('none of the recorded artifacts carry the digest being judged '
                       f'({digest})')
    for row in bound:
        try:
            if Path(row['path']).is_file():
                return True, row['path']
        except OSError:
            # An unreadable/overlong path is not proof the bytes are there.
            continue
    return False, f'the recorded artifact file is missing: {Path(bound[0]["path"]).name}'


def _assert_human_claim(document) -> None:
    """Refuse, by name, an automated judge presented as human acceptance.

    The rules are ``human_jury``'s own vocabularies; this only decides which code an
    operator sees. Without it a MODEL-signed or proposal-marked document would still
    be refused downstream, but as "invalid jury record" -- which tells the person who
    tried to auto-accept their own render nothing about the gate they just hit.
    """
    if not isinstance(document, Mapping):
        raise QualityStoreError('the human claim must be a jury verdict document; failing '
                                'closed rather than assuming a signature',
                                code='QUALITY_HUMAN_CLAIM_MALFORMED')
    markers = [name for name in human_jury.PROPOSAL_MARKERS if name in document]
    if markers:
        raise QualityStoreError(
            f'the human claim carries the proposal marker(s) {", ".join(markers)}: an '
            'automated judge produced it, and an agent suggestion re-tagged as a verdict is '
            'still not human acceptance', code='QUALITY_NOT_HUMAN')
    juror = document.get('juror') or {}
    kind = juror.get('kind') if isinstance(juror, Mapping) else None
    if kind in human_jury.AGENT_ACTOR_KINDS or (kind is not None
                                               and kind not in human_jury.HUMAN_JUROR_KINDS):
        raise QualityStoreError(
            f'an automated judge (juror kind {kind!r}) was presented as human acceptance; '
            f'only {", ".join(human_jury.HUMAN_JUROR_KINDS)} may sign this gate',
            code='QUALITY_NOT_HUMAN')
    if not str((juror or {}).get('attestation') or '').strip():
        raise QualityStoreError(
            'the human claim carries no attestation: an unsigned statement is not a signed '
            'gate', code='QUALITY_ATTESTATION_MISSING')
    try:
        human_jury.assert_not_agent_signed(document)
    except AssuranceError as exc:
        # The contract refused this claim after this module's own named guards passed.
        # That is a different fact from "this module identified an automated judge", and
        # the two codes are kept apart deliberately: `QUALITY_NOT_HUMAN` is the answer
        # to "why was my model score rejected from the human gate", while this one means
        # the verdict document is malformed in some other way the contract caught.
        raise QualityStoreError(str(exc), code='QUALITY_HUMAN_CLAIM_INVALID') from None


def human_acceptance(*, actor, actor_kind, attestation, verdict, subject_ref,
                     artifact_sha256, criteria, evidence_refs=(), members=(),
                     jury_record_id=None, decided_at=None) -> dict:
    """Build the signed human-jury verdict a QualityRecord seals, or refuse it.

    Nothing here is defaulted: no actor, no verdict, no criteria means no human
    acceptance, and the refusal names the missing input. The finished document is
    validated by ``human_jury.record_verdict`` -- this function does not own the
    criteria, weighting or REJECT-needs-evidence rules, it collects the inputs.
    """
    missing = [name for name, value in (('actor', actor), ('actor_kind', actor_kind))
               if not (isinstance(value, str) and value.strip())]
    if missing:
        raise QualityStoreError(
            f'human acceptance needs a stated {", ".join(missing)}; nothing is assumed on '
            "someone's behalf", code='QUALITY_ACTOR_MISSING')
    if not isinstance(attestation, str) or not attestation.strip():
        raise QualityStoreError(
            'human acceptance needs the attestation the actor is signing -- what they '
            'actually looked at and how; an empty statement signs nothing',
            code='QUALITY_ATTESTATION_MISSING')
    if verdict not in human_jury.VERDICTS:
        raise QualityStoreError(
            f'the human verdict must be one of {", ".join(human_jury.VERDICTS)}; got '
            f'{verdict!r}. There is no third state to file a wish under',
            code='QUALITY_VERDICT_UNKNOWN')
    if not criteria:
        raise QualityStoreError(
            'a jury verdict states the criteria it was judged on; with no criterion the '
            'record would certify a judgement nobody described',
            code='QUALITY_CRITERION_MISSING')
    document = {
        'schemaVersion': human_jury.REVIEW_VERSION,
        'kind': human_jury.KIND_VERDICT,
        'jury_record_id': jury_record_id or ('jury-' + uuid.uuid4().hex),
        'subject_ref': subject_ref,
        'artifact_sha256': artifact_sha256,
        'juror': {'juror_id': actor, 'kind': actor_kind, 'attestation': attestation,
                  **({'members': list(members)} if members else {})},
        'criteria': [dict(item) if isinstance(item, Mapping) else item
                     for item in criteria],
        'verdict': verdict,
        'decided_at': decided_at or utc_now_rfc3339(),
        'supersedes': None,
        'evidence_refs': list(evidence_refs),
    }
    _assert_human_claim(document)
    try:
        return human_jury.record_verdict(document)
    except AssuranceError as exc:
        raise QualityStoreError(str(exc), code='QUALITY_VERDICT_INVALID') from None


def record(conn, *, project_id, subject_ref, artifact_sha256, human_verdict=None,
           deterministic=(), automated_judge=(), quality_record_id=None,
           supersedes=None, created_at=None) -> dict:
    """Validate one sealed assessment against the live state, then append it.

    Returns the stored document. Order is deliberate: the state checks come before
    the contract check, because "that version is not yours" is a different mistake
    from "that document is malformed", and an operator needs to be told which.
    """
    if _project_row(conn, project_id) is None:
        raise QualityStoreError(
            f'project {project_id!r} is not recorded in this state database: an assessment '
            'cannot be filed against a project that does not exist here',
            code='QUALITY_PROJECT_NOT_RECORDED')
    row = _version_row(conn, subject_ref)
    if row is None or row['project_id'] != project_id:
        raise QualityStoreError(
            f'{subject_ref!r} is not a version of project {project_id!r}; a judgement must '
            'attach to bytes this project actually has', code='QUALITY_SUBJECT_UNKNOWN')
    if row['state'] != 'ACTIVE':
        raise QualityStoreError(
            f'{subject_ref} is {row["state"]}, not ACTIVE; only a currently readable version '
            'can be assessed, and a superseded one must be re-assessed on its own record',
            code='QUALITY_VERSION_NOT_ACTIVE')
    judged = _normalise(artifact_sha256)
    if judged != _normalise(row['content_sha256']):
        raise QualityStoreError(
            f'the digest being judged ({artifact_sha256}) does not match the digest '
            f'{subject_ref} actually holds ({row["content_sha256"]}); the record would certify '
            'one set of bytes while pointing at another', code='QUALITY_DIGEST_MISMATCH')
    present, detail = _source_state(conn, row['version_id'], artifact_sha256)
    if not present:
        raise QualityStoreError(
            f'no artifact source to judge behind {subject_ref}: {detail}',
            code='QUALITY_SOURCE_MISSING')

    if human_verdict is not None:
        _assert_human_claim(human_verdict)
        if _normalise(human_verdict.get('artifact_sha256')) != judged:
            raise QualityStoreError(
                'the human verdict is bound to a different digest than the version being '
                'judged; one record describes one artifact', code='QUALITY_DIGEST_MISMATCH')

    try:
        document = quality_record.record_quality_record(
            quality_record_id=quality_record_id or new_record_id(),
            subject_ref=subject_ref, artifact_sha256=artifact_sha256,
            deterministic=deterministic, automated_judge=automated_judge,
            human_verdict=human_verdict, created_at=created_at)
    except AssuranceError as exc:
        raise QualityStoreError(
            f'the assessment was refused by its own contract before anything was written: '
            f'{exc}', code='QUALITY_RECORD_INVALID') from exc

    if supersedes is not None:
        if not conn.execute('SELECT 1 FROM quality_record WHERE quality_record_id = ?'
                            ' AND project_id = ?', (supersedes, project_id)).fetchone():
            raise QualityStoreError(
                f'supersedes {supersedes!r} is not a quality record of this project',
                code='QUALITY_SUPERSEDES_UNKNOWN')
        if conn.execute('SELECT 1 FROM quality_record WHERE supersedes = ?',
                        (supersedes,)).fetchone():
            raise QualityStoreError(
                f'{supersedes} has already been superseded; a second replacement would fork '
                'the assessment chain and leave the current record undefined',
                code='QUALITY_ALREADY_SUPERSEDED')
        if supersedes == document['quality_record_id']:
            raise QualityStoreError('a quality record may not supersede itself',
                                    code='QUALITY_SUPERSEDES_UNKNOWN')

    jury = document.get(quality_record.FIELD_HUMAN_JURY) or {}
    juror = jury.get('juror') or {}
    try:
        conn.execute(
            'INSERT INTO quality_record (quality_record_id, project_id, subject_ref,'
            ' artifact_sha256, final_gate, human_verdict, juror_id, juror_kind, attestation,'
            ' document_json, created_at, supersedes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            (document['quality_record_id'], project_id, document['subject_ref'],
             document['artifact_sha256'], document['final_gate'], jury.get('verdict'),
             juror.get('juror_id'), juror.get('kind'), juror.get('attestation'),
             json.dumps(document, ensure_ascii=False, sort_keys=True),
             document['created_at'], supersedes))
        conn.commit()
    except sqlite3.IntegrityError as exc:
        # The triggers and CHECKs in the schema are the last line; reaching them means
        # something above this module is wrong, so it is reported, never retried.
        text = str(exc)
        code = ('QUALITY_RECORD_ID_TAKEN' if 'quality_record.' in text
                and 'immutable' not in text and 'cannot be deleted' not in text
                else 'QUALITY_DATABASE_REFUSED')
        raise QualityStoreError(
            f'the state database refused the record: {text}', code=code) from None
    return document


def list_records(conn, project_id) -> list:
    """Every stored assessment of one project, oldest first, re-validated on read.

    A row that no longer satisfies the contract is a tamper signal, not something to
    serve quietly: the append-only triggers make it unreachable in normal operation,
    so failing here means the schema or the policy moved underneath the data.
    """
    rows = conn.execute(
        'SELECT document_json FROM quality_record WHERE project_id = ?'
        ' ORDER BY created_at, quality_record_id', (project_id,)).fetchall()
    records = []
    for row in rows:
        document = json.loads(row['document_json'])
        try:
            quality_record.validate_quality_record(document)
        except AssuranceError as exc:
            raise QualityStoreError(
                f'the stored record {document.get("quality_record_id")!r} no longer satisfies '
                f'the quality record contract: {exc}', code='QUALITY_STORED_RECORD_INVALID'
            ) from None
        records.append(document)
    return records


def current_assessments(conn, project_id) -> dict:
    """subject_ref -> the record nothing has replaced. newest decision wins."""
    rows = conn.execute(
        'SELECT document_json FROM quality_record WHERE project_id = ?'
        ' AND NOT EXISTS (SELECT 1 FROM quality_record child'
        '                 WHERE child.supersedes = quality_record.quality_record_id)'
        ' ORDER BY created_at, quality_record_id', (project_id,)).fetchall()
    current = {}
    for row in rows:
        item = json.loads(row['document_json'])
        current[item['subject_ref']] = item
    return current


def assessable_versions(conn, project_id) -> list:
    """The version an assessment may be filed against per asset, digest included.

    Nobody should have to type a digest: the point of binding a record to one is that
    it is not hand-written. ``source_present`` is reported too, because a version
    whose bytes have gone is refused by ``record`` and an operator should be able to
    see that before trying.

    One row per asset -- the highest ``version_no`` still marked ACTIVE -- for the same
    reason ``jury_store.reviewable_versions`` does it that way: publications never
    demote the bytes they replace, so "every ACTIVE version" is a revision history, and
    an assessment of a draft would count as accepting the deliverable.
    """
    rows = conn.execute(
        "SELECT v.version_id, v.asset_id, v.content_sha256, v.created_at"
        " FROM asset_version v JOIN asset a ON a.asset_id = v.asset_id"
        " WHERE a.project_id = ? AND v.state = 'ACTIVE'"
        " AND v.version_no = (SELECT MAX(b.version_no) FROM asset_version b"
        "                     WHERE b.asset_id = v.asset_id AND b.state = 'ACTIVE')"
        " ORDER BY v.created_at, v.version_id", (project_id,)).fetchall()
    result = []
    for row in rows:
        present, detail = _source_state(conn, row['version_id'], row['content_sha256'])
        result.append({'subject_ref': f'{SUBJECT_PREFIX}{row["version_id"]}',
                       'version_id': row['version_id'], 'asset_id': row['asset_id'],
                       'artifact_sha256': row['content_sha256'],
                       'created_at': row['created_at'], 'source_present': present,
                       'source': detail if present else None,
                       'source_note': None if present else detail})
    return result


def summary(conn, project_id) -> dict:
    """The read-back: what is recorded, whether any of it is human acceptance,
    and what none of it proves."""
    if not _project_row(conn, project_id):
        raise QualityStoreError(
            f'project {project_id!r} is not recorded in this state database',
            code='QUALITY_PROJECT_NOT_RECORDED')
    records = list_records(conn, project_id)
    current = current_assessments(conn, project_id)
    assessable = assessable_versions(conn, project_id)
    gates = {gate: 0 for gate in quality_record.GATES}
    for item in records:
        gates[item['final_gate']] = gates.get(item['final_gate'], 0) + 1
    assessable_refs = {item['subject_ref'] for item in assessable}
    verdicts = {ref: ((current.get(ref) or {}).get(quality_record.FIELD_HUMAN_JURY) or {})
                   .get('verdict') for ref in assessable_refs}
    accepted = sorted(ref for ref, verdict in verdicts.items() if verdict == human_jury.APPROVE)
    rejected = sorted(ref for ref, verdict in verdicts.items() if verdict == human_jury.REJECT)
    # 'ACCEPTED' describes the PROJECT, so it may not be carried by one accepted subject
    # out of many, and "0 of 0 accepted" is vacuously true rather than accepted.
    every_subject_accepted = bool(assessable_refs) and set(accepted) == assessable_refs
    return {
        'schemaVersion': _READBACK_VERSION,
        'project_id': project_id,
        'record_count': len(records),
        'gates': gates,
        'current_assessments': current,
        'assessable_versions': assessable,
        # A count of what is stored, never of what is expected: zero records means
        # nobody signed anything, not that the work is fine.
        'accepted_assessable_subjects': len(accepted),
        'assessable_subject_count': len(assessable_refs),
        'human_acceptance': 'ACCEPTED' if every_subject_accepted else 'NOT_ACCEPTED',
        'human_accepted_subjects': accepted,
        'human_rejected_subjects': rejected,
        'automated_judge_is_acceptance': False,
        'does_not_prove': list(DOES_NOT_PROVE),
    }
