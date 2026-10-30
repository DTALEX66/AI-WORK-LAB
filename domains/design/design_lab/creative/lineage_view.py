# SPDX-License-Identifier: MIT
"""DLDS-F030 — one shape for every creative lineage node.

The taskpack requires CreativeJob, Operation, Attempt, Asset and AssetVersion to
each expose the same nine facts: identity, parent, inputs, outputs, state,
evidence references and a rollback statement. They already live in different
tables with different vocabularies, so this module is a read-only projection that
answers the same question the same way for all five kinds — rather than five
ad-hoc queries a caller has to remember.

Nothing here writes. Where a fact is genuinely absent in the schema (a job has no
state column of its own), the projection derives it from the recorded source and
says so in ``state_source`` instead of inventing a column.
"""
from __future__ import annotations

from .store import CreativeError

KINDS = ("job", "operation", "attempt", "asset", "version")
FIELDS = ("id", "kind", "parent", "inputs", "outputs", "state", "state_source",
          "evidence", "rollback")
ROLLBACK = {
    "job": "withdraw the job: it owns no bytes; its deliverables are per-asset versions",
    "operation": "discard the attempt's staged outputs and release the asset writer lease",
    "attempt": "an attempt with an unknown outcome must be reconciled, never silently re-run",
    "asset": "publish a new version; an existing version is never rewritten",
    "version": "supersede with a new version on the same branch, or fork a new branch",
}


def _row(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()


def _job(conn, identity: str) -> dict:
    row = _row(conn, "SELECT job_id, operation_id, project_id, brief_ref, direction_ref, "
                     "spec_sha256 FROM creative_job WHERE job_id=?", (identity,))
    if not row:
        raise CreativeError(f"unknown {identity!r} for kind 'job'")
    job_id, operation_id, project_id, brief_ref, direction_ref, spec_sha256 = row
    operation = _row(conn, "SELECT state FROM operation_state WHERE operation_id=?", (operation_id,))
    deliverables = [{"deliverable_id": r[0], "asset_kind": r[1], "host_target": r[2],
                     "editable": bool(r[3])}
                    for r in conn.execute("SELECT deliverable_id, asset_kind, host_target, editable "
                                          "FROM creative_job_deliverable WHERE job_id=? ORDER BY "
                                          "deliverable_id", (job_id,))]
    return {
        "id": job_id,
        "kind": "job",
        "parent": project_id,
        "inputs": [{"kind": "brief", "ref": brief_ref},
                   *([{"kind": "direction", "ref": direction_ref}] if direction_ref else [])],
        "outputs": deliverables,
        "state": operation[0] if operation else "NOT_DISPATCHED",
        "state_source": "derived from operation_state of the job's operation",
        "evidence": {"spec_sha256": spec_sha256},
        "rollback": ROLLBACK["job"],
    }


def _operation(conn, identity: str) -> dict:
    from .lineage import inputs_of, outputs_of
    row = _row(conn, "SELECT job_id, provider_id, model_id, params_sha256, attempt_id, recorded_at "
                     "FROM operation_lineage WHERE operation_id=?", (identity,))
    if not row:
        raise CreativeError(f"no recorded lineage for {identity!r} (kind 'operation')")
    state = _row(conn, "SELECT state FROM operation_state WHERE operation_id=?", (identity,))
    return {
        "id": identity,
        "kind": "operation",
        "parent": row[0],
        "inputs": inputs_of(conn, identity),
        "outputs": outputs_of(conn, identity),
        "state": state[0] if state else "UNRECORDED",
        "state_source": "operation_state (job_store attempt contract)",
        "evidence": {"params_sha256": row[3], "provider_id": row[1], "model_id": row[2],
                     "attempt_id": row[4], "recorded_at": row[5]},
        "rollback": ROLLBACK["operation"],
    }


def _attempt(conn, identity: str) -> dict:
    row = _row(conn, "SELECT job_id, attempt_no, state, started_at, ended_at, note FROM attempt_state "
                     "WHERE attempt_id=?", (identity,))
    if not row:
        raise CreativeError(f"unknown {identity!r} for kind 'attempt'")
    resolution = _row(conn, "SELECT proof, evidence_json FROM attempt_resolution WHERE attempt_id=?",
                      (identity,))
    events = [{"from": r[0], "to": r[1], "detail": r[2]} for r in
              conn.execute("SELECT from_state, to_state, detail FROM attempt_event WHERE attempt_id=? "
                           "ORDER BY event_no", (identity,))]
    return {
        "id": identity,
        "kind": "attempt",
        "parent": row[0],
        "inputs": [{"kind": "attempt_no", "value": row[1]}],
        "outputs": [],
        "state": row[2],
        "state_source": "attempt_state (terminal states are immutable)",
        "evidence": {"proof": resolution[0] if resolution else None,
                     "evidence_json": resolution[1] if resolution else None,
                     "started_at": row[3], "ended_at": row[4], "note": row[5],
                     "history": events},
        "rollback": ROLLBACK["attempt"],
    }


def _asset(conn, identity: str) -> dict:
    row = _row(conn, "SELECT project_id, asset_kind, created_at FROM asset WHERE asset_id=?",
               (identity,))
    if not row:
        raise CreativeError(f"unknown {identity!r} for kind 'asset'")
    versions = [{"version_id": r[0], "version_no": r[1], "state": r[2], "branch": r[3],
                 "generation": r[4], "parent_version_id": r[5]}
                for r in conn.execute("SELECT version_id, version_no, state, branch, generation, "
                                      "parent_version_id FROM asset_version WHERE asset_id=? ORDER BY "
                                      "version_no", (identity,))]
    active = [v for v in versions if v["state"] == "ACTIVE"]
    return {
        "id": identity,
        "kind": "asset",
        "parent": row[0],
        "inputs": [{"kind": "asset_kind", "value": row[1]}],
        "outputs": versions,
        "state": active[-1]["state"] if active else ("NO_VERSION" if not versions else versions[-1]["state"]),
        "state_source": "the newest ACTIVE version, else NO_VERSION",
        "evidence": {"created_at": row[2], "version_count": len(versions)},
        "rollback": ROLLBACK["asset"],
    }


def _version(conn, identity: str) -> dict:
    from .version_guard import rejection_status
    row = _row(conn, "SELECT asset_id, version_no, content_sha256, state, created_at, parent_version_id, "
                     "branch, label, generation FROM asset_version WHERE version_id=?", (identity,))
    if not row:
        raise CreativeError(f"unknown {identity!r} for kind 'version'")
    artifacts = [{"path": r[0], "sha256": r[1], "byte_size": r[2], "role": r[3]} for r in
                 conn.execute("SELECT path, sha256, byte_size, role FROM artifact WHERE version_id=? "
                              "ORDER BY path", (identity,))]
    try:
        from .lineage import inputs_of, producer_of
        producer = producer_of(conn, identity)
        inputs = inputs_of(conn, producer["operation_id"])
        evidence = {"content_sha256": row[2], "artifacts": artifacts,
                    "operation_id": producer["operation_id"], "params_sha256": producer["params_sha256"]}
    except CreativeError:
        inputs = []
        evidence = {"content_sha256": row[2], "artifacts": artifacts, "operation_id": None}
    return {
        "id": identity,
        "kind": "version",
        "parent": row[5],
        "inputs": inputs,
        "outputs": artifacts,
        "state": rejection_status(conn, identity),
        "state_source": "asset_version.state, overridden by a terminal rejection",
        "evidence": evidence,
        "rollback": ROLLBACK["version"],
    }


_PROJECTIONS = {"job": _job, "operation": _operation, "attempt": _attempt,
                "asset": _asset, "version": _version}


def node(conn, kind: str, identity: str) -> dict:
    """One lineage node in the shape every kind shares."""
    if kind not in _PROJECTIONS:
        raise CreativeError(f"unknown lineage kind {kind!r}; expected one of {list(KINDS)}")
    if not isinstance(identity, str) or not identity.strip():
        raise CreativeError("identity must be a nonempty string")
    result = _PROJECTIONS[kind](conn, identity)
    missing = [field for field in FIELDS if field not in result]
    if missing:
        raise CreativeError(f"lineage projection for {kind} is missing {missing}")
    return result


def explain(conn, kind: str, identity: str) -> str:
    """A one-line human summary; useful in logs and evidence records."""
    item = node(conn, kind, identity)
    parent = item["parent"] or "-"
    return (f"{item['kind']} {item['id']} parent={parent} state={item['state']} "
            f"inputs={len(item['inputs'])} outputs={len(item['outputs'])}")
