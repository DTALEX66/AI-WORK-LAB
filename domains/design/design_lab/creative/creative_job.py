# SPDX-License-Identifier: MIT
"""DL-P0-020 CreativeJob: the unit of design work, its deliverables and hosts.

A CreativeJob is not a chat session and not a second canvas. It fixes the brief,
the direction, the rights profile, the deliverables and the host targets that a
piece of work is accountable to, and it is the anchor every lineage edge,
requirement and decision in Wave B points at.

Semantics that the JSON Schema cannot express are enforced here and fail closed:
a blocked rights profile, a rejected direction, a deliverable that names an
undeclared host target, or an editable deliverable whose host target cannot
produce an editable source.
"""
from __future__ import annotations

import json
from functools import lru_cache

from jsonschema import Draft202012Validator

from ..runtime.paths import PROJECT_ROOT
from .store import (
    CreativeError, dumps, hash_document, new_id, now, record_intent,
    require_job as _require_job, transaction,
)

SPEC_VERSION = "design-lab/creative-job/v1"
SCHEMA_PATH = PROJECT_ROOT / "design-lab/schemas/creative-job.schema.json"


@lru_cache(maxsize=1)
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _fail(message: str, path=()) -> "CreativeError":
    where = "/".join(str(part) for part in path)
    return CreativeError(f"{message} at /{where}" if where else message)


def validate_job(job) -> dict:
    """Schema + semantic validation. Returns a deep copy; never mutates input."""
    if not isinstance(job, dict):
        raise CreativeError("creative job must be an object")
    errors = sorted(Draft202012Validator(schema()).iter_errors(job), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        raise _fail(f"creative job schema violation: {first.message}", first.path)
    document = json.loads(dumps(job))
    if document["schemaVersion"] != SPEC_VERSION:
        raise CreativeError("unsupported creative job schemaVersion")
    if document["rights_profile"]["gate_state"] == "BLOCKED":
        raise CreativeError("rights profile is BLOCKED: the job must not start")
    direction = document.get("direction_ref")
    if direction and direction.get("gate_state") == "REJECTED":
        raise CreativeError("direction gate REJECTED: the job must not start")

    seen_deliverables = set()
    for index, deliverable in enumerate(document["deliverables"]):
        identity = deliverable["deliverable_id"]
        if identity in seen_deliverables:
            raise _fail(f"duplicate deliverable_id {identity!r}", ("deliverables", index))
        seen_deliverables.add(identity)

    hosts = {}
    for index, target in enumerate(document["host_targets"]):
        host_id = target["host_id"]
        if host_id in hosts:
            raise _fail(f"duplicate host target {host_id!r}", ("host_targets", index))
        hosts[host_id] = target

    for index, deliverable in enumerate(document["deliverables"]):
        target = hosts.get(deliverable["host_target"])
        if target is None:
            raise _fail(f"undeclared host target {deliverable['host_target']!r}",
                        ("deliverables", index, "host_target"))
        if deliverable["editable"] and not target["editable_source"]:
            raise _fail(f"editable deliverable requires an editable source host; {target['host_id']!r} declares none",
                        ("deliverables", index, "editable"))
    return document


def delivery_readiness(job: dict) -> dict:
    """Non-raising projection: what still separates this job from delivery.

    ``E0``/``E1`` host targets are declared or structural only, so a job built
    entirely on them is reported as not host-verified rather than ready.
    """
    document = validate_job(job)
    hosts = {target["host_id"]: target for target in document["host_targets"]}
    host_verified = sorted({deliverable["host_target"] for deliverable in document["deliverables"]
                            if hosts[deliverable["host_target"]]["evidence_level"] in {"E2", "E3", "E4", "E5"}})
    return {
        "job": "DELIVERY_CANDIDATE" if host_verified else "NOT_HOST_VERIFIED",
        "host_verified_targets": host_verified,
        "rights_gate_state": document["rights_profile"]["gate_state"],
        "editable_deliverables": sorted(d["deliverable_id"] for d in document["deliverables"] if d["editable"]),
        "deliverable_count": len(document["deliverables"]),
    }


def create_job(conn, job, *, idempotency_scope: str, idempotency_key: str) -> dict:
    """Register a validated job. Same key + same content is idempotent.

    The project row is ensured first in its own statement, so the caller's work
    is never committed by accident: an open caller transaction is refused.
    """
    if conn.in_transaction:
        raise CreativeError("create_job requires an idle connection; caller transaction is preserved")
    document = validate_job(job)
    spec_sha256 = hash_document(document)
    project_id = document["project_id"]
    conn.execute("INSERT OR IGNORE INTO project VALUES (?,?,?)", (project_id, project_id, now()))
    conn.commit()
    with transaction(conn):
        operation_id, request = record_intent(conn, scope=idempotency_scope,
                                              key=idempotency_key, document=document)
        existing = conn.execute("SELECT job_id, spec_sha256 FROM creative_job WHERE operation_id=?",
                                (operation_id,)).fetchone()
        if existing:
            if existing[1] != spec_sha256:
                raise CreativeError("job operation is already bound to a different spec")
            return {"job_id": existing[0], "operation_id": operation_id,
                    "spec_sha256": spec_sha256, "request_hash": request, "created": False}
        job_id = new_id("job")
        conn.execute("INSERT INTO job VALUES (?,?,?)", (job_id, operation_id, "design-lab/job-spec/v2"))
        conn.execute("INSERT INTO creative_job VALUES (?,?,?,?,?,?,?,?,?)",
                     (job_id, operation_id, project_id, document["brief_ref"]["brief_id"],
                      (document.get("direction_ref") or {}).get("direction_id"),
                      document["rights_profile"]["profile_id"], dumps(document), spec_sha256, now()))
        for deliverable in document["deliverables"]:
            conn.execute("INSERT INTO creative_job_deliverable VALUES (?,?,?,?,?)",
                         (job_id, deliverable["deliverable_id"], deliverable["asset_kind"],
                          deliverable["host_target"], 1 if deliverable["editable"] else 0))
        return {"job_id": job_id, "operation_id": operation_id,
                "spec_sha256": spec_sha256, "request_hash": request, "created": True}


def load_job(conn, job_id: str) -> dict:
    row = conn.execute("SELECT spec_json, spec_sha256, operation_id, created_at FROM creative_job WHERE job_id=?",
                       (job_id,)).fetchone()
    if not row:
        raise CreativeError(f"unknown creative job: {job_id!r}")
    document = json.loads(row[0])
    if hash_document(document) != row[1]:
        raise CreativeError("stored job spec does not match its recorded hash")
    document.update({"job_id": job_id, "operation_id": row[2], "spec_sha256": row[1], "created_at": row[3]})
    return document


def deliverables(conn, job_id: str) -> list:
    _require_job(conn, job_id)
    return [{"deliverable_id": row[0], "asset_kind": row[1], "host_target": row[2], "editable": bool(row[3])}
            for row in conn.execute("SELECT deliverable_id, asset_kind, host_target, editable "
                                    "FROM creative_job_deliverable WHERE job_id=? ORDER BY deliverable_id",
                                    (job_id,))]


def job_for_operation(conn, operation_id: str) -> str:
    row = conn.execute("SELECT job_id FROM creative_job WHERE operation_id=?", (operation_id,)).fetchone()
    if not row:
        raise CreativeError(f"operation is not bound to a creative job: {operation_id!r}")
    return row[0]
