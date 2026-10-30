# SPDX-License-Identifier: MIT
"""Bounded, explicit-file migration inventory. No copy, delete, mkdir or DB writes."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3

from .paths import PathPolicyError, _no_links, _RESERVED, resolve_paths

_SUFFIXES = {'.json', '.svg', '.png', '.jpg', '.jpeg', '.webp', '.psd', '.psb', '.ai',
             '.pdf', '.wav', '.mp3', '.mp4', '.mov', '.blend', '.db', '.sqlite', '.sqlite3'}
_PRIVATE = {'auth.json', 'credentials.json', 'tokens.json', 'id_rsa', 'id_ed25519',
            'sessions.db', 'session.db', 'cookies', 'keychain', 'memory', 'memories',
            '.git', '.openhuman', '.codex', '.claude'}


def _selection_path(root, relative):
    if not isinstance(relative, str) or not relative or any(c in relative for c in '\\:*?\x00'):
        raise PathPolicyError('migration selections must be explicit repository-relative paths')
    pure = PurePosixPath(relative)
    if pure.is_absolute() or any(p in ('.', '..') for p in pure.parts):
        raise PathPolicyError('escaping migration selection')
    parts = [p.casefold() for p in pure.parts]
    if any(p in _PRIVATE or p.startswith('.env') or 'prompt' in p or 'response' in p for p in parts):
        raise PathPolicyError('private runtime selection rejected')
    if pure.suffix.lower() not in _SUFFIXES:
        raise PathPolicyError('migration requires a supported explicit artifact or project database file')
    legacy = parts[:3] in [['.hermes', 'task-runtime', 'reconstruction'],
                          ['.hermes', 'task-artifacts', 'reconstruction']]
    if not parts or (parts[0] != '.project-local' and not legacy) or '.hermes' in parts[1:]:
        raise PathPolicyError('migration source is outside project artifact roots')
    if any(p.endswith(('.', ' ')) or p.split('.')[0].upper() in _RESERVED
           or any(ord(c) < 32 or c in '<>"|' for c in p) for p in parts):
        raise PathPolicyError('nonportable migration selection')
    path = root.joinpath(*pure.parts)
    _no_links(path, root)
    if path.exists():
        if not path.is_file() or path.stat().st_nlink != 1:
            raise PathPolicyError('selection must be a regular non-hardlinked file')
    return path


def _fingerprint(stat):
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def _digest(path, before):
    with path.open('rb') as stream:
        if _fingerprint(os.fstat(stream.fileno())) != _fingerprint(before):
            raise PathPolicyError('migration source changed before hashing')
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if _fingerprint(path.stat()) != _fingerprint(before):
        raise PathPolicyError('migration source changed while hashing')
    return digest


def _database_check(path):
    # Immutable mode is only used for diagnosis after companions were rejected;
    # it is not proof that an external writer has stopped.
    try:
        conn = sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)
        try:
            columns = {row[1] for row in conn.execute('PRAGMA table_info(operation_intent)')}
            return {'operation_id', 'idempotency_scope', 'idempotency_key', 'request_hash'} <= columns
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return False


def preview(manifest, *, project_root=None, environ=None, max_total_bytes=512*1024*1024):
    layout = resolve_paths(project_root=project_root, environ=environ)
    if (not isinstance(manifest, dict) or set(manifest) != {'schemaVersion', 'files'}
            or manifest['schemaVersion'] != 'design-lab/migration-selection/v1'
            or not isinstance(manifest['files'], list) or not 1 <= len(manifest['files']) <= 1000):
        raise PathPolicyError('invalid or unbounded migration manifest')
    if isinstance(max_total_bytes, bool) or not isinstance(max_total_bytes, int) or max_total_bytes <= 0:
        raise PathPolicyError('migration byte budget must be positive')
    selected, destinations = [], set()
    # Validate every selector before opening any content, not progressively.
    for entry in manifest['files']:
        if not isinstance(entry, dict) or set(entry) != {'source', 'destination'}:
            raise PathPolicyError('each migration entry needs source and destination only')
        source = _selection_path(layout.project_root, entry['source'])
        destination = _selection_path(layout.project_root, entry['destination'])
        destination = layout.checked_path(destination)
        key = str(destination).casefold()
        if key in destinations or key == str(source).casefold():
            raise PathPolicyError('duplicate or self-referencing migration destination')
        destinations.add(key)
        selected.append((source, destination, entry))
    rows, used_bytes = [], 0
    for source, destination, entry in selected:
        row = {**entry, 'backup_required': source.suffix.lower() in {'.db', '.sqlite', '.sqlite3'}}
        rows.append(row)
        if not source.is_file():
            row['status'] = 'SOURCE_MISSING'
            continue
        if row['backup_required'] and any(Path(str(source)+suffix).exists() for suffix in ('-wal', '-shm', '-journal')):
            row['status'] = 'DATABASE_COMPANION_PRESENT'
            continue
        before = source.stat()
        row['size_bytes'] = before.st_size
        destination_size = destination.stat().st_size if destination.is_file() else 0
        if used_bytes + before.st_size + destination_size > max_total_bytes:
            row['status'] = 'BYTE_BUDGET_EXCEEDED'
            continue
        used_bytes += before.st_size + destination_size
        if row['backup_required'] and not _database_check(source):
            row['status'] = 'UNRECOGNIZED_PROJECT_DATABASE'
            continue
        row['sha256'] = _digest(source, before)
        row['mtime_ns'] = before.st_mtime_ns
        row['status'] = 'READY_FOR_BACKUP'
        if destination.is_file():
            digest = _digest(destination, destination.stat())
            row['destination_sha256'] = digest
            row['status'] = 'ALREADY_IDENTICAL' if digest == row['sha256'] else 'DESTINATION_CONFLICT'
    ready = all(row['status'] in {'READY_FOR_BACKUP', 'ALREADY_IDENTICAL'} for row in rows)
    return {'schemaVersion':'design-lab/migration-preview/v1', 'status':'PREVIEW_READY' if ready else 'BLOCKED',
            'observed_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'project_root':layout.project_root.as_posix(), 'files':rows, 'budgeted_bytes':used_bytes,
            'migration_executed':False, 'writers_stopped_verified':False,
            'required_before_migration':['stop and verify project writers', 'backup DB and artifacts with hash readback',
                                         'copy into staging and verify', 'switch one writer root', 'reopen and verify or restore backup']}


def preview_file(path, *, project_root=None, environ=None):
    layout = resolve_paths(project_root=project_root, environ=environ)
    path = layout.checked_path(path)
    path = _selection_path(layout.project_root, path.relative_to(layout.project_root).as_posix())
    with path.open('rb') as stream:
        raw = stream.read(1024*1024 + 1)
    if len(raw) > 1024*1024:
        raise PathPolicyError('migration manifest exceeds 1 MiB')
    def unique(pairs):
        values = {}
        for key, value in pairs:
            if key in values:
                raise PathPolicyError('duplicate migration manifest key')
            values[key] = value
        return values
    try:
        manifest = json.loads(raw, object_pairs_hook=unique)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise PathPolicyError('invalid migration manifest JSON') from exc
    return preview(manifest, project_root=layout.project_root, environ=environ)
