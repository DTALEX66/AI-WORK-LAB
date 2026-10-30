# SPDX-License-Identifier: MIT
"""Project-owned native exports and bounded immutable archive downloads.

``create`` publishes the archive *and* the DeliveryReceipt V2 that says what shipped,
from which host, with which digests. ``receipt`` reads that persisted document back and
``readback`` adds what the asset ledger now says about the restores the document promises;
the document is never extended on the way out, because it signs its own bytes. The receipt
is validated by the emitter before it is stored and re-verified on every read, so a delivery
never answers with a document its own bytes contradict, and a rollback reference that names
no current version is reported as unresolved rather than believed. A missing host readback
stays missing: the document this path emits is ``PARTIAL`` by construction and says plainly
what it does not prove.
"""
from contextlib import closing, contextmanager
import hashlib
import re
import sqlite3

from .image_assets import ImageAssetError
from .interop import InteropError, delivery_receipt
from .native_tasks import NativeTasks, NativeTaskError
from .task_queries import TaskQueries
from .runtime.bundle_store import MAX_TOTAL

RECEIPT_QUERY = ('SELECT r.receipt_json,r.receipt_sha256 FROM delivery_receipt_v1 r '
    'JOIN asset a ON a.asset_id=r.asset_id '
    'JOIN asset_version v ON v.version_id=r.version_id AND v.asset_id=a.asset_id '
    'JOIN artifact f ON f.version_id=v.version_id '
    "WHERE r.version_id=? AND r.asset_id=? AND r.project_id=? AND a.project_id=? "
    "AND v.version_id=? AND v.state='ACTIVE'")

#: The shape ``native_bundles._rollback_of`` writes. The receipt schema only requires that
#: ``backup_ref`` be text, and records in this repository really do carry other forms
#: (``backup-1``, ``backup://job-7``), so a reference outside this form is reported as unparsed
#: rather than guessed at: inventing an asset id to make a promise look satisfied is exactly the
#: false green this file exists to avoid.
BACKUP_REF = re.compile(r'^asset:(?P<asset_id>[^/]+)/version:(?P<version_id>[^/]+)$')

#: What checking one rollback reference against the asset ledger can conclude.
ROLLBACK_STATES = ('RESOLVED', 'SOURCE_MISSING', 'OTHER_PROJECT', 'SOURCE_NOT_ACTIVE',
                   'REF_UNPARSED')

#: How those per-deliverable states aggregate into one word for the whole read-back.
ROLLBACK_SUMMARIES = ('ALL_RESOLVED', 'PARTLY_UNRESOLVED', 'NONE_RESOLVED',
                      'NOTHING_TO_CHECK', 'LEDGER_UNREADABLE')

#: Published with every envelope, so a reader gets the vocabulary and the limit together and the
#: Workbench transponds both instead of restating them in its own words.
ROLLBACK_STATE_MEANING = {
    'RESOLVED': 'the named asset version is still recorded here, belongs to this project and is '
                'ACTIVE -- the restore the receipt plans still has something to restore from',
    'SOURCE_MISSING': 'no such version row exists for the named asset at all',
    'OTHER_PROJECT': 'the version exists but its asset belongs to a different project, so this '
                     'project could not restore from it',
    'SOURCE_NOT_ACTIVE': 'the version row exists but is not ACTIVE, so it is not a current '
                         'restore point',
    'REF_UNPARSED': 'the reference is not in the asset:<id>/version:<id> form this emitter '
                    'writes, so nothing was looked up',
    'ALL_RESOLVED': 'every deliverable of this receipt names a restore source that still resolves',
    'PARTLY_UNRESOLVED': 'some deliverables resolve and some do not; the document still promises '
                         'a restore it cannot fully honour',
    'NONE_RESOLVED': 'no deliverable names a restore source that resolves',
    'NOTHING_TO_CHECK': 'the receipt carries no deliverables, so there was nothing to resolve -- '
                        'which is not the same fact as "all resolved"',
    'LEDGER_UNREADABLE': 'the asset ledger could not be asked during this read, so no '
                         'reference was checked; the word says the lookup failed, not that '
                         'the restore sources are gone',
}

#: The version the envelope binds, written as data the emitter emits (verify_contract_bindings.py
#: holds a row to the version that really appears in this file).
READBACK_SCHEMA_VERSION = 'design-lab/delivery-receipt-readback/v1'

#: What no amount of resolution proves. Said once, published on every response.
ROLLBACK_DOES_NOT_PROVE = (
    'a RESOLVED reference proves that the immutable source version the archive was exported from '
    'is still recorded for this project; it does not prove that a restore was performed, and none '
    'has been: the receipt calls its own rollback record a plan',
    'resolution reads the asset ledger only. It opens no host document, re-runs no task, and '
    're-checks no artifact byte beyond what the receipt already digests',
    'an unparsed reference is reported as REF_UNPARSED with the text that failed to parse. '
    'Nothing here supplies an asset id or a version number the document did not state',
)

#: (state, version_no, project match) for one named version, whatever its state.
ROLLBACK_LOOKUP = ('SELECT v.state,v.version_no,a.project_id FROM asset_version v '
    'JOIN asset a ON a.asset_id=v.asset_id WHERE v.asset_id=? AND v.version_id=?')


def _resolve_rollback(conn, project_id: str, entry: dict) -> dict:
    """One deliverable's rollback promise, looked up in the ledger it names."""
    record = entry.get('rollback') or {}
    reference = record.get('backup_ref')
    proof = {'deliverable_id': entry.get('deliverable_id'), 'backup_ref': reference,
             'procedure': record.get('procedure'), 'asset_id': None, 'version_id': None,
             'version_no': None, 'source_state': None}
    if not isinstance(reference, str) or not reference.strip():
        return {**proof, 'state': 'REF_UNPARSED',
                'reason': 'the rollback record states no backup_ref, so there is nothing to look '
                          'up and no restore point to promise'}
    match = BACKUP_REF.match(reference.strip())
    if match is None:
        return {**proof, 'state': 'REF_UNPARSED',
                'reason': f'{reference!r} is not in the asset:<id>/version:<id> form this emitter '
                          'writes, so it names no ledger row'}
    asset_id, version_id = match['asset_id'], match['version_id']
    row = conn.execute(ROLLBACK_LOOKUP, (asset_id, version_id)).fetchone()
    identity = {**proof, 'asset_id': asset_id, 'version_id': version_id}
    if row is None:
        return {**identity, 'state': 'SOURCE_MISSING',
                'reason': f'no version {version_id} is recorded for asset {asset_id}: the '
                          'document promises a restore from something this ledger does not hold'}
    state, version_no, owner = row[0], row[1], row[2]
    found = {**identity, 'version_no': version_no, 'source_state': state}
    if owner != project_id:
        return {**found, 'state': 'OTHER_PROJECT',
                'reason': f'asset {asset_id} belongs to another project, so this project cannot '
                          'restore from the version the receipt names'}
    if state != 'ACTIVE':
        return {**found, 'state': 'SOURCE_NOT_ACTIVE',
                'reason': f'the version row is {state!r}, not ACTIVE'}
    return {**found, 'state': 'RESOLVED',
            'reason': f'version {version_no} of asset {asset_id} is recorded ACTIVE for this '
                      'project, which is what the rollback plan assumes still exists'}


def rollback_proofs(conn, receipt: dict, project_id: str):
    """(summary, per-deliverable proofs) for one receipt document."""
    proofs = [_resolve_rollback(conn, project_id, entry)
              for entry in (receipt.get('deliverables') or [])]
    states = [proof['state'] for proof in proofs]
    if not states:
        summary = 'NOTHING_TO_CHECK'
    elif all(state == 'RESOLVED' for state in states):
        summary = 'ALL_RESOLVED'
    elif any(state == 'RESOLVED' for state in states):
        summary = 'PARTLY_UNRESOLVED'
    else:
        summary = 'NONE_RESOLVED'
    return summary, proofs


def _rollback_or_unreadable(conn, receipt: dict, project_id: str):
    """Resolve the promises a receipt makes, or say plainly that the ledger could not be asked.

    A query failure must not surface as NOTHING_TO_CHECK: that word means the document names no
    deliverable. Reporting an unread ledger under it would turn "nothing was looked at" into
    "there was nothing to look at", which is the same collapse this file refuses everywhere else.
    """
    try:
        return rollback_proofs(conn, receipt, project_id)
    except sqlite3.Error:
        return 'LEDGER_UNREADABLE', []


class NativeDelivery:
    def __init__(self,service):
        self.service=service

    def create(self,project_id,job_id):
        task=TaskQueries(self.service).get(project_id,job_id)['task']
        aid=task['attempt']['attempt_id']
        database=self.service.paths.database_path(self.service.database)
        with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)) as conn:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='native_execution_v1'").fetchone():
                raise ImageAssetError(409,'NATIVE_RECEIPT_UNAVAILABLE')
            if not conn.execute('SELECT 1 FROM native_execution_v1 WHERE attempt_id=? AND project_id=?',(aid,project_id)).fetchone():
                raise ImageAssetError(404,'NATIVE_TASK_NOT_FOUND')
        try:
            bundle=NativeTasks(self.service).export_bundle(aid,authorization=dict(
                actor='authenticated-local-client',scope='project-native-test',
                receipt='Explicit authenticated project-scoped bundle export; no rights/quality acceptance'))
        except NativeTaskError:
            raise ImageAssetError(409,'NATIVE_BUNDLE_UNVERIFIED') from None
        public={key:value for key,value in bundle.items() if key!='path'}
        return dict(bundle=public,download_path=f"/api/projects/{project_id}/bundles/{bundle['id']}/versions/{bundle['version_id']}/content")

    def receipt(self,project_id,asset_id,version_id):
        """Read back the receipt this project's delivery was published with.

        Ownership is decided by the asset ledger, not by the receipt row's own
        self-declared ``project_id``: both must name the asking project, and the
        version must still be ACTIVE with a published artifact, so a row written for
        another project can never make one project's document readable from another.

        The document comes back byte-for-byte as stored. It is self-digesting, so no field
        may be added to it on the way out: that is why the rollback resolution lives in
        :meth:`readback` beside it rather than inside it.
        """
        return self._load(project_id,asset_id,version_id)[0]

    def readback(self,project_id,asset_id,version_id):
        """The receipt document, plus what the ledger says about the restores it promises.

        A receipt carries, per deliverable, a ``rollback`` record naming the immutable source
        version the archive was exported from, and the honest sentence about it has always been
        that the record is a plan and no restore has been performed. What was never checked is
        whether the plan still has a target: the reference was printed and believed. This reads
        each one back against ``asset_version`` and reports a state per deliverable.

        The document itself is untouched, so ``receipt_sha256`` still describes the bytes it
        covers. The envelope is where the new fact goes, and the envelope version is bound by
        design-lab/config/contract-bindings.json exactly as the document's is.
        """
        receipt,_digest,summary,proofs=self._load(project_id,asset_id,version_id)
        return {
            'schemaVersion':READBACK_SCHEMA_VERSION,
            'receipt':receipt,
            'rollback_state':summary,
            'rollback_state_vocabulary':list(ROLLBACK_SUMMARIES),
            'rollback_states':list(ROLLBACK_STATES),
            'state_meaning':dict(ROLLBACK_STATE_MEANING),
            'rollback_proofs':proofs,
            'does_not_prove':list(ROLLBACK_DOES_NOT_PROVE),
        }

    def _load(self,project_id,asset_id,version_id):
        """(document, stored digest, rollback summary, proofs) for one bundle version."""
        if self.service.get_project(project_id) is None:
            raise ImageAssetError(404,'PROJECT_NOT_FOUND')
        database=self.service.paths.database_path(self.service.database)
        with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)) as conn:
            try:
                row=conn.execute(RECEIPT_QUERY,(version_id,asset_id,project_id,project_id,version_id)).fetchone()
            except sqlite3.Error:
                raise ImageAssetError(404,'DELIVERY_RECEIPT_NOT_FOUND') from None
            if not row:
                raise ImageAssetError(404,'DELIVERY_RECEIPT_NOT_FOUND')
            try:
                receipt=delivery_receipt.loads(row[0])
            except (InteropError,ValueError):
                raise ImageAssetError(409,'DELIVERY_RECEIPT_UNVERIFIED') from None
            if receipt['receipt_sha256']!=row[1]:
                raise ImageAssetError(409,'DELIVERY_RECEIPT_UNVERIFIED')
            # Resolved inside the same read-only connection: a lookup after `with closing(...)`
            # would have needed a second open of the same database for no benefit.
            summary,proofs=_rollback_or_unreadable(conn,receipt,project_id)
        return receipt,row[1],summary,proofs

    @contextmanager
    def content(self,project_id,asset_id,version_id):
        if self.service.get_project(project_id) is None:
            raise ImageAssetError(404,'PROJECT_NOT_FOUND')
        database=self.service.paths.database_path(self.service.database)
        with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)) as conn:
            rows=conn.execute('SELECT f.path,f.sha256,f.byte_size FROM asset a JOIN asset_version v ON v.asset_id=a.asset_id '
                'JOIN artifact f ON f.version_id=v.version_id WHERE a.project_id=? AND a.asset_id=? '
                "AND a.asset_kind='other' AND v.version_id=? AND v.state='ACTIVE' "
                # The version is pinned, but a version may register more than one file, and
                # this read demands exactly one row: without the preference a delivery that
                # carries a preview answered 404 BUNDLE_NOT_FOUND for a package that exists.
                'AND f.artifact_id=(SELECT g.artifact_id FROM artifact g WHERE g.version_id=v.version_id '
                "ORDER BY CASE g.role WHEN 'deliverable' THEN 0 ELSE 1 END, g.path LIMIT 1)",
                (project_id,asset_id,version_id)).fetchall()
        if len(rows)!=1:raise ImageAssetError(404,'BUNDLE_NOT_FOUND')
        raw_path,expected,size=rows[0]
        try:
            path=self.service.paths.checked_path(raw_path)
            if not path.is_relative_to(self.service.paths.category_dir('projects',project_id,'assets')):
                raise ValueError('wrong artifact owner')
            if path.suffix!='.zip' or not 0<size<=MAX_TOTAL+1024*1024:
                raise ValueError('invalid archive size/type')
            stream=path.open('rb')
            try:
                import os
                before=os.fstat(stream.fileno())
                if before.st_nlink!=1 or before.st_size!=size:raise ValueError('invalid artifact')
                digest=hashlib.file_digest(stream,'sha256').hexdigest()
                after=os.fstat(stream.fileno())
                if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns) or digest!=expected.removeprefix('sha256:'):
                    raise ValueError('archive changed')
                stream.seek(0)
            except BaseException:
                stream.close();raise
        except (OSError,ValueError):
            raise ImageAssetError(409,'BUNDLE_BYTES_UNVERIFIED') from None
        with stream:
            yield stream,size,digest
