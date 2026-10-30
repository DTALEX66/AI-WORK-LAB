# SPDX-License-Identifier: MIT
"""Reversible project-state backups with read-back verification.

The runtime root is gitignored, so anything that lives only there disappears on
the next cleanup or machine move. That is not theoretical: a 2026-10-06 cleanup
removed `task-runtime/service/state.db`, which was the index for 346 asset and
native-plan files that exist nowhere else, and no shadow copy was reachable.

A backup here is a single zip with a manifest of per-file sha256 values, and a
restore re-hashes every file it writes before reporting success. Paths are
sanitised on both sides: an archive cannot write outside the target root, and a
non-empty target is refused unless the caller explicitly overwrites.

Two guarantees the first version did not have, both learned from that incident:

* the archive appears only once it has been read back, and a restore installs
  from a staged copy, so an interrupted run leaves the previous state standing
  rather than half-replaced;
* the state database is snapshotted through SQLite's backup API, so a live
  database is captured as one consistent transaction set -- including anything
  already committed into its WAL -- instead of copying file bytes that may split
  a commit across `state.db` and `state.db-wal`.

What that still does *not* give: a writer that touches the files without ever
recording to the state database is invisible to this barrier. Everything the
product itself publishes does record (the writer lease, the publication journal,
the host guard and the attempt row), so the archive can prove no such writer
moved during the capture -- but the proof is only as good as the record, and a
root whose database carries none of those tables reports
`WRITES_NOT_OBSERVABLE` rather than pretending to be quiet.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

BACKUP_SCHEMA = 'design-lab/project-backup/v1'
MANIFEST_NAME = 'backup-manifest.json'
# The durable product state. Caches, run scratch and evidence logs are excluded
# on purpose: they are regenerable, and including them made archives useless.
DEFAULT_MEMBERS = ('projects', 'task-runtime/service')
# The service state database and the sidecars that belong to it. The database is
# never copied as bytes; it is snapshotted (see _database_snapshot) and the
# sidecars are what that snapshot already folds in, so archiving them separately
# would restore a second, older copy of the same committed rows.
STATE_DATABASE_MEMBER = 'task-runtime/service/state.db'
STATE_DATABASE_SIDECARS = ('task-runtime/service/state.db-wal',
                           'task-runtime/service/state.db-shm')


class BackupError(RuntimeError):
    pass


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _digest_matches(payload: bytes, stored):
    """True/False when the index can be judged, None when it cannot be read.

    The asset store writes digests through `canonical_hash`, which prefixes
    `sha256:` (runtime/attempt_contract.py:10), so a bare-hex comparison against
    real production rows always fails. A value that is neither form is not a
    mismatch -- it is an index this build cannot interpret, and claiming either
    would be a lie in the opposite direction.
    """
    normal = str(stored).strip().removeprefix('sha256:').lower()
    if not re.fullmatch(r'[0-9a-f]{64}', normal):
        return None
    return normal == _sha256_bytes(payload)


def _safe_relative(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise BackupError('backup member paths must be non-empty strings')
    # Checked on the raw string, before PurePosixPath can hide it: on Windows
    # `projects\..\state.db` splits into ONE posix part that contains no '..',
    # and then joins back into two directories, so the part-wise test below would
    # wave it through. ':' is refused for the same reason -- a drive prefix and
    # an NTFS alternate data stream both survive the posix split.
    if '\\' in value or ':' in value:
        raise BackupError(f'path traversal refused in backup member: {value!r}')
    pure = PurePosixPath(value)
    if pure.is_absolute() or (pure.parts and pure.parts[0].endswith(':')):
        raise BackupError(f'absolute backup path refused: {value!r}')
    if any(part in ('', '.', '..') for part in pure.parts):
        raise BackupError(f'path traversal refused in backup member: {value!r}')
    return pure


def _iter_members(local_root: Path, members) -> list[PurePosixPath]:
    found: list[PurePosixPath] = []
    for member in members:
        relative = _safe_relative(member)
        target = local_root.joinpath(*relative.parts)
        if target.is_file():
            found.append(relative)
            continue
        if not target.is_dir():
            raise BackupError(f'backup member is absent: {member}')
        for path in sorted(target.rglob('*')):
            if path.is_file():
                found.append(PurePosixPath(path.relative_to(local_root).as_posix()))
    return sorted(set(found), key=str)


def create_backup(local_root, archive_path, *, members=None,
                  version: str = 'unknown') -> dict:
    """Write a verified archive of the project state and return its manifest.

    The archive is built in a sibling temporary directory and moved into place
    only after it has been read back, so a failure part-way through leaves any
    archive that was already at `archive_path` intact.
    """
    members = DEFAULT_MEMBERS if members is None else tuple(members)
    local_root = Path(local_root).resolve()
    archive_path = Path(archive_path).resolve()
    relatives = _iter_members(local_root, members)
    before = production_state(local_root)
    member_roots = [local_root.joinpath(*_safe_relative(member).parts)
                    for member in members]
    if any(archive_path.is_relative_to(root) for root in member_roots):
        # The zip would be enumerated as a member of itself: _iter_members runs
        # before anything is written, but the file already exists by the time the
        # manifest is hashed, so the archive would carry a partial copy of itself.
        raise BackupError('backup archive must be outside the backed-up members')
    with tempfile.TemporaryDirectory(prefix='design-lab-backup-',
                                     dir=archive_path.parent) as scratch:
        pending = Path(scratch) / 'pending.zip'
        manifest = _write_backup(local_root, pending, relatives, version, Path(scratch),
                                 before)
        verified = verify_backup(pending)
        if verified['fileCount'] != manifest['fileCount']:
            raise BackupError('backup verification count mismatch')
        os.replace(pending, archive_path)
    return verified


def _write_backup(local_root: Path, archive_path: Path, relatives,
                  version: str, scratch: Path, before: dict) -> dict:
    entries = []
    with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in relatives:
            source = local_root.joinpath(*relative.parts)
            if source.is_symlink() or source.resolve() != source:
                raise BackupError(f'linked backup member refused: {relative.as_posix()}')
            posix = relative.as_posix()
            if posix == STATE_DATABASE_MEMBER:
                payload = _database_snapshot(source, scratch)
            elif posix in STATE_DATABASE_SIDECARS:
                continue
            else:
                payload = source.read_bytes()
            entries.append({'path': posix, 'bytes': len(payload),
                            'sha256': _sha256_bytes(payload)})
            archive.writestr(posix, payload)
        # Every byte is captured by this point, so the after-read brackets the copy
        # window. A writer that moved raises here, before the manifest exists, and
        # the pending archive is thrown away with the temporary directory.
        proof = _quiescence_proof(before, production_state(local_root))
        manifest = {
            'schemaVersion': BACKUP_SCHEMA,
            'createdAt': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'designLabVersion': version,
            'projectLocalRootName': local_root.name,
            'productionQuiescence': proof,
            # Restore needs the root the archive came from to tell a relocated
            # artifact or journal path from a foreign one. Without it an archive can
            # only be read back where it was made (see _relocate_artifact_paths and
            # _relocate_publication_journal).
            'sourceLocalRoot': str(local_root),
            'stateSchemaVersion': state_schema_version(local_root),
            'members': entries,
            'fileCount': len(entries),
            'totalBytes': sum(entry['bytes'] for entry in entries),
        }
        archive.writestr(MANIFEST_NAME,
                         json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return manifest


def _database_snapshot(source: Path, scratch: Path) -> bytes:
    """Snapshot a possibly-live database through SQLite's own backup API."""
    snapshot = scratch / 'state.db'
    try:
        with closing(_open_readonly(source)) as live:
            with closing(sqlite3.connect(snapshot)) as destination:
                live.backup(destination)
    except sqlite3.Error as exc:
        raise BackupError(f'state database cannot be snapshotted: {exc}') from None
    return snapshot.read_bytes()


# What production writes leave behind in the state database. A backup is only
# cross-file consistent if none of it moved while the files were being copied.
ACTIVITY_QUERIES = (
    # (label, table, sql, row -> identity)
    ('PREPARED_PUBLICATION', 'asset_publication',
     "SELECT publication_id, asset_id FROM asset_publication WHERE state='PREPARED'"
     " ORDER BY publication_id",
     lambda row: f'{row[0]}#{row[1]}'),
    ('HOST_GUARD', 'native_host_guard_v1',
     "SELECT host, attempt_id FROM native_host_guard_v1 ORDER BY host",
     lambda row: f'{row[0]}#{row[1]}'),
    ('NON_TERMINAL_ATTEMPT', 'attempt_state',
     "SELECT attempt_id, state FROM attempt_state WHERE state IN"
     " ('PENDING','RUNNING','CANCEL_REQUESTED','RECONCILING','OUTCOME_UNKNOWN')"
     " ORDER BY attempt_id",
     lambda row: f'{row[0]}#{row[1]}'),
)

# The writer lease is judged in Python, not in SQL, and deliberately so:
# `expires_at` holds a unix float (asset_store._expiry -> time.time()), while
# `acquire_writer` additionally treats a legacy HELD row with NO expiry as
# blocking. Comparing either of those in SQL is how a busy root gets read as
# quiet -- a REAL expiry compared against a TEXT now is always "less", so every
# live lease would look expired. The store's own predicates are the truth here.
LEASE_SELECT = ("SELECT resource_key, holder_attempt_id, generation, state, expires_at"
                " FROM asset_writer_lock ORDER BY resource_key")

# Counters that only ever grow. They catch the publication that starts AND
# finishes inside the capture window: both reads then show an empty activity set,
# yet bytes moved -- a set difference alone would call that consistent.
COUNTER_QUERIES = (
    ('asset_publication', 'rowid'),
    ('asset_version', 'rowid'),
    ('artifact', 'rowid'),
    ('attempt_event', 'event_no'),
    ('asset_writer_lock', 'generation'),
    # A signed human record takes no writer lease -- jury_store.record() and
    # quality_store.record() commit straight through -- so a lease check cannot see
    # one land. Without these two rows a backup window that swallowed a verdict in
    # flight would still report PROVED_QUIESCENT, and the archive that "proved" nothing
    # moved would be missing the attestation the project cites later.
    ('jury_record', 'rowid'),
    ('quality_record', 'rowid'),
    # The rest of the tables production writes without holding a lease. Each was
    # measured, not guessed: design-lab/tests/test_backup_watches_written_tables.py
    # derives the written set from the shipped INSERTs and refuses either direction of
    # disagreement, so a new store cannot be added while the proof stays blind to it.
    ('project', 'rowid'),
    ('asset', 'rowid'),
    ('approval', 'rowid'),
    ('audit_event', 'rowid'),
    ('job', 'rowid'),
    ('job_attempt', 'rowid'),
    ('operation_intent', 'rowid'),
    ('rights_decision', 'rowid'),
    # 2026-10-08: research_store.record() commits a finding with no writer lease either, so a
    # backup window that swallowed one in flight would otherwise still report PROVED_QUIESCENT.
    ('research_finding', 'rowid'),
    # 2026-10-19 T16/U09: knowledge_feedback.py files a candidate and a revocation straight
    # through, with no writer lease, so the proof cannot see either land without these rows.
    ('knowledge_candidate', 'rowid'),
    ('knowledge_revocation', 'rowid'),
    # 2026-10-20: ModelSelection.record() appends a choice with no writer lease, and the row is
    # immutable (the no-update/no-delete triggers make the revision itself the record), so a backup
    # window that swallowed one would otherwise still report PROVED_QUIESCENT while the decision
    # path the operator reads back had moved.
    ('model_selection', 'rowid'),
    # 2026-10-22: PromptResults.store() and .review() both append without a writer lease, and the
    # rows are immutable by trigger. Without these two the proof would report PROVED_QUIESCENT over a
    # window that swallowed a stored prompt or a signature in flight -- and a signature is exactly the
    # kind of row the project gets asked to cite later.
    ('prompt_result', 'rowid'),
    ('prompt_result_review', 'rowid'),
    # 2026-10-23 DL-KB-02: knowledge_library writes three tables with no writer lease -- the
    # entry identity row, its append-only revisions, and the derived-index receipt. A backup
    # window that swallowed an entry (or its replacement revision) would otherwise still
    # report PROVED_QUIESCENT while the library the operator reads back had moved.
    ('knowledge_entry', 'rowid'),
    ('knowledge_entry_revision', 'rowid'),
    ('knowledge_index_state', 'rowid'),
    # 2026-10-24 DL-KB-05 D5: a recorded judgement (recommendation moved back, source marked dead)
    # is appended with no writer lease. It changes what the library answers as recommended without
    # touching a revision row, so a proof blind to this table could call a window quiescent while
    # the pointer every plan reads had moved.
    ('knowledge_judgement', 'rowid'),
    # 2026-10-24 DL-KB-07: the assistance plan store writes its identity row, its
    # append-only revisions and the recorded choice with no writer lease. A backup
    # window that swallowed a revision or a named-human choice would otherwise still
    # report PROVED_QUIESCENT while the plan the page reads back had moved.
    ('assistance_plan', 'rowid'),
    ('assistance_plan_revision', 'rowid'),
    ('assistance_plan_choice', 'rowid'),
    # 2026-10-24 DL-KB-09: a draft target profile is written with no writer lease. The five seeded
    # profiles live in the tracked config and cannot move at runtime, but a draft somebody adds at
    # the selection panel can land inside a backup window -- and the panel reads it back later as
    # the registry's own record of what the operator claimed.
    ('target_profile_draft', 'rowid'),
    # 2026-10-24 DL-KB-16: a voluntary external-use report is committed with no writer lease. A
    # backup window that swallowed one would otherwise still report PROVED_QUIESCENT while the
    # experience record the 我的方案 screen reads back had moved -- and this is the row people cite
    # later about whether material actually worked somewhere else.
    ('plan_feedback', 'rowid'),
)


def production_state(local_root: Path) -> dict:
    """Read the write activity the state database records, without touching it.

    `observable` is False when the database carries none of the tables that
    record writers. That is not the same statement as "nothing is running", and
    an archive must not convert one into the other.
    """
    database = local_root.joinpath(*PurePosixPath(STATE_DATABASE_MEMBER).parts)
    if not database.is_file():
        return {'state': 'NO_STATE_DATABASE', 'observable': False, 'activity': [],
                'counters': {}, 'tables_observed': []}
    try:
        with closing(_open_readonly(database)) as conn:
            return _read_activity(conn)
    except sqlite3.Error:
        # A database this build cannot read proves only that writers cannot be
        # observed, not that none are running. Say so, and let the snapshot step
        # fail closed with its own precise reason.
        return {'state': 'STATE_DATABASE_UNREADABLE', 'observable': False,
                'activity': [], 'counters': {}, 'tables_observed': []}


def _read_activity(conn) -> dict:
    from .asset_store import _expiration, _lease_live
    tables = {row[0] for row in
              conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    activity = []
    if 'asset_writer_lock' in tables:
        for resource, *lease in conn.execute(LEASE_SELECT).fetchall():
            # HELD with a live expiry, or legacy HELD with no expiry at all --
            # both block acquire_writer, so both block a backup.
            if _lease_live(lease) or (lease[2] == 'HELD' and _expiration(lease) is None):
                activity.append(f'LIVE_WRITER_LOCK:{resource}#{lease[0]}+{lease[1]}')
    for label, table, sql, identity in ACTIVITY_QUERIES:
        if table not in tables:
            continue
        activity += [f'{label}:{identity(row)}' for row in conn.execute(sql).fetchall()]
    counters = {}
    for table, column in COUNTER_QUERIES:
        if table not in tables:
            continue
        count, total = conn.execute(
            f'SELECT COUNT(*), COALESCE(SUM({column}), 0) FROM {table}').fetchone()
        counters[table] = [int(count), int(total)]
    writer_tables = {'asset_writer_lock'} | {table for _, table, _, _ in ACTIVITY_QUERIES}
    observed = sorted((({table for table, _ in COUNTER_QUERIES} | writer_tables) & tables))
    return {'state': ('WRITES_NOT_OBSERVABLE' if not observed
                      else 'BUSY' if activity else 'PROVED_QUIESCENT'),
            'observable': bool(observed), 'activity': sorted(activity),
            'counters': counters, 'tables_observed': list(observed)}


def _quiescence_proof(before: dict, after: dict) -> dict:
    """Refuse when a writer was live or moved; otherwise record what was proved."""
    if not before['observable']:
        return {'state': before['state'], 'tablesObserved': before['tables_observed'],
                'activityBefore': before['activity'], 'activityAfter': after['activity'],
                'countersBefore': before['counters'], 'countersAfter': after['counters']}
    if before['activity']:
        raise BackupError('production write in flight before backup: '
                          + ';'.join(before['activity']))
    if after['activity']:
        raise BackupError('production write in flight during backup: '
                          + ';'.join(after['activity']))
    if before['counters'] != after['counters']:
        moved = ';'.join(
            f'{key}:{before["counters"].get(key)}->{after["counters"].get(key)}'
            for key in sorted(set(before['counters']) | set(after['counters']))
            if before['counters'].get(key) != after['counters'].get(key))
        raise BackupError(f'production write moved during the backup window: {moved}')
    return {'state': 'PROVED_QUIESCENT', 'tablesObserved': before['tables_observed'],
            'activityBefore': [], 'activityAfter': [],
            'countersBefore': before['counters'], 'countersAfter': after['counters']}


def _manifest_of(archive_path: Path) -> dict:
    if not archive_path.is_file():
        raise BackupError(f'backup archive is absent: {archive_path.name}')
    with zipfile.ZipFile(archive_path) as archive:
        try:
            raw = archive.read(MANIFEST_NAME)
        except KeyError:
            raise BackupError('archive carries no backup manifest') from None
    manifest = json.loads(raw.decode('utf-8'))
    if manifest.get('schemaVersion') != BACKUP_SCHEMA:
        raise BackupError(f"unsupported backup schema: {manifest.get('schemaVersion')!r}")
    return manifest


def verify_backup(archive_path) -> dict:
    """Re-hash every archived file against the manifest; raise on any mismatch."""
    archive_path = Path(archive_path).resolve()
    manifest = _manifest_of(archive_path)
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        for entry in manifest['members']:
            relative = _safe_relative(entry['path']).as_posix()
            if relative not in names:
                raise BackupError(f'archive is missing member {relative}')
            digest = _sha256_bytes(archive.read(relative))
            if digest != entry['sha256']:
                raise BackupError(f'archive member hash mismatch: {relative}')
    return manifest


def state_schema_version(local_root) -> int | None:
    """Read the SQLite schema version of the service state database, if present."""
    database = Path(local_root).joinpath(*PurePosixPath('task-runtime/service/state.db').parts)
    if not database.is_file():
        return None
    try:
        # sqlite3.connect opens the file, so an unreadable database raises here too.
        with closing(_open_readonly(database)) as connection:
            row = connection.execute('PRAGMA user_version').fetchone()
    except sqlite3.Error:
        # A database this build cannot open reports no version, which skips the
        # comparison rather than pretending it passed.
        return None
    return None if row is None else int(row[0])


def _open_readonly(database: Path):
    # as_uri(), not an f-string: a '#' in the path is a URI fragment, and an
    # unencoded one makes SQLite open some other file and answer PRAGMA with the
    # default 0 -- a wrong version that would silently pass the compatibility gate.
    return sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)


def compatibility(manifest: dict, *, version: str = 'unknown',
                  local_state_schema_version: int | None = None) -> dict:
    """Say whether an archive may be restored into this build.

    An archive from a newer design-lab or a newer state schema can carry rows
    this build cannot interpret, so a mismatch is reported instead of being
    silently unpacked. The caller decides whether to override with
    `allow_upgrade`.
    """
    reasons = []
    archived = manifest.get('stateSchemaVersion')
    if local_state_schema_version is not None:
        if archived is None:
            reasons.append('ARCHIVE_RECORDS_NO_STATE_SCHEMA')
        elif int(archived) != int(local_state_schema_version):
            reasons.append(f'STATE_SCHEMA_MISMATCH:archive={archived}'
                           f':local={local_state_schema_version}')
    archived_version = str(manifest.get('designLabVersion', ''))
    if version != 'unknown' and archived_version and archived_version != version:
        reasons.append(f'VERSION_MISMATCH:archive={archived_version}:local={version}')
    return {'compatible': not reasons, 'reasons': reasons,
            'archiveVersion': archived_version or None,
            'archiveStateSchemaVersion': archived}


def restore_backup(archive_path, target_local_root, *, force: bool = False,
                   allow_upgrade: bool = False, version: str = 'unknown',
                   local_state_schema_version: int | None = None) -> dict:
    """Unpack a verified archive under `target_local_root` and re-read every hash."""
    archive_path = Path(archive_path).resolve()
    target = Path(target_local_root).resolve()
    manifest = verify_backup(archive_path)
    check = compatibility(manifest, version=version,
                          local_state_schema_version=local_state_schema_version)
    if not check['compatible'] and not allow_upgrade:
        raise BackupError('backup is not compatible with this build: '
                          + ','.join(check['reasons']))
    if target.exists() and any(target.rglob('*')) and not force:
        raise BackupError(f'target root is not empty (pass force to overwrite): {target.name}')
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='design-lab-restore-',
                                     dir=target.parent) as scratch:
        staged = Path(scratch) / 'staged'
        previous = Path(scratch) / 'previous'
        restored = 0
        with zipfile.ZipFile(archive_path) as archive:
            for entry in manifest['members']:
                relative = _safe_relative(entry['path'])
                destination = staged.joinpath(*relative.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(relative.as_posix()))
                if _sha256_bytes(destination.read_bytes()) != entry['sha256']:
                    raise BackupError(f'restored hash mismatch: {relative.as_posix()}')
                restored += 1
        # Rebase the live indexes while they are still the staged copy, so the
        # bytes that go on disk already point at where the files will be.
        artifacts = _relocate_artifact_paths(staged, manifest, destination_root=target)
        journal = _relocate_publication_journal(staged, manifest, destination_root=target)
        relocated = artifacts['relocated']
        target.mkdir(parents=True, exist_ok=True)
        installed = []
        try:
            for entry in manifest['members']:
                relative = _safe_relative(entry['path'])
                destination = target.joinpath(*relative.parts)
                if destination.is_symlink() or destination.resolve() != destination:
                    raise BackupError(f'linked restore destination refused: '
                                      f'{relative.as_posix()}')
                destination.parent.mkdir(parents=True, exist_ok=True)
                old = previous.joinpath(*relative.parts)
                had_previous = destination.exists()
                if had_previous:
                    old.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(destination, old)
                # Recorded before the move: if the move itself is the failure,
                # the rollback still knows this path was freshly created.
                installed.append((destination, old, had_previous))
                os.replace(staged.joinpath(*relative.parts), destination)
        except BaseException:
            for destination, old, had_previous in reversed(installed):
                if had_previous:
                    os.replace(old, destination)
                elif destination.exists():
                    destination.unlink()
            raise
    return {'schemaVersion': BACKUP_SCHEMA, 'restored': restored,
            'relocatedArtifactPaths': relocated,
            # The crash journal travels too: its four path columns are filesystem
            # coordinates, and a PREPARED row left pointing at the archived root
            # is one recovery can never see (see _relocate_publication_journal).
            'relocatedPublicationPaths': journal['relocated'],
            'publicationJournalRows': journal['rows'],
            'artifactsHashVerified': artifacts['verified'],
            'artifactsUnverifiable': artifacts['unverifiable'],
            # Carried through from the archive: the backup either proved no writer
            # moved, or it says plainly that it could not look.
            'productionQuiescence': manifest.get('productionQuiescence', {}).get(
                'state', 'ARCHIVE_RECORDS_NO_QUIESCENCE'),
            # Signed execution history is deliberately not rewritten; a host
            # plan made under another root has to be replanned, not repointed.
            'nativeExecutionRecovery': 'REPLAN_REQUIRED_AFTER_RELOCATION'
                                       if relocated or journal['relocated']
                                       else 'UNCHANGED',
            'totalBytes': manifest['totalBytes'],
            'createdAt': manifest['createdAt'], 'verified': True,
            'compatibility': check}


def _relocate_artifact_paths(root, manifest, *, destination_root=None):
    """Rebase the live artifact index and prove it matches the archived bytes.

    `root` is the staged copy of the local root; `destination_root` is where it
    will live once installed. Two things are checked, not one:

    * every absolute artifact row must resolve to a file the archive actually
      carries -- a database that indexes a byte nobody backed up is the failure
      this whole module exists to prevent, so it is refused here rather than
      restored and discovered later;
    * where the row records a sha256, the archived bytes must match it. That is
      the assertion which proves the database and the files beside it agree. A
      row without a digest, or with a relative path this code cannot resolve the
      way the store does, is counted as unverifiable instead of passing.
    """
    database = root / 'task-runtime/service/state.db'
    if not database.is_file():
        return {'relocated': 0, 'verified': 0, 'unverifiable': 0}
    destination_root = Path(root) if destination_root is None else Path(destination_root)
    source_root = manifest.get('sourceLocalRoot')
    with closing(sqlite3.connect(database)) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                           "AND name='artifact'").fetchone():
            return {'relocated': 0, 'verified': 0, 'unverifiable': 0}
        relocated = verified = unverifiable = 0
        for rowid, value, digest in conn.execute(
                'SELECT rowid, path, sha256 FROM artifact').fetchall():
            original = Path(value)
            if not original.is_absolute():
                # Relative rows are resolved by the store against its own root,
                # so they travel with the archive unchanged -- but nothing here can
                # prove the bytes beside them, so they are counted, never passed.
                unverifiable += 1
                continue
            if source_root is None:
                # An archive made before sourceLocalRoot existed carries no origin,
                # so a cross-root restore cannot be verified -- say so instead of
                # reporting success over paths that still point at the old machine.
                if not original.is_relative_to(destination_root):
                    raise BackupError(
                        'legacy archive records no source root; artifact paths still '
                        f'point outside the restore target: {value}')
                unverifiable += 1
                continue
            source = Path(source_root)
            if not original.is_relative_to(source):
                raise BackupError(f'artifact path is outside the archived local root: {value}')
            relative = original.relative_to(source)
            staged_file = Path(root) / relative
            if not staged_file.is_file():
                raise BackupError(f'restored artifact is absent: {relative.as_posix()}')
            if digest:
                outcome = _digest_matches(staged_file.read_bytes(), digest)
                if outcome is False:
                    raise BackupError('restored artifact hash does not match the index: '
                                      f'{relative.as_posix()}')
                if outcome is None:
                    unverifiable += 1
                else:
                    verified += 1
            else:
                unverifiable += 1
            destination = destination_root / relative
            if destination != original:
                conn.execute('UPDATE artifact SET path = ? WHERE rowid = ?',
                             (str(destination), rowid))
                relocated += 1
        conn.commit()
        return {'relocated': relocated, 'verified': verified, 'unverifiable': unverifiable}


# `asset_publication` columns that are filesystem coordinates and nothing else.
# Every other column in the row is identity or verdict, and is never rewritten.
PUBLICATION_PATH_COLUMNS = ('store_root', 'stage_path', 'final_path', 'quarantine_path')
# Journal states product code reads back: PREPARED is the half-made publication
# `asset_store.recover_publications` selects on (`WHERE store_root=? AND
# state='PREPARED'`), COMMITTED is the row `asset_store.publish_version` re-reads
# for its idempotency check and `_check_path`s against the store root it was handed.
JOURNAL_STATES_READ_BACK = ('PREPARED', 'COMMITTED')


def _relocate_publication_journal(root, manifest, *, destination_root=None):
    """Rebase the publication journal's path columns into the restore target.

    WHY THIS IS THE SAFE FORM. `asset_publication` is the crash journal
    `publish_version` writes before it renames, and `recover_publications` reads it
    back with `WHERE store_root=? AND state='PREPARED'`. The four columns here are
    pure filesystem coordinates, so the same rebase the artifact index already gets
    applies to them: left archived-stale, the new root's recovery selects nothing
    and the in-flight publication is neither recovered nor reported, while a
    COMMITTED row makes `publish_version` raise 'publication path escapes store
    root' over bytes that are in fact sitting beside the index. Selecting by
    identity instead -- dropping the `store_root=?` predicate -- would widen every
    live root's recovery to rows belonging to other stores, so the journal text is
    corrected and the predicate is not.

    Only path data is rewritten. `state`, `sha256`, `holder_attempt_id`,
    `generation`, `version_id`, `publication_id`, `asset_id` and `created_at` stay
    exactly as archived: they are the fenced writer's verdict and identity, and
    re-dating or re-fencing a journal row would launder a claim this root never
    made. Nothing here claims the journal's bytes are proven either -- a PREPARED
    row may hold a partial staged copy by design (recovery quarantines it, or
    reports MISSING), so no digest is re-checked here; the artifact index is where
    `_relocate_artifact_paths` proves bytes against digests.

    What this deliberately does NOT touch:
    * `native_host_guard_v1` -- it carries no path column, and its claim is
      non-expiring on purpose ('Host guards deliberately never expire',
      native_tasks.py). Clearing, re-dating or re-keying a restored guard would let
      a second writer share a host the archived attempt may still be holding.
    * `native_execution_v1` and the attempt/operation state -- signed execution
      records, never rewritten per the standing owner ruling; that is why the
      receipt reports REPLAN_REQUIRED_AFTER_RELOCATION instead of repointing them.

    A journal row naming a path outside the archived local root is refused, exactly
    as an artifact row naming one is: it indexes bytes nobody backed up.
    """
    database = Path(root) / 'task-runtime/service/state.db'
    if not database.is_file():
        return {'relocated': 0, 'rows': 0}
    destination_root = Path(root) if destination_root is None else Path(destination_root)
    source_root = manifest.get('sourceLocalRoot')
    with closing(sqlite3.connect(database)) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                           "AND name='asset_publication'").fetchone():
            return {'relocated': 0, 'rows': 0}
        relocated = rows = 0
        selected = ', '.join(PUBLICATION_PATH_COLUMNS)
        for rowid, state, *paths in conn.execute(
                f'SELECT rowid, state, {selected} FROM asset_publication').fetchall():
            rows += 1
            if source_root is None:
                # No origin recorded, so a moved path cannot be told from a foreign
                # one. A row that product code still has to read back is then a
                # publication this restore can never make recoverable, and the
                # honest answer is to refuse, not to report a clean restore.
                if state in JOURNAL_STATES_READ_BACK:
                    stored = Path(paths[0])
                    if stored.is_absolute() and not stored.is_relative_to(destination_root):
                        raise BackupError(
                            'legacy archive records no source root; its '
                            f'{state} publication journal still names a store outside '
                            f'the restore target, so it cannot be recovered here: '
                            f'{paths[0]}')
                continue
            source = Path(source_root)
            updates = []
            for column, value in zip(PUBLICATION_PATH_COLUMNS, paths):
                original = Path(value)
                if not original.is_absolute():
                    # The store always writes absolute paths; anything else travels
                    # as it is rather than being guessed at.
                    continue
                if not original.is_relative_to(source):
                    raise BackupError(f'publication journal {column} is outside the '
                                      f'archived local root: {value}')
                moved = destination_root / original.relative_to(source)
                if str(moved) != value:
                    updates.append((str(moved), column))
            if updates:
                # Column names come from PUBLICATION_PATH_COLUMNS, never from data.
                conn.execute('UPDATE asset_publication SET '
                             + ', '.join(f'{column} = ?' for _, column in updates)
                             + ' WHERE rowid = ?',
                             tuple(value for value, _ in updates) + (rowid,))
                relocated += 1
        conn.commit()
        return {'relocated': relocated, 'rows': rows}
