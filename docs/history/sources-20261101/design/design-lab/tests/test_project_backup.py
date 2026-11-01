# SPDX-License-Identifier: MIT
"""Backup/restore contract tests, including the CLI path (E2 controlled runtime).

A restore is only worth anything if it refuses to write where it should not and
if it re-reads what it wrote. These cover both, plus a real subprocess round trip
through `design-lab ... backup` / `restore`.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
import types
import unittest
import zipfile

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))

from design_lab.runtime.project_backup import (  # noqa: E402
    MANIFEST_NAME, BackupError, create_backup, restore_backup, state_schema_version,
    verify_backup)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _rewrite_manifest(archive, destination, *, drop=()):
    """Re-pack a real archive with keys removed from its manifest.

    Used to make an archive that looks like it came from an older build, rather
    than asserting against a hand-written one that no build ever produced.
    """
    with zipfile.ZipFile(archive) as source:
        manifest = json.loads(source.read(MANIFEST_NAME).decode('utf-8'))
        blobs = [(info.filename, source.read(info.filename))
                 for info in source.infolist() if info.filename != MANIFEST_NAME]
    for key in drop:
        manifest.pop(key, None)
    with zipfile.ZipFile(destination, 'w') as out:
        for name, payload in blobs:
            out.writestr(name, payload)
        out.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return manifest


def _synthetic_archive(destination, members):
    """Write an archive whose manifest lists `members` = {stored name: bytes}."""
    with zipfile.ZipFile(destination, 'w') as out:
        out.writestr(MANIFEST_NAME, json.dumps({
            'schemaVersion': 'design-lab/project-backup/v1',
            'createdAt': '2026-10-06T00:00:00Z', 'designLabVersion': 'test',
            'projectLocalRootName': 'x', 'fileCount': len(members),
            'totalBytes': sum(len(p) for p in members.values()),
            'members': [{'path': name, 'bytes': len(payload),
                         'sha256': _sha(payload)} for name, payload in members.items()],
        }, indent=2) + '\n')
        for name, payload in members.items():
            out.writestr(name, payload)


def _state_root(parent: Path) -> Path:
    local = parent / '.project-local'
    (local / 'projects' / 'p1' / 'assets' / 'versions' / 'v1').mkdir(parents=True)
    (local / 'projects' / 'p1' / 'assets' / 'versions' / 'v1' / 'native.psd').write_bytes(
        b'PSD-bytes-not-a-real-one' * 7)
    (local / 'projects' / 'p1' / 'state-marker.json').write_text(
        json.dumps({'id': 'p1', 'name': 'Backup Probe'}), encoding='utf-8')
    (local / 'task-runtime' / 'service').mkdir(parents=True)
    import sqlite3
    connection = sqlite3.connect(local / 'task-runtime' / 'service' / 'state.db')
    connection.execute('PRAGMA user_version = 7')
    connection.execute('CREATE TABLE marker (id text primary key, name text)')
    connection.execute("INSERT INTO marker VALUES ('p1', 'Backup Probe')")
    connection.commit()
    connection.close()
    return local


class ProjectBackupTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        self.local = _state_root(self.base)
        self.archive = self.base / 'backup.zip'

    def test_backup_lists_every_state_file_and_verifies(self):
        manifest = create_backup(self.local, self.archive)
        self.assertEqual(manifest['fileCount'], 3)
        self.assertEqual(manifest['schemaVersion'], 'design-lab/project-backup/v1')
        checked = verify_backup(self.archive)
        self.assertEqual(checked['fileCount'], 3)
        self.assertGreater(checked['totalBytes'], 0)

    def test_restore_round_trip_reproduces_every_hash(self):
        create_backup(self.local, self.archive)
        target = self.base / 'restored'
        receipt = restore_backup(self.archive, target)
        self.assertTrue(receipt['verified'])
        self.assertEqual(receipt['restored'], 3)
        with zipfile.ZipFile(self.archive) as archive:
            for entry in verify_backup(self.archive)['members']:
                archived = hashlib.sha256(archive.read(entry['path'])).hexdigest()
                restored = hashlib.sha256(target.joinpath(
                    *entry['path'].split('/')).read_bytes()).hexdigest()
                self.assertEqual(archived, restored, entry['path'])
                if entry['path'] != 'task-runtime/service/state.db':
                    # Every other member is a byte copy of the live file, so the
                    # archive-restored-source chain has to close for it.
                    source = hashlib.sha256(self.local.joinpath(
                        *entry['path'].split('/')).read_bytes()).hexdigest()
                    self.assertEqual(source, restored, entry['path'])
        # The database is deliberately not a byte copy: it comes out of SQLite's
        # backup API, whose header (change counter) differs from the live file.
        # What must survive is the database as an answerable database, so that is
        # what is read back here instead of a hash of bytes that were never equal.
        with closing(sqlite3.connect(target / 'task-runtime/service/state.db')) as conn:
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 7)
            self.assertEqual([row[0] for row in conn.execute('SELECT name FROM marker')],
                             ['Backup Probe'])

    def test_wal_commits_are_in_the_database_snapshot(self):
        """Committed-in-WAL rows survive, which a raw file copy would drop.

        The connection is left open across the backup on purpose: SQLite
        checkpoints and removes the WAL when the last connection closes, so a
        test that closed first would pass even with a byte-for-byte copy.
        """
        with closing(sqlite3.connect(self.local / 'task-runtime' / 'service' / 'state.db')) as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute("INSERT INTO marker VALUES ('wal', 'Committed in WAL')")
            conn.commit()
            self.assertTrue((self.local / 'task-runtime' / 'service' / 'state.db-wal').is_file(),
                            'the fixture must leave the commit in the WAL, not in state.db')
            create_backup(self.local, self.archive)
        target = self.base / 'wal-restored'
        restore_backup(self.archive, target)
        with closing(sqlite3.connect(target / 'task-runtime' / 'service' / 'state.db')) as restored:
            self.assertEqual(
                restored.execute("SELECT name FROM marker WHERE id='wal'").fetchone(),
                ('Committed in WAL',))
        # The sidecars are folded into the snapshot, not archived beside it: a
        # restored state.db plus an older -wal would replay stale frames over it.
        self.assertFalse((target / 'task-runtime' / 'service' / 'state.db-wal').is_file())
        self.assertFalse((target / 'task-runtime' / 'service' / 'state.db-shm').is_file())

    def test_backup_inside_its_own_members_is_refused(self):
        """An archive written under a member is enumerated as a member of itself."""
        with self.assertRaisesRegex(BackupError, 'outside the backed-up members'):
            create_backup(self.local, self.local / 'projects' / 'backup.zip')

    def test_interrupted_write_leaves_the_previous_archive_byte_for_byte(self):
        from unittest.mock import patch
        from design_lab.runtime import project_backup
        create_backup(self.local, self.archive)
        previous = self.archive.read_bytes()

        def interrupt(*args, **kwargs):
            raise OSError('synthetic interrupted write')

        with patch.object(project_backup, '_database_snapshot', side_effect=interrupt):
            with self.assertRaises(OSError):
                create_backup(self.local, self.archive)
        self.assertEqual(self.archive.read_bytes(), previous)

    def test_unsnapshottable_database_produces_no_archive(self):
        broken = _state_root(self.base / 'broken-local')
        (broken / 'task-runtime' / 'service' / 'state.db').write_bytes(b'not a database')
        destination = self.base / 'broken.zip'
        with self.assertRaisesRegex(BackupError, 'cannot be snapshotted'):
            create_backup(broken, destination)
        self.assertFalse(destination.exists(),
                         'a half-built archive is worse than no archive')

    def test_restore_install_failure_rolls_back_previous_files(self):
        from unittest.mock import patch
        from design_lab.runtime import project_backup
        create_backup(self.local, self.archive)
        target = self.base / 'occupied-rollback'
        old = target / 'projects' / 'p1' / 'assets' / 'versions' / 'v1' / 'native.psd'
        old.parent.mkdir(parents=True)
        old.write_bytes(b'previous asset')
        real_replace = os.replace

        def interrupted(source, destination):
            if 'staged' in Path(source).parts and Path(destination).name == 'state.db':
                raise OSError('synthetic interrupted restore')
            return real_replace(source, destination)

        with patch.object(project_backup, 'os', types.SimpleNamespace(replace=interrupted)):
            with self.assertRaisesRegex(OSError, 'interrupted'):
                restore_backup(self.archive, target, force=True)
        self.assertEqual(old.read_bytes(), b'previous asset',
                         'a file that was replaced before the failure must come back')
        self.assertFalse((target / 'projects' / 'p1' / 'state-marker.json').exists(),
                         'a file installed before the failure must be withdrawn')
        self.assertFalse((target / 'task-runtime' / 'service' / 'state.db').exists())

    def test_backslash_member_cannot_escape_the_target(self):
        """PurePosixPath does not split on backslash, so the raw string is checked.

        Measured rather than assumed, in three parts, because the obvious demo
        hides the defect: Python's own zipfile rewrites `\\` to `/` when it stores
        a name, so a hand-built archive cannot carry the escape -- an archive from
        any other tool can. The guard is the only thing refusing it, so the guard
        and the sink are both asserted here, not just the end-to-end refusal.
        """
        from design_lab.runtime.project_backup import _safe_relative
        escaping = 'projects\\..\\..\\escaped.txt'
        with self.assertRaisesRegex(BackupError, 'traversal'):
            _safe_relative(escaping)
        # The sink: what would happen if the guard let a shape through. Which shape that
        # is depends on the platform's own separator, so it is named per platform and the
        # claim is asserted on both. On Windows a single accepted posix part
        # `projects\..\..\escaped.txt` resolves two directories up, because `\` is a
        # separator there. On POSIX backslash is an ordinary filename character, so that
        # same string cannot escape and the escape arrives as explicit `..` parts instead.
        root = self.base / 'sink-root'
        self.assertEqual(len(PurePosixPath(escaping).parts), 1,
                         'the backslash member is a single posix part, which is what hides it')
        posix_escape = 'projects/../../escaped.txt'
        joined = root.joinpath(*PurePosixPath(posix_escape).parts)
        self.assertFalse(joined.resolve().is_relative_to(root.resolve()),
                         f'{posix_escape!r} accepted as parts still resolves outside the root')
        if os.sep == '\\':
            native = root.joinpath(PurePosixPath(escaping).parts[0])
            self.assertFalse(native.resolve().is_relative_to(root.resolve()),
                             'a single accepted part still resolves outside the root on Windows')
        create_backup(self.local, self.archive)
        evil = self.base / 'backslash.zip'
        _synthetic_archive(evil, {'projects\\..\\escaped.txt': b'evil'})
        with self.assertRaisesRegex(BackupError, 'traversal'):
            restore_backup(evil, self.base / 'bs-target')
        self.assertFalse((self.base / 'escaped.txt').exists())

    def test_state_schema_version_reads_a_hash_in_the_path(self):
        """A '#' in the runtime root is a URI fragment, not a filename character.

        `f'file:{path}?mode=ro'` truncates there and answers the PRAGMA from some
        other file: measured on this machine it reported version 0 for a database
        whose real version was 7, which would have steered the compatibility gate
        with a wrong number instead of failing.
        """
        local = _state_root(self.base / 'shaped#root')
        self.assertEqual(state_schema_version(local), 7)

    def test_linked_backup_member_is_refused(self):
        try:
            target = self.base / 'linked-member-target'
            target.write_bytes(b'outside the archive')
            link = self.local / 'projects' / 'linked.psd'
            link.symlink_to(target)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f'ENVIRONMENT_FAIL: native symlink creation unavailable: {exc}')
        with self.assertRaisesRegex(BackupError, 'linked backup member refused'):
            create_backup(self.local, self.archive)

    def test_tampered_member_is_refused(self):
        create_backup(self.local, self.archive)
        evil = self.base / 'evil.zip'
        with zipfile.ZipFile(self.archive) as source, zipfile.ZipFile(evil, 'w') as out:
            for item in source.infolist():
                payload = source.read(item.filename)
                if item.filename.endswith('native.psd'):
                    payload = b'tampered'
                out.writestr(item, payload)
        with self.assertRaisesRegex(BackupError, 'hash mismatch'):
            verify_backup(evil)
        with self.assertRaisesRegex(BackupError, 'hash mismatch'):
            restore_backup(evil, self.base / 'never-written')
        self.assertFalse((self.base / 'never-written' / 'projects').exists())

    def test_traversal_member_in_manifest_cannot_escape_the_target(self):
        create_backup(self.local, self.archive)
        evil = self.base / 'traversal.zip'
        with zipfile.ZipFile(evil, 'w') as out:
            out.writestr('backup-manifest.json', json.dumps({
                'schemaVersion': 'design-lab/project-backup/v1',
                'createdAt': '2026-10-06T00:00:00Z', 'designLabVersion': 'test',
                'projectLocalRootName': 'x', 'fileCount': 1, 'totalBytes': 4,
                'members': [{'path': '../escaped.txt', 'bytes': 4,
                             'sha256': hashlib.sha256(b'evil').hexdigest()}],
            }))
            out.writestr('escaped.txt', b'evil')
        with self.assertRaisesRegex(BackupError, 'traversal'):
            restore_backup(evil, self.base / 'target')
        self.assertFalse((self.base / 'escaped.txt').exists())

    def test_non_empty_target_needs_explicit_overwrite(self):
        create_backup(self.local, self.archive)
        target = self.base / 'occupied'
        (target / 'projects').mkdir(parents=True)
        (target / 'projects' / 'existing.json').write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(BackupError, 'not empty'):
            restore_backup(self.archive, target)
        receipt = restore_backup(self.archive, target, force=True)
        self.assertEqual(receipt['restored'], 3)

    def test_archive_records_the_state_schema_version(self):
        manifest = create_backup(self.local, self.archive)
        self.assertEqual(manifest['stateSchemaVersion'], 7)

    def test_state_schema_mismatch_refuses_restore_unless_overridden(self):
        create_backup(self.local, self.archive)
        with self.assertRaisesRegex(BackupError, 'STATE_SCHEMA_MISMATCH:archive=7:local=8'):
            restore_backup(self.archive, self.base / 'blocked',
                           local_state_schema_version=8)
        receipt = restore_backup(self.archive, self.base / 'allowed',
                                 local_state_schema_version=8, allow_upgrade=True)
        self.assertEqual(receipt['restored'], 3)
        self.assertFalse(receipt['compatibility']['compatible'])

    def test_unreadable_database_reports_no_version_instead_of_passing(self):
        from design_lab.runtime.project_backup import state_schema_version
        broken = self.base / 'broken-local'
        (broken / 'task-runtime' / 'service').mkdir(parents=True)
        (broken / 'task-runtime' / 'service' / 'state.db').write_bytes(b'not a database')
        self.assertIsNone(state_schema_version(broken))


class RelocationTests(unittest.TestCase):
    """Restoring into a different root has to point the index at the moved bytes.

    The 2026-10-06 loss was an index that no longer matched the files; a restore
    that rewrites paths without checking them, or checks them and still claims
    success, recreates that failure in a new shape.
    """

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        self.local = _state_root(self.base)
        self.archive = self.base / 'backup.zip'
        self.db = self.local / 'task-runtime' / 'service' / 'state.db'

    def _artifact_row(self, stored_path, artifact_id='a1'):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS artifact ('
                         'artifact_id TEXT PRIMARY KEY, version_id TEXT, path TEXT NOT NULL,'
                         ' sha256 TEXT, byte_size INTEGER, role TEXT NOT NULL)')
            conn.execute('INSERT INTO artifact (artifact_id, version_id, path, role)'
                         ' VALUES (?,?,?,?)', (artifact_id, 'v1', str(stored_path), 'deliverable'))
            conn.commit()

    def _row_path(self, database):
        with closing(sqlite3.connect(database)) as conn:
            return conn.execute('SELECT path FROM artifact').fetchone()[0]

    def test_relocated_artifact_index_reads_the_restored_bytes(self):
        original = self.local / 'projects/p1/assets/versions/v1/native.psd'
        self._artifact_row(original)
        create_backup(self.local, self.archive)
        target = self.base / 'moved'
        receipt = restore_backup(self.archive, target)
        self.assertEqual(receipt['relocatedArtifactPaths'], 1)
        self.assertEqual(receipt['nativeExecutionRecovery'], 'REPLAN_REQUIRED_AFTER_RELOCATION')
        relocated = Path(self._row_path(target / 'task-runtime/service/state.db'))
        self.assertTrue(relocated.is_relative_to(target), str(relocated))
        self.assertTrue(relocated.is_file(), 'the index must point at a file that exists')
        self.assertEqual(relocated.read_bytes(), original.read_bytes())

    def test_restoring_into_the_original_root_relocates_nothing(self):
        original = self.local / 'projects/p1/assets/versions/v1/native.psd'
        self._artifact_row(original)
        create_backup(self.local, self.archive)
        receipt = restore_backup(self.archive, self.local, force=True)
        self.assertEqual(receipt['relocatedArtifactPaths'], 0)
        self.assertEqual(receipt['nativeExecutionRecovery'], 'UNCHANGED')
        self.assertEqual(Path(self._row_path(self.db)), original)

    def test_relative_artifact_paths_travel_unchanged(self):
        self._artifact_row('projects/p1/assets/versions/v1/native.psd')
        create_backup(self.local, self.archive)
        target = self.base / 'relative'
        receipt = restore_backup(self.archive, target)
        self.assertEqual(receipt['relocatedArtifactPaths'], 0)
        self.assertEqual(self._row_path(target / 'task-runtime/service/state.db'),
                         'projects/p1/assets/versions/v1/native.psd')

    def test_artifact_row_naming_unarchived_bytes_refuses_the_restore(self):
        """A database that indexes a file the archive does not carry is not restorable."""
        loose = self.local / 'task-artifacts' / 'loose.psd'
        loose.parent.mkdir(parents=True)
        loose.write_bytes(b'outside every member')
        self._artifact_row(loose)
        create_backup(self.local, self.archive)
        with self.assertRaisesRegex(BackupError, 'restored artifact is absent'):
            restore_backup(self.archive, self.base / 'moved')

    def test_artifact_row_outside_the_archived_root_refuses_the_restore(self):
        foreign = self.base / 'somewhere-else.psd'
        foreign.write_bytes(b'not under the local root')
        self._artifact_row(foreign)
        create_backup(self.local, self.archive)
        with self.assertRaisesRegex(BackupError, 'outside the archived local root'):
            restore_backup(self.archive, self.base / 'moved')

    def test_legacy_archive_without_a_source_root_refuses_a_cross_root_restore(self):
        """An older archive records no origin, so a moved restore cannot be proven."""
        original = self.local / 'projects/p1/assets/versions/v1/native.psd'
        self._artifact_row(original)
        create_backup(self.local, self.archive)
        legacy = self.base / 'legacy.zip'
        _rewrite_manifest(self.archive, legacy, drop=('sourceLocalRoot',))
        self.assertNotIn('sourceLocalRoot', verify_backup(legacy))
        with self.assertRaisesRegex(BackupError, 'records no source root'):
            restore_backup(legacy, self.base / 'moved')

    def test_legacy_archive_still_restores_where_it_was_made(self):
        original = self.local / 'projects/p1/assets/versions/v1/native.psd'
        self._artifact_row(original)
        create_backup(self.local, self.archive)
        legacy = self.base / 'legacy-local.zip'
        _rewrite_manifest(self.archive, legacy, drop=('sourceLocalRoot',))
        receipt = restore_backup(legacy, self.local, force=True)
        self.assertEqual(receipt['relocatedArtifactPaths'], 0)

    def test_real_image_import_survives_project_relocation(self):
        """The whole product path, not the archive plumbing: import → back up → move."""
        import base64
        import io
        from unittest.mock import patch
        from PIL import Image
        from design_lab.image_assets import ImageAssets
        from design_lab.service import ProjectService
        with patch.dict(os.environ):
            os.environ.pop('PROJECT_LOCAL_ROOT', None)
            owner = self.base / 'source-owner'
            owner.mkdir()
            (owner / 'AGENTS.md').write_text('# synthetic backup fixture', encoding='utf-8')
            service = ProjectService(owner)
            project = service.create_project('Image restore fixture')['id']
            stream = io.BytesIO()
            Image.new('RGB', (12, 8), 'green').save(stream, format='PNG')
            encoded = base64.b64encode(stream.getvalue()).decode()
            ImageAssets(service).import_image(project, encoded, 'backup-image')

            create_backup(owner / '.project-local', self.archive)
            recovered_owner = self.base / 'recovered-owner'
            recovered_owner.mkdir()
            (recovered_owner / 'AGENTS.md').write_text('# synthetic restored fixture',
                                                       encoding='utf-8')
            restore_backup(self.archive, recovered_owner / '.project-local')

            images = ImageAssets(ProjectService(recovered_owner))
            assets = images.list(project)
            self.assertEqual(len(assets), 1)
            self.assertEqual(images.content(project, assets[0]['id'])['content_base64'], encoded)


def _tracked_ddl(table):
    """Pull one CREATE TABLE statement out of the place the product declares it.

    The barrier reads the product's own tables, so the fixtures must create those
    exact tables. Re-declaring columns here would let a test pass against a schema
    the product never writes. Two of them (the host guard, the recovery protocol)
    are declared inside native_tasks.py rather than a .sql file, so both sources
    are searched and an unfound table fails the test instead of being invented.
    """
    sources = sorted((REPO / 'design-lab/schemas/state').glob('*.sql')) + [
        REPO / 'src/design_lab/native_tasks.py']
    for path in sources:
        match = re.search(rf"CREATE TABLE (?:IF NOT EXISTS )?{table}\b.*?\n\s*\);",
                          path.read_text(encoding='utf-8'), re.S)
        if match:
            return match.group(0)
    raise AssertionError(f'{table} is not declared by any tracked schema or DDL string')


ACTIVITY_TABLES = ('asset', 'asset_version', 'artifact', 'asset_writer_lock',
                   'asset_publication', 'attempt_state', 'native_host_guard_v1',
                   'jury_record', 'quality_record')


def _activity_root(parent: Path) -> Path:
    """A state root whose database carries the tables production writes through."""
    local = _state_root(parent)
    conn = sqlite3.connect(local / 'task-runtime/service/state.db')
    try:
        conn.execute('CREATE TABLE project (project_id TEXT PRIMARY KEY,'
                     ' display_name TEXT NOT NULL, created_at TEXT NOT NULL)')
        for table in ACTIVITY_TABLES:
            conn.execute(_tracked_ddl(table))
        conn.execute('INSERT INTO project VALUES ("p1","Activity Probe","2026-10-08T00:00:00Z")')
        conn.execute('INSERT INTO asset VALUES ("a1","p1","psd","2026-10-08T00:00:00Z")')
        conn.commit()
    finally:
        conn.close()
    return local


def _insert_artifact(local: Path, stored_path, digest):
    with closing(sqlite3.connect(local / 'task-runtime/service/state.db')) as conn:
        conn.execute('INSERT INTO asset_version (version_id, asset_id, version_no,'
                     ' content_sha256, state, created_at)'
                     ' VALUES ("v1","a1",1,?,"ACTIVE","2026-10-08T00:00:00Z")',
                     (digest or 'sha256:' + 'a' * 64,))
        conn.execute('INSERT INTO artifact (artifact_id, version_id, path, sha256,'
                     ' byte_size, role) VALUES ("art1","v1",?,?,10,"deliverable")',
                     (str(stored_path), digest))
        conn.commit()


def _publication_row(local: Path, publication_id, state, holder='attempt-1', *, root=None):
    root = Path(local) / 'projects/p1/assets' if root is None else Path(root)
    with closing(sqlite3.connect(local / 'task-runtime/service/state.db')) as conn:
        conn.execute('INSERT INTO asset_publication VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                     (publication_id, 'a1', str(root), str(root / 'staging'),
                      str(root / 'versions'), str(root / 'quarantine'),
                      'sha256:' + 'b' * 64, holder, 1, state, None,
                      '2026-10-08T00:00:00Z'))
        conn.commit()


class WriteCoordinationTests(unittest.TestCase):
    """A backup is cross-file consistent only if no writer moved during the window.

    The barrier reads what production itself records: the per-asset writer lease,
    the publication journal, the host guard and the attempt row. Fixtures go
    through those real writers (`asset_store.acquire_writer`, `publish_version` and
    its crash seam) rather than hand-inserted rows, so the test proves the product's
    own state is what the gate looks at.
    """

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        self.local = _activity_root(self.base)
        self.db = self.local / 'task-runtime/service/state.db'
        self.archive = self.base / 'backup.zip'

    def _publish_lease(self, resource='asset:a1', holder='attempt-1', lease=60):
        from design_lab.runtime import asset_store as assets
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertTrue(assets.acquire_writer(conn, resource, holder,
                                                 lease_seconds=lease))
            conn.commit()
            return assets.writer_token(conn, resource, holder)

    def test_backup_refuses_while_a_real_lease_is_held(self):
        self._publish_lease()
        with self.assertRaisesRegex(BackupError, 'LIVE_WRITER_LOCK'):
            create_backup(self.local, self.archive)
        self.assertFalse(self.archive.exists(),
                         'a refused backup must not leave an archive behind')

    def test_a_lease_that_expired_is_not_counted_as_live(self):
        """An expired lease fences its holder out of every remaining DB step."""
        from unittest.mock import patch
        from design_lab.runtime import asset_store
        self._publish_lease()
        with patch.object(asset_store, '_clock',
                          return_value=asset_store._clock() + 120):
            manifest = create_backup(self.local, self.archive)
        self.assertEqual(manifest['productionQuiescence']['state'], 'PROVED_QUIESCENT')

    def test_a_legacy_held_lease_without_expiry_blocks(self):
        """`acquire_writer` refuses to treat a missing expiry as executable.

        The row is inserted directly because no current writer creates it: it is
        the pre-expiry-schema shape the store still honours, and a barrier that
        ignored it would back up over a lease the product itself respects.
        """
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("INSERT INTO asset_writer_lock (resource_key, holder_attempt_id,"
                         " generation, state, acquired_at, expires_at)"
                         " VALUES ('asset:a1','attempt-legacy',1,'HELD',"
                         "'2026-10-08T00:00:00Z',NULL)")
            conn.commit()
        with self.assertRaisesRegex(BackupError, 'LIVE_WRITER_LOCK'):
            create_backup(self.local, self.archive)

    def test_backup_refuses_over_a_prepared_publication(self):
        """Crash the real publisher between stage and commit, then try to back up.

        The lease is released explicitly afterwards, because that is what the
        caller does and not the publisher: `publish_version` never calls
        `release_writer` (image_assets.py:131 owns the `finally`). Releasing it
        here isolates the journal -- otherwise the lease alone blocks the backup
        and this test would prove nothing about PREPARED rows.
        """
        from unittest.mock import patch
        from design_lab.runtime import asset_store as assets
        generation = self._publish_lease(holder='attempt-9')
        source = self.base / 'incoming.psd'
        source.write_bytes(b'publication in flight')
        digest = 'sha256:' + hashlib.sha256(source.read_bytes()).hexdigest()
        root = self.local / 'projects/p1/assets'
        with closing(sqlite3.connect(self.db)) as conn:
            with patch.object(assets, '_after_stage',
                              side_effect=OSError('stopped between stage and commit')):
                with self.assertRaises(OSError):
                    assets.publish_version(conn, 'a1', source, store_root=root,
                                          artifact_name='native.psd',
                                          expected_sha256=digest,
                                          holder_attempt_id='attempt-9',
                                          generation=generation)
            assets.release_writer(conn, 'asset:a1', 'attempt-9', generation=generation)
            conn.commit()
            prepared = conn.execute("SELECT COUNT(*) FROM asset_publication"
                                    " WHERE state='PREPARED'").fetchone()[0]
        self.assertEqual(prepared, 1, 'the fixture must leave exactly one half-made publication')
        with self.assertRaisesRegex(BackupError, 'PREPARED_PUBLICATION'):
            create_backup(self.local, self.archive)

    def test_a_publication_that_completes_inside_the_window_is_detected(self):
        """The blind spot: nothing is live in either read, yet a row appeared."""
        from unittest.mock import patch
        from design_lab.runtime import project_backup
        create_backup(self.local, self.archive)
        original = project_backup._database_snapshot
        moved = []

        def publish_during_snapshot(source, scratch):
            payload = original(source, scratch)
            _publication_row(self.local, 'pub-fast', 'COMMITTED')
            moved.append(True)
            return payload

        second = self.base / 'second.zip'
        with patch.object(project_backup, '_database_snapshot',
                          side_effect=publish_during_snapshot):
            with self.assertRaisesRegex(BackupError, 'moved during the backup window'):
                create_backup(self.local, second)
        self.assertTrue(moved, 'the fixture must actually have written inside the window')
        self.assertFalse(second.exists(), 'a window that moved must not produce an archive')

    def test_host_guard_and_running_attempt_both_block(self):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute('INSERT INTO attempt_state VALUES (?,?,?,?,?,?,?)',
                         ('at-1', 'job-1', 1, 'RUNNING', '2026-10-08T00:00:00Z', None, None))
            conn.commit()
        with self.assertRaisesRegex(BackupError, 'NON_TERMINAL_ATTEMPT'):
            create_backup(self.local, self.archive)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("DELETE FROM attempt_state WHERE attempt_id='at-1'")
            conn.execute('INSERT INTO attempt_state VALUES (?,?,?,?,?,?,?)',
                         ('at-2', 'job-2', 1, 'RECEIPTED', '2026-10-08T00:00:00Z',
                          '2026-10-08T00:00:01Z', None))
            conn.execute('INSERT INTO native_host_guard_v1 VALUES (?,?,?)',
                         ('illustrator', 'at-2', '2026-10-08T00:00:00Z'))
            conn.commit()
        with self.assertRaisesRegex(BackupError, 'HOST_GUARD'):
            create_backup(self.local, self.archive)

    def test_quiet_root_records_the_proof_and_restore_echoes_it(self):
        manifest = create_backup(self.local, self.archive)
        proof = manifest['productionQuiescence']
        self.assertEqual(proof['state'], 'PROVED_QUIESCENT')
        self.assertIn('asset_writer_lock', proof['tablesObserved'])
        self.assertEqual(proof['countersBefore'], proof['countersAfter'])
        receipt = restore_backup(self.archive, self.base / 'restored')
        self.assertEqual(receipt['productionQuiescence'], 'PROVED_QUIESCENT')

    def test_a_human_record_written_inside_the_window_is_not_read_as_quiet(self):
        """A verdict takes no lease, so the counters are the only witness it moved."""
        from design_lab.runtime import project_backup
        from unittest.mock import patch
        first = project_backup.production_state(self.local)
        self.assertEqual(first['state'], 'PROVED_QUIESCENT')
        self.assertIn('jury_record', first['counters'],
                      'a table the backup does not count is a table it cannot see move')
        self.assertIn('quality_record', first['counters'])

        original = project_backup._database_snapshot

        def sign_during_snapshot(source, scratch):
            payload = original(source, scratch)
            with closing(sqlite3.connect(self.db)) as conn:
                conn.execute('INSERT INTO jury_record (jury_record_id, kind, project_id,'
                             ' subject_ref, artifact_sha256, verdict, juror_id, juror_kind,'
                             ' attestation, document_json, decided_at)'
                             ' VALUES ("jury-window-1","JURY_VERDICT","p1","version:v1",'
                             '"sha256:" || ?,"APPROVE","dtalex66","HUMAN",'
                             '"reviewed at 100%","{}","2026-10-08T00:00:00Z")',
                             ('0' * 64,))
                conn.commit()
            return payload

        second = self.base / 'human-in-window.zip'
        with patch.object(project_backup, '_database_snapshot',
                          side_effect=sign_during_snapshot):
            with self.assertRaisesRegex(BackupError, 'moved during the backup window'):
                create_backup(self.local, second)
        self.assertFalse(second.exists(),
                         'a window that swallowed a signature must not produce an archive')

    def test_a_root_that_cannot_observe_writers_says_so_and_stays_said(self):
        """The plain fixture database has no writer tables: that is not "quiet"."""
        plain = _state_root(self.base / 'plain')
        manifest = create_backup(plain, self.base / 'plain.zip')
        self.assertEqual(manifest['productionQuiescence']['state'], 'WRITES_NOT_OBSERVABLE')
        self.assertEqual(manifest['productionQuiescence']['tablesObserved'], [])
        receipt = restore_backup(self.base / 'plain.zip', self.base / 'plain-restored')
        self.assertEqual(receipt['productionQuiescence'], 'WRITES_NOT_OBSERVABLE',
                         'a restore may not upgrade an unproven backup into a proof')

    def test_a_root_with_no_database_reports_no_database(self):
        bare = self.base / 'bare'
        (bare / 'projects').mkdir(parents=True)
        (bare / 'projects' / 'note.txt').write_text('no state db yet', encoding='utf-8')
        (bare / 'task-runtime' / 'service').mkdir(parents=True)
        manifest = create_backup(bare, self.base / 'bare.zip')
        self.assertEqual(manifest['productionQuiescence']['state'], 'NO_STATE_DATABASE')

    def test_restore_proves_the_index_against_the_archived_bytes(self):
        asset = self.local / 'projects/p1/assets/versions/v1/native.psd'
        digest = hashlib.sha256(asset.read_bytes()).hexdigest()
        _insert_artifact(self.local, str(asset), digest)
        create_backup(self.local, self.archive)
        receipt = restore_backup(self.archive, self.base / 'proven')
        self.assertEqual(receipt['artifactsHashVerified'], 1)
        self.assertEqual(receipt['artifactsUnverifiable'], 0)

    def test_restore_refuses_an_index_that_lies_about_the_bytes(self):
        asset = self.local / 'projects/p1/assets/versions/v1/native.psd'
        _insert_artifact(self.local, str(asset), '0' * 64)
        create_backup(self.local, self.archive)
        with self.assertRaisesRegex(BackupError, 'hash does not match the index'):
            restore_backup(self.archive, self.base / 'refused')

    def test_a_row_without_a_digest_is_counted_not_passed(self):
        asset = self.local / 'projects/p1/assets/versions/v1/native.psd'
        _insert_artifact(self.local, str(asset), None)
        create_backup(self.local, self.archive)
        receipt = restore_backup(self.archive, self.base / 'partial')
        self.assertEqual(receipt['artifactsHashVerified'], 0)
        self.assertEqual(receipt['artifactsUnverifiable'], 1)


def _owner_root(parent: Path, name: str) -> Path:
    """A real project owner: the AGENTS.md marker `resolve_paths` demands."""
    owner = parent / name
    owner.mkdir(parents=True)
    (owner / 'AGENTS.md').write_text('# synthetic publication fixture', encoding='utf-8')
    return owner


def _barrier_blind_to(*labels):
    """Write an archive the CURRENT quiescence barrier would refuse to produce.

    `create_backup` blocks on a PREPARED journal row and on a host-guard row --
    both are in `project_backup.ACTIVITY_QUERIES` -- so this build cannot put
    either into an archive. An archive made by a build whose barrier did not look
    at that table carries whatever the journal held, though, and the restore is the
    side that has to survive it. Only the named labels are hidden, and only while
    the archive is being built: the restore, the recovery and the host claim under
    test all run on unpatched product code.
    """
    from unittest.mock import patch
    from design_lab.runtime import project_backup
    kept = tuple(entry for entry in project_backup.ACTIVITY_QUERIES
                 if entry[0] not in labels)
    if len(kept) == len(project_backup.ACTIVITY_QUERIES):
        raise AssertionError(f'no barrier label named {labels}')
    return patch.object(project_backup, 'ACTIVITY_QUERIES', kept)


class PublicationJournalTests(unittest.TestCase):
    """A crash journal has to survive being restored under a different root.

    `asset_store.recover_publications` selects
    `WHERE store_root=? AND state='PREPARED'`, and the restore only ever rebased
    the artifact index, so a journal row that travelled into a new root stayed
    pointing at the old one: the new root's recovery selected nothing and returned
    an empty list -- neither recovered nor missing, just quiet. Same row, same
    bytes, same store.
    """

    def setUp(self):
        from unittest.mock import patch
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        self.environment = patch.dict(os.environ)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        os.environ.pop('PROJECT_LOCAL_ROOT', None)
        self.owner = _owner_root(self.base, 'jo')
        # Windows caps a plain path at 260 characters and a restore creates
        # <owner>/.project-local/.../staged/projects/<32 hex>/assets/staging/<64 hex>
        # below its target, so the fixture's OWN labels are the only part of that chain
        # this test controls -- they are kept short, and the remaining budget is asserted
        # here instead of being discovered as an opaque WinError 206 on a deeper checkout.
        # Measured: these cases pass in the primary tree and failed at 276 characters in a
        # nested git worktree until the labels were shortened.
        self.assertLess(len(str(self.base)) + len('jo/.project-local/task-runtime/service'),
                        200, f'fixture root is already {len(str(self.base))} chars deep at '
                             f'{self.base}: shorten the checkout path, because no label here '
                             'can recover that budget')
        self.local = self.owner / '.project-local'
        self.db = self.local / 'task-runtime' / 'service' / 'state.db'
        self.archive = self.base / 'journal.zip'
        from design_lab.service import ProjectService
        self.service = ProjectService(self.owner)
        self.project = self.service.create_project('Journal restore fixture')['id']
        self.store = self.service.paths.category_dir('projects', self.project, 'assets')

    def _recovered_owner(self, name='jr'):
        return _owner_root(self.base, name)

    def _member_bytes(self):
        """One real file under `projects`, so the archive has a member to carry."""
        member = self.local / 'projects' / self.project / 'assets' / 'journal-fixture.txt'
        member.parent.mkdir(parents=True, exist_ok=True)
        member.write_bytes(b'journal fixture bytes')
        return member

    def _journal_verdict(self, database):
        """The columns that are identity or verdict, never path data."""
        with closing(sqlite3.connect(database)) as conn:
            return conn.execute('SELECT publication_id, asset_id, state, sha256,'
                                ' holder_attempt_id, generation, version_id, created_at'
                                ' FROM asset_publication').fetchall()

    def _recovered_store(self, recovered):
        """The store root exactly as the product computes it for recovery."""
        from design_lab.service import ProjectService
        return ProjectService(recovered).paths.category_dir('projects', self.project,
                                                            'assets')

    def _crash_a_publication(self, *, release=True):
        """Publish through the product and die between stage and commit.

        Returns (digest, staged_file). `publish_version` never releases
        the lease -- the caller does (image_assets.py:131) -- so releasing it here
        is what leaves a journal row for the archive rather than a live writer.
        """
        from unittest.mock import patch
        from design_lab.runtime import asset_store as assets
        source = self.base / 'incoming.psd'
        source.write_bytes(b'publication bytes that never committed' * 5)
        digest = 'sha256:' + hashlib.sha256(source.read_bytes()).hexdigest()
        with closing(sqlite3.connect(self.db)) as conn:
            assets.register_asset(conn, self.project, 'a1', 'psd')
            self.assertTrue(assets.acquire_writer(conn, 'asset:a1', 'attempt-crash',
                                                  lease_seconds=60))
            generation = assets.writer_token(conn, 'asset:a1', 'attempt-crash')
            with patch.object(assets, '_after_stage',
                              side_effect=OSError('stopped between stage and commit')):
                with self.assertRaises(OSError):
                    assets.publish_version(conn, 'a1', source, store_root=self.store,
                                           artifact_name='native.psd',
                                           expected_sha256=digest,
                                           holder_attempt_id='attempt-crash',
                                           generation=generation,
                                           project_root=self.owner)
            if release:
                assets.release_writer(conn, 'asset:a1', 'attempt-crash',
                                      generation=generation)
            conn.commit()
            staged = conn.execute("SELECT stage_path FROM asset_publication"
                                  " WHERE state='PREPARED'").fetchone()[0]
        return digest, Path(staged)

    def test_prepared_publication_from_the_archive_is_recovered_in_the_new_root(self):
        digest, staged = self._crash_a_publication()
        self.assertTrue(staged.is_file(), 'the fixture must leave the half-made bytes')
        before = self._journal_verdict(self.db)
        with _barrier_blind_to('PREPARED_PUBLICATION'):
            manifest = create_backup(self.local, self.archive)
        self.assertTrue(any('/staging/' in entry['path'] for entry in manifest['members']),
                        'the staged bytes have to travel in the archive')

        recovered = self._recovered_owner()
        target = recovered / '.project-local'
        restored_db = target / 'task-runtime/service/state.db'
        receipt = restore_backup(self.archive, target)
        with closing(sqlite3.connect(restored_db)) as conn:
            rebased = conn.execute('SELECT store_root, stage_path, final_path,'
                                   ' quarantine_path FROM asset_publication').fetchone()
        # Read before recovery runs: recovery is entitled to rewrite `state`, and
        # nothing else, so the verdict has to be judged while only the restore has
        # had its hand on the row.
        verdict_after_restore = self._journal_verdict(restored_db)

        # The claim itself, in the order that matters: the product's own recovery,
        # run against the new root the way `native_tasks` runs it, has to find the
        # row. Pre-fix this returned [] -- the row was neither recovered nor
        # reported, only quiet.
        from design_lab.runtime import asset_store as assets
        restored_store = self._recovered_store(recovered)
        with closing(sqlite3.connect(restored_db)) as conn:
            recovered_rows = assets.recover_publications(conn, store_root=restored_store,
                                                         project_root=recovered)
        self.assertEqual([row['state'] for row in recovered_rows], ['QUARANTINED'],
                         'an archived PREPARED row must be recovered, not skipped')
        # The recovery was handed exactly what this build computes for the new
        # owner's asset category (native_tasks.py:161), and it reached the row: so
        # the stored text has to be that same path, not merely some path in it.
        self.assertEqual(rebased[0], str(restored_store),
                         'the rebased store root must be what this build computes')
        quarantined = Path(recovered_rows[0]['path'])
        self.assertEqual(quarantined, Path(rebased[3]))
        self.assertTrue(quarantined.is_relative_to(target))
        self.assertEqual('sha256:' + hashlib.sha256(quarantined.read_bytes()).hexdigest(),
                         digest, 'recovery must quarantine the bytes that really travelled')
        self.assertFalse(Path(rebased[1]).exists(),
                         'recovery moved the restored staging copy, not some other file')
        self.assertTrue(staged.is_file(),
                        'a restore must leave the root it came from alone')

        # Then what the restore itself reports, and what it refused to touch.
        self.assertEqual(receipt['relocatedPublicationPaths'], 1,
                         'the archived journal row must have been rebased into the target')
        self.assertEqual(receipt['relocatedArtifactPaths'], 0,
                         'a PREPARED row has no artifact row; only the journal moved')
        self.assertEqual(receipt['nativeExecutionRecovery'], 'REPLAN_REQUIRED_AFTER_RELOCATION')
        self.assertEqual(verdict_after_restore, before,
                         'a restore fixes path columns only; the verdict travels')
        for stored in rebased:
            self.assertTrue(Path(stored).is_relative_to(target),
                            f'{stored} still names the root it was archived from')
            self.assertFalse(Path(stored).is_relative_to(self.local),
                             f'{stored} was not rebased out of the source root')

    def test_committed_journal_path_is_rebased_so_identical_bytes_return_the_version(self):
        """The same gap on a row this build can archive: COMMITTED final_path.

        `publish_version` re-reads a COMMITTED row for its idempotency check and
        `_check_path`s the stored final path against the root it was handed. Left
        archived-stale, re-publishing bytes that are genuinely present raises
        'publication path escapes store root'.
        """
        from design_lab.runtime import asset_store as assets
        source = self.base / 'c.psd'
        source.write_bytes(b'fully published bytes' * 4)
        digest = 'sha256:' + hashlib.sha256(source.read_bytes()).hexdigest()
        with closing(sqlite3.connect(self.db)) as conn:
            assets.register_asset(conn, self.project, 'a2', 'psd')
            assets.acquire_writer(conn, 'asset:a2', 'attempt-ok', lease_seconds=60)
            generation = assets.writer_token(conn, 'asset:a2', 'attempt-ok')
            version = assets.publish_version(conn, 'a2', source, store_root=self.store,
                                             artifact_name='native.psd',
                                             expected_sha256=digest,
                                             holder_attempt_id='attempt-ok',
                                             generation=generation,
                                             project_root=self.owner)
            assets.release_writer(conn, 'asset:a2', 'attempt-ok', generation=generation)
            conn.commit()
        create_backup(self.local, self.archive)

        recovered = self._recovered_owner('cr')
        target = recovered / '.project-local'
        receipt = restore_backup(self.archive, target)

        # The claim first: re-publishing the very same bytes into the restored root
        # must resolve to the version that already exists, not error over a journal
        # row that still names the root the archive came from.
        restored_store = self._recovered_store(recovered)
        with closing(sqlite3.connect(target / 'task-runtime/service/state.db')) as conn:
            assets.register_asset(conn, self.project, 'a2', 'psd')
            assets.acquire_writer(conn, 'asset:a2', 'attempt-again', lease_seconds=60)
            again = assets.writer_token(conn, 'asset:a2', 'attempt-again')
            try:
                returned = assets.publish_version(conn, 'a2', source,
                                                  store_root=restored_store,
                                                  artifact_name='native.psd',
                                                  expected_sha256=digest,
                                                  holder_attempt_id='attempt-again',
                                                  generation=again,
                                                  project_root=recovered)
            finally:
                assets.release_writer(conn, 'asset:a2', 'attempt-again', generation=again)
            versions = conn.execute('SELECT COUNT(*) FROM asset_version').fetchone()[0]
        self.assertEqual(returned, version,
                         'the same bytes must resolve to the version already published')
        self.assertEqual(versions, 1, 'no second version row may be minted for the same bytes')
        self.assertEqual(receipt['relocatedPublicationPaths'], 1,
                         'the committed journal row must have been rebased into the target')

    def test_legacy_archive_with_an_unrecoverable_prepared_row_refuses_the_restore(self):
        """No recorded origin means no honest rebase: refuse, do not report clean."""
        self._crash_a_publication()
        with _barrier_blind_to('PREPARED_PUBLICATION'):
            create_backup(self.local, self.archive)
        legacy = self.base / 'lj.zip'
        _rewrite_manifest(self.archive, legacy, drop=('sourceLocalRoot',))
        target = self.base / 'lt'
        with self.assertRaisesRegex(BackupError, 'cannot be recovered here'):
            restore_backup(legacy, target / 'recovery')
        self.assertFalse((target / 'recovery' / 'task-runtime').exists(),
                         'a refused restore must not leave a half-restored root behind')
        # Same archive, same root it came from: the journal rows already live where
        # they point, so the refusal is about the move and not about the row.
        receipt = restore_backup(legacy, self.local, force=True)
        self.assertEqual(receipt['relocatedPublicationPaths'], 0)

    def test_journal_row_naming_bytes_outside_the_archived_root_refuses_the_restore(self):
        """A journal row indexing bytes nobody backed up is not restorable.

        The artifact index already answers this way (`_relocate_artifact_paths`
        refuses an artifact path outside the archived local root); the journal is
        the second index of the same bytes and gets the same answer, because a
        rebase that happily rewrote a foreign path would be pointing recovery at
        bytes outside the restore it is supposed to be making.
        """
        self._member_bytes()
        foreign = self.base / 'elsewhere' / 'assets'
        _publication_row(self.local, 'pub-foreign', 'PREPARED', root=foreign)
        with _barrier_blind_to('PREPARED_PUBLICATION'):
            create_backup(self.local, self.archive)
        with self.assertRaisesRegex(BackupError,
                                    'publication journal store_root is outside'):
            restore_backup(self.archive,
                           self.base / 'foreign-target' / '.project-local')
        self.assertFalse((self.base / 'foreign-target' / '.project-local').exists(),
                         'a refused restore must not leave a half-restored root behind')

    def test_archived_host_guard_is_never_relocated_or_revived(self):
        """The guard has no path column, so the journal rebase must leave it alone.

        'Not revived' is asserted both ways: the archived claim travels verbatim --
        no refreshed `acquired_at`, no re-keyed attempt, no deleted row -- and the
        restored project still cannot claim that host for a new attempt, because a
        guard cleared or re-dated by a restore would let a second writer share a
        host the archived attempt may still be holding.
        """
        from unittest.mock import patch
        from design_lab.runtime import job_store as jobs
        from design_lab.runtime.attempt_contract import request_hash
        self._member_bytes()
        # Every row here goes in through the product's own stores, so the archived
        # database is one the product could have written -- including the attempt
        # the guard points at, which the restored root needs present to judge it.
        with closing(jobs.connect(self.db, project_root=self.owner)) as conn:
            conn.execute(_tracked_ddl('native_host_guard_v1'))
            claimed = jobs.begin_attempt(conn, 'job-guard', operation_id='op-guard',
                                         idempotency_scope='native:p1:illustrator',
                                         idempotency_key='guard-claim',
                                         request_hash=request_hash({'host': 'illustrator'}))
            archived = ('illustrator', claimed['attempt_id'], '2026-10-08T00:00:00Z')
            conn.execute('INSERT INTO native_host_guard_v1 VALUES (?,?,?)', archived)
            conn.commit()
            archived_attempt = conn.execute(
                'SELECT attempt_id, job_id, attempt_no, state, started_at, ended_at, note'
                ' FROM attempt_state').fetchone()
        _publication_row(self.local, 'pub-alongside-guard', 'PREPARED')
        with _barrier_blind_to('PREPARED_PUBLICATION', 'HOST_GUARD', 'NON_TERMINAL_ATTEMPT'):
            create_backup(self.local, self.archive)

        recovered = self._recovered_owner('gr')
        target = recovered / '.project-local'
        receipt = restore_backup(self.archive, target)
        self.assertEqual(receipt['relocatedPublicationPaths'], 1,
                         'the journal rebase must really have run on this database')
        restored = target / 'task-runtime' / 'service' / 'state.db'
        with closing(sqlite3.connect(restored)) as conn:
            self.assertEqual(conn.execute('SELECT host, attempt_id, acquired_at'
                                          ' FROM native_host_guard_v1').fetchall(),
                             [archived],
                             'the guard travels verbatim: not cleared, not re-dated,'
                             ' not re-keyed to an attempt this root made')
            self.assertEqual(conn.execute(
                'SELECT attempt_id, job_id, attempt_no, state, started_at, ended_at, note'
                ' FROM attempt_state').fetchone(), archived_attempt,
                'signed attempt state is never rewritten by a restore')
        # Through the product's own claim path: a fresh attempt in the restored
        # root is refused the host, so nothing was absorbed, cleared or re-issued.
        from design_lab.native_tasks import NativeTasks, NativeTaskError
        from design_lab.service import ProjectService
        with patch.dict(os.environ):
            os.environ.pop('PROJECT_LOCAL_ROOT', None)
            tasks = NativeTasks(ProjectService(recovered))
            with closing(tasks._connect()) as conn:
                attempt = jobs.begin_attempt(conn, 'job-guard-check',
                                             operation_id='op-guard-check',
                                             idempotency_scope='native:p1:illustrator',
                                             idempotency_key='guard-check',
                                             request_hash=request_hash({'host': 'illustrator',
                                                                        'project': 'p1'}))
                with self.assertRaisesRegex(NativeTaskError, 'HOST_BUSY_UNRESOLVED'):
                    tasks._claim(conn, attempt, 'illustrator')


class BackupCliTests(unittest.TestCase):
    def test_cli_backup_then_restore_into_a_fresh_root(self):
        base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        project = base / 'project'
        project.mkdir()
        (project / 'AGENTS.md').write_text('# backup probe project', encoding='utf-8')
        local = _state_root(project)
        env = {**os.environ, 'PYTHONPATH': str(REPO / 'src'),
               'PROJECT_LOCAL_ROOT': str(local)}
        archive = base / 'cli-backup.zip'
        created = subprocess.run(
            [sys.executable, '-B', '-m', 'design_lab', '--project', str(project),
             'backup', '--out', str(archive)],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            env=env, timeout=180)
        self.assertEqual(created.returncode, 0, created.stderr)
        record = json.loads(created.stdout)
        self.assertEqual(record['status'], 'BACKUP_CREATED')
        self.assertEqual(record['fileCount'], 3)
        self.assertRegex(record['sha256'], r'^[0-9a-f]{64}$')

        restored = subprocess.run(
            [sys.executable, '-B', '-m', 'design_lab', '--project', str(project),
             'restore', '--from', str(archive), '--into', str(base / 'recovered')],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            env=env, timeout=180)
        self.assertEqual(restored.returncode, 0, restored.stderr)
        receipt = json.loads(restored.stdout)
        self.assertEqual(receipt['status'], 'RESTORE_VERIFIED')
        self.assertEqual(receipt['restored'], 3)
        self.assertTrue(receipt['compatibility']['compatible'],
                        'a backup taken by this build must restore into this build')
        self.assertEqual(receipt['compatibility']['archiveStateSchemaVersion'], 7)
        self.assertTrue((base / 'recovered' / 'task-runtime' / 'service'
                         / 'state.db').is_file())


if __name__ == '__main__':
    unittest.main()
