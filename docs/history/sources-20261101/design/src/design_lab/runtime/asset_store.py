# SPDX-License-Identifier: MIT
"""Local asset metadata, fenced leases and recoverable immutable publication.

record_version imports adapter-verified metadata (does not read files).
publish_version is the file-writing API: stages and hashes bytes, checks the
lease at rename/commit, and preserves uncommitted bytes for explicit recovery.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import math
import os
import shutil
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .attempt_contract import canonical_hash
from .paths import PathPolicyError, resolve_paths
from .state_resources import state_schema

_SCHEMA = state_schema("design-lab-state-assets-v1.sql")
_BASE_SCHEMA = state_schema("design-lab-state-v1.sql")
_V2_SCHEMA = state_schema("design-lab-state-assets-v2.sql")


class AssetError(RuntimeError):
    """Asset registry contract violation."""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _clock():
    return time.time()


@contextmanager
def _transaction(conn):
    if conn.in_transaction:
        raise AssetError("write API requires idle connection; caller transaction is preserved")
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def connect(db_path, *, project_root=None):
    try:
        db_path = resolve_paths(project_root=project_root).database_path(db_path)
    except PathPolicyError as exc:
        raise AssetError(str(exc)) from exc
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=15)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(_BASE_SCHEMA.read_text(encoding="utf-8"))
        conn.executescript(_SCHEMA.read_text(encoding="utf-8"))
        conn.execute("CREATE TABLE IF NOT EXISTS runtime_migration (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
        conn.commit()
        if not conn.execute("SELECT 1 FROM runtime_migration WHERE name='assets-v2'").fetchone():
            if conn.execute("SELECT 1 FROM asset_version LIMIT 1").fetchone():
                backup_path = db_path.with_name(f"{db_path.name}.pre-assets-v2-{uuid.uuid4().hex}.bak")
                backup = sqlite3.connect(str(backup_path))
                try:
                    conn.backup(backup)
                finally:
                    backup.close()
            with _transaction(conn):
                if not conn.execute("SELECT 1 FROM runtime_migration WHERE name='assets-v2'").fetchone():
                    statement = ""
                    for line in _V2_SCHEMA.read_text(encoding="utf-8").splitlines(keepends=True):
                        statement += line
                        if sqlite3.complete_statement(statement):
                            conn.execute(statement)
                            statement = ""
                    if statement.strip():
                        raise AssetError("incomplete migration SQL")
                    conn.execute("INSERT INTO runtime_migration VALUES ('assets-v2', ?)", (_now(),))
        return conn
    except BaseException:
        conn.close()
        raise


def create_project(conn, project_id, display_name):
    with _transaction(conn):
        conn.execute("INSERT OR IGNORE INTO project VALUES (?,?,?)", (project_id, display_name, _now()))


def register_asset(conn, project_id, asset_id, asset_kind):
    with _transaction(conn):
        old = conn.execute("SELECT project_id,asset_kind FROM asset WHERE asset_id=?", (asset_id,)).fetchone()
        if old and old != (project_id, asset_kind):
            raise AssetError("asset identity is already bound to another project/kind")
        conn.execute("INSERT OR IGNORE INTO asset VALUES (?,?,?,?)", (asset_id, project_id, asset_kind, _now()))


def _digest(value):
    try:
        return canonical_hash(value)
    except ValueError as exc:
        raise AssetError(str(exc)) from exc


def _record_version(conn, asset_id, content_sha256, *, state="ACTIVE", artifacts=(), attempt_id=None):
    if state not in {"PENDING", "ACTIVE", "SUPERSEDED", "FAILED", "CANCELLED"}:
        raise AssetError(f"invalid version state: {state!r}")
    digest = _digest(content_sha256)
    existing = conn.execute("SELECT version_id FROM asset_version WHERE asset_id=? AND content_sha256 IN (?,?)",
                            (asset_id, digest, digest.removeprefix("sha256:"))).fetchone()
    if existing:
        return existing[0]
    artifacts = list(artifacts)
    if state == "ACTIVE" and not artifacts:
        raise AssetError("ACTIVE version requires at least one verified artifact")
    version_no = conn.execute("SELECT COALESCE(MAX(version_no),0)+1 FROM asset_version WHERE asset_id=?", (asset_id,)).fetchone()[0]
    version_id = "v-" + uuid.uuid4().hex
    # Named columns: later additive migrations append columns, and a positional
    # insert would silently break the v1 writer when they do.
    conn.execute("INSERT INTO asset_version "
                 "(version_id, asset_id, version_no, content_sha256, state, created_at) "
                 "VALUES (?,?,?,?,?,?)",
                 (version_id, asset_id, version_no, digest, state, _now()))
    seen = set()
    for path, sha, size, role in artifacts:
        if not isinstance(path, str) or not path or path in seen:
            raise AssetError("artifact paths must be nonempty and distinct within a version")
        if state == "ACTIVE":
            sha = _digest(sha)
            if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
                raise AssetError("ACTIVE artifact requires a positive byte size")
        seen.add(path)
        conn.execute("INSERT INTO artifact VALUES (?,?,?,?,?,?)",
                     ("a-" + uuid.uuid4().hex, version_id, path, sha, size, role))
    if attempt_id:
        conn.execute("INSERT INTO audit_event VALUES (?,?,?,?)",
                     (uuid.uuid4().hex, attempt_id, f"asset_version_created:{version_id}", _now()))
    return version_id


def record_version(conn, asset_id, content_sha256, *, state="ACTIVE", artifacts=(), attempt_id=None):
    """Atomically import metadata. Paths are attributes, never artifact identity."""
    with _transaction(conn):
        return _record_version(conn, asset_id, content_sha256, state=state, artifacts=artifacts, attempt_id=attempt_id)


def latest_active_version(conn, asset_id):
    row = conn.execute("SELECT version_id,version_no,content_sha256,state,created_at FROM asset_version "
                       "WHERE asset_id=? AND state='ACTIVE' ORDER BY version_no DESC LIMIT 1", (asset_id,)).fetchone()
    return dict(zip(("version_id", "version_no", "content_sha256", "state", "created_at"), row)) if row else None


def _expiry(lease_seconds):
    if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, (int, float)) or not math.isfinite(lease_seconds) or lease_seconds <= 0:
        raise AssetError("lease duration must be finite and positive")
    return _clock() + lease_seconds


def _expiration(row):
    if not row:
        return None
    try:
        # Legacy ISO leases are recognized; missing expiry is never executable.
        expiry = float(row[3])
    except (ValueError, TypeError):
        try:
            parsed = datetime.fromisoformat(row[3])
            if parsed.tzinfo is None:
                return None
            expiry = parsed.timestamp()
        except (ValueError, TypeError):
            return None
    return expiry if math.isfinite(expiry) else None


def _lease_live(row):
    expiry = _expiration(row)
    return bool(row and row[2] == "HELD" and expiry is not None and expiry > _clock())


def _lease(conn, resource_key):
    return conn.execute("SELECT holder_attempt_id,generation,state,expires_at FROM asset_writer_lock WHERE resource_key=?",
                        (resource_key,)).fetchone()


def acquire_writer(conn, resource_key, holder_attempt_id, *, lease_seconds=60):
    expires = _expiry(lease_seconds)
    with _transaction(conn):
        old = _lease(conn, resource_key)
        # Legacy HELD/no-expiry requires explicit takeover, never silent expiry.
        if _lease_live(old) or (old and old[2] == "HELD" and _expiration(old) is None):
            return False
        generation = old[1] + 1 if old else 1
        conn.execute("INSERT INTO asset_writer_lock VALUES (?,?,?,'HELD',?,?) "
                     "ON CONFLICT(resource_key) DO UPDATE SET holder_attempt_id=excluded.holder_attempt_id,"
                     "generation=excluded.generation,state='HELD',acquired_at=excluded.acquired_at,expires_at=excluded.expires_at",
                     (resource_key, holder_attempt_id, generation, _now(), str(expires)))
        return True


def writer_token(conn, resource_key, holder_attempt_id):
    row = _lease(conn, resource_key)
    if not _lease_live(row) or row[0] != holder_attempt_id:
        raise AssetError("writer has no valid lease")
    return row[1]


def _fence(conn, resource_key, holder_attempt_id, generation):
    row = _lease(conn, resource_key)
    if (isinstance(generation, bool) or not isinstance(generation, int)
            or not _lease_live(row) or row[:2] != (holder_attempt_id, generation)):
        raise AssetError("expired or stale writer fencing token")


def assert_writer_fence(conn, resource_key, holder_attempt_id, generation):
    """Assert the caller's lease is still current, on the CALLER's open transaction.

    ``_fence`` is the rule ``renew_writer`` and ``publish_version`` already apply,
    but both open their own transaction and therefore refuse a connection that is
    mid-write (``_transaction`` fails closed on ``conn.in_transaction``). A
    SQLite-only writer that owns its transaction -- the design-system token append
    in ``design_layer.py`` -- needs the same check without a second BEGIN, so it
    gets this one instead of a second lock. Read-only: it asserts, never renews,
    never extends an expiry and never takes a lease from another holder.
    """
    _fence(conn, resource_key, holder_attempt_id, generation)
    return generation


def takeover_writer(conn, resource_key, holder_attempt_id, *, lease_seconds=60, expected_holder=None):
    """Explicit handover; always increments generation and records the change."""
    expires = _expiry(lease_seconds)
    with _transaction(conn):
        old = _lease(conn, resource_key)
        if expected_holder is not None and (not old or old[0] != expected_holder):
            raise AssetError('writer ownership changed before recovery takeover')
        generation = old[1] + 1 if old else 1
        conn.execute("INSERT INTO asset_writer_lock VALUES (?,?,?,'HELD',?,?) "
                     "ON CONFLICT(resource_key) DO UPDATE SET holder_attempt_id=excluded.holder_attempt_id,"
                     "generation=excluded.generation,state='HELD',acquired_at=excluded.acquired_at,expires_at=excluded.expires_at",
                     (resource_key, holder_attempt_id, generation, _now(), str(expires)))
        conn.execute("INSERT INTO audit_event VALUES (?,?,?,?)",
                     (uuid.uuid4().hex, holder_attempt_id, f"writer_takeover:{resource_key}", _now()))
        return generation


def renew_writer(conn, resource_key, holder_attempt_id, *, generation, lease_seconds=60):
    expires = _expiry(lease_seconds)
    with _transaction(conn):
        _fence(conn, resource_key, holder_attempt_id, generation)
        conn.execute("UPDATE asset_writer_lock SET expires_at=? WHERE resource_key=?", (str(expires), resource_key))


def release_writer(conn, resource_key, holder_attempt_id, *, generation=None):
    with _transaction(conn):
        old = _lease(conn, resource_key)
        if not old or old[0] != holder_attempt_id or old[2] != "HELD":
            return False
        if isinstance(generation, bool) or not isinstance(generation, int) or old[1] != generation:
            return False
        conn.execute("UPDATE asset_writer_lock SET state='RELEASED' WHERE resource_key=?", (resource_key,))
        return True


def _safe_root(store_root, *, project_root=None):
    try:
        layout = resolve_paths(project_root=project_root)
        raw = layout.checked_path(store_root)
    except PathPolicyError as exc:
        raise AssetError(str(exc)) from exc
    _check_path(raw, layout.local_root)
    return raw


def _check_path(path, root):
    path = Path(path).absolute()
    if not path.is_relative_to(root):
        raise AssetError("publication path escapes store root")
    for parent in (path, *path.parents):
        if parent.exists() or parent.is_symlink():
            if parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
                raise AssetError("publication path traverses a link/junction")
        if parent == root:
            break
    if not path.resolve().is_relative_to(root.resolve()):
        raise AssetError("resolved publication path escapes store root")


def _file_hash(path):
    with Path(path).open("rb") as stream:
        return "sha256:" + hashlib.file_digest(stream, "sha256").hexdigest()


def _after_stage(publication_id):
    """Fault-injection seam after durable staging, before acquiring publish lock."""


def _after_rename(publication_id):
    """Fault-injection seam after rename, before SQLite metadata commit."""


def _portable_name(name):
    if not isinstance(name, str) or not name or name in {".", ".."}:
        return False
    if name.endswith((".", " ")) or any(ord(char) < 32 or char in '/\\:"<>|?*' for char in name):
        return False
    stem = name.split('.', 1)[0].upper().rstrip(' ')
    devices = {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$'}
    devices.update(prefix + str(n) for prefix in ('COM', 'LPT') for n in range(1, 10))
    return stem not in devices


def publish_version(conn, asset_id, source, *, store_root, artifact_name,
                    expected_sha256, holder_attempt_id, generation, project_root=None):
    """Copy to immutable per-publication location; keep recovery journal on failure."""
    root = _safe_root(store_root, project_root=project_root)
    if not _portable_name(artifact_name):
        raise AssetError("artifact_name must be a single portable filename")
    source = Path(source)
    digest = _digest(expected_sha256)
    if not source.is_file() or _file_hash(source) != digest or source.stat().st_size <= 0:
        raise AssetError("source file hash/size mismatch")
    pid = uuid.uuid4().hex
    stage = root / "staging" / pid / artifact_name
    final = root / "versions" / pid / artifact_name
    quarantine = root / "quarantine" / pid / artifact_name
    resource = f"asset:{asset_id}"
    with _transaction(conn):
        _fence(conn, resource, holder_attempt_id, generation)
        existing = conn.execute("SELECT p.version_id,p.final_path FROM asset_publication p "
                                "JOIN asset_version v ON p.version_id=v.version_id "
                                "WHERE p.asset_id=? AND p.sha256=? AND p.state='COMMITTED' AND v.state='ACTIVE'",
                                (asset_id, digest)).fetchone()
        if existing:
            old_path = Path(existing[1])
            _check_path(old_path, root)
            if old_path.is_file() and _file_hash(old_path) == digest:
                return existing[0]
            raise AssetError("existing published bytes are missing or corrupt")
        known = conn.execute("SELECT version_id FROM asset_version WHERE asset_id=? AND content_sha256 IN (?,?)",
                             (asset_id, digest, digest.removeprefix("sha256:"))).fetchone()
        if known:
            raise AssetError("content already registered without a verified publication; reconcile/import explicitly")
        conn.execute("INSERT INTO asset_publication VALUES (?,?,?,?,?,?,?,?,?,'PREPARED',NULL,?)",
                     (pid, asset_id, str(root), str(stage), str(final), str(quarantine),
                      digest, holder_attempt_id, generation, _now()))
    for path in (stage, final, quarantine):
        _check_path(path, root)
    stage.parent.mkdir(parents=True, exist_ok=False)
    with source.open("rb") as incoming, stage.open("xb") as outgoing:
        shutil.copyfileobj(incoming, outgoing)
        outgoing.flush()
        os.fsync(outgoing.fileno())
    if _file_hash(stage) != digest:
        raise AssetError("staged file hash mismatch")
    _after_stage(pid)
    with _transaction(conn):
        _fence(conn, resource, holder_attempt_id, generation)
        for path in (stage, final):
            _check_path(path, root)
        if conn.execute("SELECT state FROM asset_publication WHERE publication_id=?", (pid,)).fetchone()[0] != "PREPARED":
            raise AssetError("publication already recovered or completed")
        if _file_hash(stage) != digest:
            raise AssetError("staged file changed after verification")
        if conn.execute("SELECT 1 FROM asset_version WHERE asset_id=? AND content_sha256 IN (?,?)",
                        (asset_id, digest, digest.removeprefix("sha256:"))).fetchone():
            raise AssetError("content registered by another publication while staging")
        final.parent.mkdir(parents=True, exist_ok=False)
        _fence(conn, resource, holder_attempt_id, generation)
        os.replace(stage, final)
        _after_rename(pid)
        if _file_hash(final) != digest:
            raise AssetError("published file hash mismatch")
        version = _record_version(conn, asset_id, digest,
                                  artifacts=[(str(final), digest, final.stat().st_size, "deliverable")],
                                  attempt_id=holder_attempt_id)
        _fence(conn, resource, holder_attempt_id, generation)
        conn.execute("UPDATE asset_publication SET state='COMMITTED',version_id=? WHERE publication_id=?", (version, pid))
        return version


def recover_publications(conn, *, store_root, project_root=None, asset_id=None,
                         holder_attempt_id=None, generation=None):
    """Run with project writers stopped. Preserve uncommitted bytes in quarantine.

    Each journal operation holds the same DB write lock as publish/takeover.
    Recovery can be repeated after a crash during its own rename.
    Alternatively scope to one asset/attempt with a current fencing token;
    caller must independently prove that attempt's old worker has stopped.
    Other assets/attempts are untouched by scoped recovery.
    """
    root = _safe_root(store_root, project_root=project_root)
    recovered = []
    with _transaction(conn):
        scoped = (asset_id, holder_attempt_id, generation)
        if any(value is not None for value in scoped) and any(value is None for value in scoped):
            raise AssetError('scoped recovery requires asset, attempt and fencing generation')
        query = ("SELECT publication_id,stage_path,final_path,quarantine_path "
                 "FROM asset_publication WHERE store_root=? AND state='PREPARED'")
        parameters = [str(root)]
        if asset_id is not None:
            _fence(conn, 'asset:' + asset_id, holder_attempt_id, generation)
            query += ' AND asset_id=? AND holder_attempt_id=?'
            parameters.extend((asset_id, holder_attempt_id))
        rows = conn.execute(query, parameters).fetchall()
        for pid, stage, final, quarantine in rows:
            stage, final, quarantine = map(Path, (stage, final, quarantine))
            for path in (stage, final, quarantine):
                _check_path(path, root)
            source = final if final.is_file() else stage
            if quarantine.is_file():
                state = "QUARANTINED"
            elif source.is_file():
                quarantine.parent.mkdir(parents=True, exist_ok=True)
                os.replace(source, quarantine)
                state = "QUARANTINED"
            else:
                state = "MISSING"
            conn.execute("UPDATE asset_publication SET state=? WHERE publication_id=?", (state, pid))
            recovered.append(dict(publication_id=pid, state=state, path=str(quarantine)))
    return recovered
