# SPDX-License-Identifier: MIT
"""Persist Human Jury records against the state database.

`human_jury.py` validates a verdict; this module is what makes one survive a
restart, so a route can serve it and the Workbench can show a real judgement
instead of an empty panel.

Three properties are enforced here rather than left to the caller:

* a verdict is bound to an existing published version and to that version's own
  digest, so nobody can approve a bytes-the-project-does-not-have;
* history is append-only. A re-judgement is a new record carrying `supersedes`,
  and a verdict that has already been superseded cannot be superseded twice --
  that would fork the acceptance chain and leave "the current verdict" undefined;
* an agent proposal is stored as a proposal. It never reaches the verdict column,
  and the human-signature guard is applied to verdicts only.
"""
from __future__ import annotations

import json
import sqlite3

from .human_jury import (AssuranceError, KIND_PROPOSAL, KIND_VERDICT, agent_may_propose,
                         record_verdict)
from ..runtime.state_resources import state_schema

_JURIES = state_schema('design-lab-state-jury-v1.sql')

#: A verdict is taken on one published version, and the only stable name for that
#: in this state is its version_id. Anything looser (a filename, a project id) can
#: be re-pointed at different bytes after the fact.
SUBJECT_PREFIX = 'version:'


class JuryStoreError(RuntimeError):
    pass


def connect(db_path, *, project_root=None) -> sqlite3.Connection:
    """Open the state database with the jury tables present.

    The asset store is asked to open its own database rather than this module
    re-applying schema files: `asset_store.connect` carries the path policy, the
    foreign-key pragma and the assets-v2 migration with its pre-migration backup.
    Doing it twice here would be a second implementation of the same migration,
    and the two would drift.
    """
    from ..runtime.asset_store import connect as connect_assets
    connection = connect_assets(db_path, project_root=project_root)
    connection.row_factory = sqlite3.Row
    connection.executescript(_JURIES.read_text(encoding='utf-8'))
    connection.commit()
    return connection


def _normalise_digest(value):
    if not isinstance(value, str):
        return None
    return value.strip().removeprefix('sha256:').lower()


def _version_row(conn, project_id, subject_ref):
    """Return the published version a verdict is about, or None."""
    if not isinstance(subject_ref, str) or not subject_ref.startswith(SUBJECT_PREFIX):
        raise JuryStoreError(
            f'subject_ref must be "{SUBJECT_PREFIX}<version_id>"; a verdict bound to '
            'nothing cannot be reviewed or reverted')
    version_id = subject_ref[len(SUBJECT_PREFIX):]
    return conn.execute(
        'SELECT v.version_id, v.asset_id, v.version_no, v.content_sha256, v.state, a.project_id,'
        ' (SELECT MAX(b.version_no) FROM asset_version b'
        '   WHERE b.asset_id = v.asset_id AND b.state = \'ACTIVE\') AS latest_version_no'
        ' FROM asset_version v JOIN asset a ON a.asset_id = v.asset_id'
        ' WHERE v.version_id = ?', (version_id,)).fetchone()


def record(conn, *, project_id, document: dict, kind: str = KIND_VERDICT) -> dict:
    """Validate and append one jury record; returns the stored document.

    `kind` selects the guard: a verdict must be human-signed and must match a real
    published version, a proposal must NOT carry a verdict.
    """
    declared = document.get('kind')
    if declared not in (None, kind):
        raise JuryStoreError(
            f'record kind {declared!r} does not match the endpoint it was sent to ({kind!r})')
    document = dict(document)
    document['kind'] = kind
    # `project_id` is deliberately not written into the document: the record schema
    # closes its properties, and the owning project is a column on the row. Copying
    # it in would make a valid human verdict fail validation for a storage reason.
    if kind == KIND_PROPOSAL:
        if document.get('verdict') is not None:
            raise JuryStoreError(
                'a proposal may not carry a verdict; an agent may propose, never decide')
        # The route pins the key set; only the contract checks the VALUES. Without this
        # call a proposal with a non-digest artifact_sha256, an empty rationale, a
        # suggested_verdict outside the declared vocabulary or criteria that are not
        # criterion objects would be appended to an immutable table -- and the row is
        # exactly the kind of record a later reader trusts as "what the agent said".
        # Reuse the contract's own builder rather than re-implementing its rules here.
        try:
            document = agent_may_propose(
                proposal_id=document.get('proposal_id'), subject_ref=document.get('subject_ref'),
                artifact_sha256=document.get('artifact_sha256'),
                proposer=document.get('proposer'), criteria=document.get('criteria'),
                suggested_verdict=document.get('suggested_verdict'),
                rationale=document.get('rationale'),
                created_at=document.get('created_at')).as_dict()
        except AssuranceError as exc:
            raise JuryStoreError(str(exc)) from None
    else:
        try:
            document = record_verdict(document)
        except AssuranceError as exc:
            raise JuryStoreError(str(exc)) from None
        subject_ref = document.get('subject_ref')
        row = _version_row(conn, project_id, subject_ref)
        if row is None or row['project_id'] != project_id:
            raise JuryStoreError(
                f'the verdict names {subject_ref!r}, which is not a version of this project; '
                'a judgement must attach to bytes that exist')
        if row['state'] != 'ACTIVE':
            raise JuryStoreError(
                f'{subject_ref} is {row["state"]}, not ACTIVE; only a currently readable '
                'version can be accepted, and a superseded one must be re-judged on its own')
        # A revision that was published after this one leaves it ACTIVE on disk (the
        # store never demotes replaced bytes), so `state` alone would still let a
        # reviewer sign a draft and have it count as accepting the deliverable.
        if row['version_no'] != row['latest_version_no']:
            raise JuryStoreError(
                f'{subject_ref} is version {row["version_no"]} of {row["asset_id"]}, but the '
                f'latest ACTIVE one is {row["latest_version_no"]}; a verdict has to name the '
                'bytes that would actually be delivered, not a draft they replaced')
        stored = _normalise_digest(document.get('artifact_sha256'))
        if stored != _normalise_digest(row['content_sha256']):
            raise JuryStoreError(
                'artifact_sha256 does not match the version being judged: the verdict would '
                ' certify one digest while pointing at another')

    supersedes = document.get('supersedes')
    if supersedes is not None and kind == KIND_VERDICT:
        if not conn.execute('SELECT 1 FROM jury_record WHERE jury_record_id = ? AND project_id = ?',
                            (supersedes, project_id)).fetchone():
            raise JuryStoreError(f'supersedes {supersedes!r} is not a record of this project')
        if conn.execute('SELECT 1 FROM jury_record WHERE supersedes = ?', (supersedes,)).fetchone():
            raise JuryStoreError(
                f'{supersedes} has already been superseded; a second replacement would fork '
                'the acceptance chain and leave the current verdict undefined')

    juror = document.get('juror') or {}
    # A verdict is keyed by jury_record_id; a proposal is keyed by proposal_id and
    # has no juror at all. Reading one field for both would raise on the very record
    # type whose whole purpose is to be distinguishable from a verdict.
    record_id = document.get('jury_record_id') or document.get('proposal_id')
    if not record_id:
        raise JuryStoreError('the record carries neither jury_record_id nor proposal_id')
    conn.execute(
        'INSERT INTO jury_record (jury_record_id, kind, project_id, subject_ref,'
        ' artifact_sha256, verdict, juror_id, juror_kind, attestation, document_json,'
        ' decided_at, supersedes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
        (record_id, kind, project_id, document.get('subject_ref'),
         _normalise_digest(document.get('artifact_sha256')), document.get('verdict'),
         juror.get('juror_id'), juror.get('kind'), juror.get('attestation'),
         json.dumps(document, ensure_ascii=False, sort_keys=True),
         document.get('decided_at') or document.get('created_at'), supersedes))
    conn.commit()
    return document


def list_records(conn, project_id, *, after=None) -> list:
    """Return records for one project, newest first within the chain order."""
    rows = conn.execute(
        'SELECT document_json FROM jury_record WHERE project_id = ?'
        ' ORDER BY decided_at, jury_record_id', (project_id,)).fetchall()
    records = [json.loads(row['document_json']) for row in rows]
    if after is not None:
        index = next((i for i, item in enumerate(records)
                      if item['jury_record_id'] == after), None)
        if index is None:
            raise JuryStoreError(f'after cursor {after!r} is not a record of this project')
        records = records[index + 1:]
    return records


def reviewable_versions(conn, project_id) -> list:
    """The version a verdict may be filed against per asset, digest included.

    A reviewer should never have to type a digest: the point of binding a verdict
    to one is that nobody has to trust a hand-written value. This is the list the
    picker offers, and `record` re-checks the pairing anyway.

    One row per asset, not one per revision: `publish_version` never demotes the
    bytes it replaced, so an asset keeps every ACTIVE version it has ever had, and
    the product reads "the current one" as the highest `version_no` elsewhere
    (`native_assets.list`, `current_version`). Offering the whole history here would
    invite a signature on a superseded draft and then let that signature count as
    acceptance of work that is no longer deliverable.
    """
    rows = conn.execute(
        "SELECT v.version_id, v.asset_id, v.content_sha256, v.created_at, v.version_no"
        " FROM asset_version v JOIN asset a ON a.asset_id = v.asset_id"
        " WHERE a.project_id = ? AND v.state = 'ACTIVE'"
        " AND v.version_no = (SELECT MAX(b.version_no) FROM asset_version b"
        "                     WHERE b.asset_id = v.asset_id AND b.state = 'ACTIVE')"
        " ORDER BY v.created_at, v.version_id", (project_id,)).fetchall()
    return [{'subject_ref': f'{SUBJECT_PREFIX}{row["version_id"]}',
             'version_id': row['version_id'], 'asset_id': row['asset_id'],
             'version_no': row['version_no'],
             'artifact_sha256': row['content_sha256'], 'created_at': row['created_at']}
            for row in rows]


def current_verdicts(conn, project_id) -> dict:
    """Map subject_ref -> the record nothing has replaced.

    Only JURY_VERDICT rows qualify; proposals are listed but never become the
    current judgement, which is the difference between a suggestion and a gate.
    """
    rows = conn.execute(
        "SELECT document_json FROM jury_record WHERE project_id = ?"
        " AND kind = 'JURY_VERDICT'"
        " AND NOT EXISTS (SELECT 1 FROM jury_record child"
        "                 WHERE child.supersedes = jury_record.jury_record_id)"
        " ORDER BY decided_at, jury_record_id", (project_id,)).fetchall()
    current = {}
    for row in rows:
        item = json.loads(row['document_json'])
        # Later rows win: two verdicts for one subject with no supersede link between
        # them is a data bug, and the newest decision is the only defensible answer.
        current[item['subject_ref']] = item
    return current
