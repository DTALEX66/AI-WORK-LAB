# SPDX-License-Identifier: MIT
"""DL-P0-022 AssetVersion V2: branch, parent and generation over frozen v1 rows.

v1 identity is unchanged: a version is still ``(asset_id, version_no)`` with a
content digest. V2 adds the facts a design job needs to explain itself — which
version it was derived from, on which branch, and how many derivations deep.
Creation reuses the v1 writer (``asset_store._record_version``) inside this
module's transaction, so there is one writer and one set of rows, never a copy.

Identical bytes never create a second version: the existing version is returned
with ``created=False`` and its recorded parent is left untouched.
"""
from __future__ import annotations

import sqlite3

from ..runtime import asset_store
from .store import CreativeError, require_job, transaction

_STATES = {"PENDING", "ACTIVE", "SUPERSEDED", "FAILED", "CANCELLED"}


def _branch(value) -> str:
    if not isinstance(value, str) or not value.strip() or any(c.isspace() for c in value):
        raise CreativeError("branch must be a nonempty string without whitespace")
    return value


def version(conn, version_id: str) -> dict:
    row = conn.execute("SELECT version_id, asset_id, version_no, content_sha256, state, created_at, "
                       "parent_version_id, branch, label, generation FROM asset_version WHERE version_id=?",
                       (version_id,)).fetchone()
    if not row:
        raise CreativeError(f"unknown asset version: {version_id!r}")
    return {"version_id": row[0], "asset_id": row[1], "version_no": row[2], "content_sha256": row[3],
            "state": row[4], "created_at": row[5], "parent_version_id": row[6], "branch": row[7],
            "label": row[8], "generation": row[9]}


def create_version(conn, asset_id: str, content_sha256: str, *, artifacts=(), state: str = "ACTIVE",
                   parent_version_id=None, branch: str = "main", label=None, attempt_id=None) -> dict:
    """Create (or find) a version, then attach V2 lineage fields atomically."""
    if state not in _STATES:
        raise CreativeError(f"invalid version state: {state!r}")
    branch = _branch(branch)
    if label is not None and (not isinstance(label, str) or not label.strip()):
        raise CreativeError("label must be a nonempty string or null")
    if not conn.execute("SELECT 1 FROM asset WHERE asset_id=?", (asset_id,)).fetchone():
        raise CreativeError(f"unknown asset: {asset_id!r}")
    generation = 1
    if parent_version_id is not None:
        parent = version(conn, parent_version_id)
        if parent["asset_id"] != asset_id:
            raise CreativeError("parent version belongs to a different asset")
        from .version_guard import assert_servable
        assert_servable(conn, parent_version_id)
        generation = parent["generation"] + 1

    with transaction(conn):
        try:
            digest = asset_store._digest(content_sha256)
        except asset_store.AssetError as exc:
            raise CreativeError(str(exc)) from exc
        before = conn.execute("SELECT version_id FROM asset_version WHERE asset_id=? AND content_sha256 IN (?,?)",
                              (asset_id, digest, digest.removeprefix("sha256:"))).fetchone()
        try:
            version_id = asset_store._record_version(conn, asset_id, digest, state=state,
                                                     artifacts=artifacts, attempt_id=attempt_id)
        except asset_store.AssetError as exc:
            raise CreativeError(str(exc)) from exc
        if before:
            return {"version_id": version_id, "created": False, **{k: v for k, v in version(conn, version_id).items()
                                                                   if k in {"branch", "label", "generation",
                                                                            "parent_version_id", "version_no"}}}
        conn.execute("UPDATE asset_version SET parent_version_id=?, branch=?, label=?, generation=? "
                     "WHERE version_id=?", (parent_version_id, branch, label, generation, version_id))
        return {"version_id": version_id, "created": True, "branch": branch, "label": label,
                "generation": generation, "parent_version_id": parent_version_id,
                "version_no": version(conn, version_id)["version_no"]}


def fork(conn, version_id: str, *, branch: str, content_sha256: str, artifacts=(), label=None,
         state: str = "ACTIVE", attempt_id=None) -> dict:
    """Start a branch from an existing version (parent = that version)."""
    parent = version(conn, version_id)
    if _branch(branch) == parent["branch"]:
        raise CreativeError("fork must target a new branch name")
    return create_version(conn, parent["asset_id"], content_sha256, artifacts=artifacts, state=state,
                          parent_version_id=version_id, branch=branch, label=label, attempt_id=attempt_id)


def chain(conn, version_id: str) -> list:
    """Root-to-version ancestry along parent links; detects a broken chain."""
    walk, seen = [], set()
    current = version_id
    while current is not None:
        if current in seen:
            raise CreativeError(f"parent chain cycle at {current!r}")
        seen.add(current)
        record = version(conn, current)
        walk.append({"version_id": record["version_id"], "branch": record["branch"],
                     "generation": record["generation"], "state": record["state"], "label": record["label"]})
        current = record["parent_version_id"]
    return list(reversed(walk))


def branch_tip(conn, asset_id: str, branch: str = "main"):
    """Highest version on a branch, regardless of state; None when empty."""
    row = conn.execute("SELECT version_id FROM asset_version WHERE asset_id=? AND branch=? "
                       "ORDER BY version_no DESC, version_id DESC LIMIT 1",
                       (asset_id, _branch(branch))).fetchone()
    return row[0] if row else None


def branches(conn, asset_id: str) -> list:
    # version_id is an opaque identity; UUID ordering must never decide which
    # version is the branch tip. Use the same version_no ordering as branch_tip.
    return [{"branch": row[0], "versions": row[1], "tip": row[2]} for row in conn.execute(
        "SELECT v.branch, COUNT(*), "
        "(SELECT tip.version_id FROM asset_version AS tip "
        " WHERE tip.asset_id=v.asset_id AND tip.branch=v.branch "
        " ORDER BY tip.version_no DESC, tip.version_id DESC LIMIT 1) "
        "FROM asset_version AS v WHERE v.asset_id=? "
        "GROUP BY v.branch ORDER BY v.branch", (asset_id,))]


def set_label(conn, version_id: str, label) -> None:
    """Labels are operator metadata, not evidence; state and bytes stay frozen."""
    version(conn, version_id)
    if label is not None and (not isinstance(label, str) or not label.strip()):
        raise CreativeError("label must be a nonempty string or null")
    with transaction(conn):
        conn.execute("UPDATE asset_version SET label=? WHERE version_id=?", (label, version_id))


def register_asset_for_job(conn, job_id: str, asset_id: str, asset_kind: str) -> None:
    """Create an asset inside the job's project; the project binding is checked."""
    job = require_job(conn, job_id)
    try:
        asset_store.register_asset(conn, job["project_id"], asset_id, asset_kind)
    except (asset_store.AssetError, sqlite3.IntegrityError) as exc:
        raise CreativeError(str(exc)) from exc
