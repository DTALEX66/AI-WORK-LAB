"""NF-08-0: compatible extension of the federation handoff envelope (v2).

Extends the existing envelope / receipt / capsule contract family INCREMENTALLY
— it does not create a second authoritative format.  Delta vs v1:

  * producer/consumer move from a hardcoded three-project ENUM to *registered
    project references* (registry-driven); source/target SOFTWARE and
    environment are first-class fields so a project id is never mistaken for a
    client id.
  * task revision, baseline kind, immutable artifact digest, receipt location,
    target capability, authorization reference and ``supersedes`` are added to
    the existing envelope, not duplicated into a parallel document.
  * The code/workspace baseline is explicitly distinguished from the task-body
    revision; the Ready pointer is only published after the immutable snapshot
    is complete.
  * Authorization comes from a *trusted local record* (registry / grant store),
    never from model-mutable ``scope`` / ``approved`` text in the payload.
  * A delivery whose task+revision carries a DIFFERENT digest is a CONFLICT,
    never a silent overwrite of previously approved content.

Old v1 envelopes remain readable (``read_v1``); a v2 message must not be
silently truncated by an old reader — the schema version const makes the
rejection explicit.  Pure and deterministic: no network, no filesystem, no
paid call, no native private store.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

SCHEMA_V1 = "workflow/federation-envelope/v1"
SCHEMA_V2 = "workflow/federation-envelope/v2"

BASELINE_KINDS = ("git", "artifact")
ALLOWED_CLASSIFICATIONS = ("public", "private", "internal", "classified")
ALLOWED_RIGHTS = ("owned", "licensed", "restricted", "unknown")


def _stable_digest(payload: Mapping[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def body_digest(body: Mapping[str, Any]) -> str:
    """Digest over the task *body* (distinct from the code/workspace baseline)."""
    return _stable_digest(body)


def build_v2_envelope(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Build a v2 federation envelope from a draft dict with strong fields.

    The draft carries camelCase fields (matching the wire format).  Missing or
    invalid required fields raise; the result is a normalized envelope where the
    task body travels only through its immutable snapshot reference.
    """
    def need(key: str) -> Any:
        val = envelope.get(key)
        if val in (None, "", 0):
            if key in ("workUnitId", "messageId"):
                raise ValueError(f"{key} is required")
        return val

    message_id = envelope.get("messageId")
    task_id = envelope.get("workUnitId")
    if not task_id or not message_id:
        raise ValueError("workUnitId and messageId are required")
    task_revision = int(envelope.get("taskRevision", 0))
    if task_revision < 1:
        raise ValueError("taskRevision must be >= 1")
    classification = envelope.get("classification", "internal")
    if classification not in ALLOWED_CLASSIFICATIONS:
        raise ValueError(f"unknown classification {classification!r}")
    rights_status = envelope.get("rightsStatus", "owned")
    if rights_status not in ALLOWED_RIGHTS:
        raise ValueError(f"unknown rights status {rights_status!r}")

    baseline = dict(envelope.get("baseline") or {})
    base_kind = baseline.get("kind")
    if base_kind not in BASELINE_KINDS:
        raise ValueError(f"baseline kind must be one of {BASELINE_KINDS}")
    if base_kind == "git" and not baseline.get("commit"):
        raise ValueError("git baseline requires an exact commit")
    if base_kind == "artifact" and not baseline.get("digest"):
        raise ValueError("artifact baseline requires an immutable digest")

    out = {
        "schemaVersion": SCHEMA_V2,
        "messageId": message_id,
        "producer": envelope.get("producer"),          # registered project ref, NOT an enum
        "consumer": envelope.get("consumer"),
        "sourceSoftware": envelope.get("sourceSoftware"),  # client id, kept distinct from project
        "targetSoftware": envelope.get("targetSoftware"),
        "environment": envelope.get("environment", "local"),
        "correlationId": envelope.get("correlationId") or message_id,
        "workUnitId": task_id,
        "taskRevision": task_revision,
        "baseline": baseline,                             # code/workspace baseline
        "bodyDigest": envelope.get("bodyDigest") or body_digest(envelope),
        "artifactRef": baseline.get("digest") or baseline.get("commit") or "",
        "receiptLocation": envelope.get("receiptLocation", ""),
        "targetCapability": envelope.get("targetCapability", ""),
        "authorizationRef": envelope.get("authorizationRef", ""),  # trusted local grant id
        "supersedes": dict(envelope["supersedes"]) if envelope.get("supersedes") else None,
        "classification": classification,
        "rightsStatus": rights_status,
        "createdAt": envelope.get("createdAt", ""),
        "idempotencyKey": envelope.get("idempotencyKey")
        or f"{task_id}:{task_revision}:{_stable_digest(baseline)}",
    }
    # the body travels only via the immutable snapshot reference; the envelope
    # carries its digest so receivers verify rather than re-infer.
    out["taskBody"] = None  # intentional: digest-only, content via artifactRef
    return out


def publish_ready_pointer(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Publish the Ready pointer only after the immutable snapshot is complete."""
    base = envelope.get("baseline") or {}
    base_kind = base.get("kind")
    if base_kind not in BASELINE_KINDS:
        raise ValueError("Ready pointer requires a valid baseline kind")
    if base_kind == "git" and not base.get("commit"):
        return {"ready": False, "reason": "git baseline commit missing; snapshot not complete"}
    if base_kind == "artifact" and not base.get("digest"):
        return {"ready": False, "reason": "artifact digest missing; snapshot not complete"}
    return {"ready": True, "pointer": f"{envelope.get('workUnitId')}@rev{envelope.get('taskRevision')}",
            "digest": envelope.get("bodyDigest")}


def check_authorization(
    envelope: Mapping[str, Any],
    trusted_grants: Mapping[str, str],
) -> dict[str, Any]:
    """Authorization comes ONLY from the trusted local grant record.

    ``trusted_grants`` maps grant_id -> scope (the locally verifiable record).
    Model-mutable payload text (``approved=true`` / ``permission_scope``
    strings) is never a grant: it is ignored by design and reported as such.
    """
    ref = envelope.get("authorizationRef")
    if not ref:
        return {"authorized": False, "reason": "no authorizationRef; no grant is self-conferred"}
    granted_scope = trusted_grants.get(ref)
    if granted_scope is None:
        return {"authorized": False,
                "reason": f"grant {ref!r} not found in trusted local records"}
    payload_claims = envelope.get("payload_claims") or {}
    claims_untrusted = any(
        payload_claims.get(k) for k in ("approved", "scope", "permission_scope")
    )
    return {
        "authorized": True,
        "scope": granted_scope,
        "note": ("payload self-claims were present but IGNORED; the local "
                 "grant record is the only authority" if claims_untrusted else
                 "authorization bound to trusted grant record"),
    }


class RevisionRegistry:
    """Tracks task revisions so a new revision never overwrites old evidence.

    A delivery whose task+revision carries a different body digest is a
    CONFLICT (same task+revision, different content); a HIGHER revision is
    appended (supersede chain preserved), not merged over the older one.
    """

    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}  # task_id -> {rev: record}

    def record(self, envelope: Mapping[str, Any]) -> dict[str, Any]:
        task_id = envelope.get("workUnitId")
        revision = int(envelope.get("taskRevision", 0))
        digest = envelope.get("bodyDigest")
        known = self._records.setdefault(task_id, {})
        existing = known.get(revision)
        if existing is not None:
            if existing["bodyDigest"] != digest:
                return {"status": "CONFLICT", "task_id": task_id, "revision": revision,
                        "reason": "same task+revision carried a different digest; "
                                  "previously approved content is NOT overwritten",
                        "recorded": False}
            return {"status": "ALREADY_RECORDED", "task_id": task_id, "revision": revision,
                    "recorded": False}
        # supersede chain: point at the highest previously recorded revision
        prior_revs = sorted(known.keys())
        known[revision] = {
            "bodyDigest": digest,
            "messageId": envelope.get("messageId"),
            "supersedes_rev": prior_revs[-1] if prior_revs else None,
            "artifactRef": envelope.get("artifactRef"),
        }
        return {"status": "RECORDED", "task_id": task_id, "revision": revision,
                "supersedes_rev": known[revision]["supersedes_rev"], "recorded": True}

    def active_revision(self, task_id: str) -> int | None:
        known = self._records.get(task_id)
        if not known:
            return None
        return max(known.keys())

    def chain(self, task_id: str) -> list[dict[str, Any]]:
        known = self._records.get(task_id, {})
        return [
            {"revision": rev, **rec}
            for rev, rec in sorted(known.items())
        ]

    def late_low_revision_result(self, task_id: str, result_revision: int) -> dict[str, Any]:
        """A late-arriving result for an already-superseded revision is held,
        not allowed to complete a higher revision."""
        active = self.active_revision(task_id)
        if active is not None and result_revision < active:
            return {"status": "HELD_STALE", "result_revision": result_revision,
                    "active_revision": active,
                    "note": "stale result preserved for audit; does not advance rev "
                            f"{active}"}
        return {"status": "ACCEPTED", "result_revision": result_revision,
                "active_revision": active}


def read_v1(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Compatibility read: old three-project v1 messages remain readable."""
    if envelope.get("schemaVersion") != SCHEMA_V1:
        raise ValueError(f"not a v1 envelope (got {envelope.get('schemaVersion')!r})")
    required = {"schemaVersion", "messageId", "producer", "consumer",
                "correlationId", "contentHash", "classification", "rightsStatus",
                "createdAt", "idempotencyKey"}
    missing = required - set(envelope)
    if missing:
        raise ValueError(f"v1 envelope missing required fields: {sorted(missing)}")
    return {"readable": True, "schema": SCHEMA_V1,
            "note": "legacy three-project message kept readable; producer/consumer "
                    "are legacy enum values, not registry references"}


def read_v2(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """A v2 reader must EXPLICITLY reject a v1 message it cannot interpret —
    no silent truncation.  An old reader seeing v2 rejects via the schema
    version const, symmetrically."""
    if envelope.get("schemaVersion") != SCHEMA_V2:
        return {"readable": False, "schema": envelope.get("schemaVersion"),
                "reason": "explicit version rejection: not silently truncated"}
    for field in ("producer", "consumer", "workUnitId", "taskRevision",
                  "bodyDigest", "authorizationRef"):
        if not envelope.get(field):
            return {"readable": False, "reason": f"v2 envelope missing {field!r}"}
    return {"readable": True, "schema": SCHEMA_V2}


def migrate_v1_to_v2(v1: Mapping[str, Any], *, registry_projects: Mapping[str, str],
                      source_software: str, target_software: str,
                      environment: str = "local") -> dict[str, Any]:
    """Incremental migration of a legacy v1 message into registry references.

    ``registry_projects`` maps legacy enum name -> stable opaque project id.
    Unregistered legacy names are refused (fail-closed), never guessed.
    """
    producer = registry_projects.get(v1.get("producer"))
    consumer = registry_projects.get(v1.get("consumer"))
    if producer is None or consumer is None:
        raise ValueError(
            "legacy producer/consumer not in the project registry; refusing to "
            "guess a stable reference (fail-closed)"
        )
    return {
        "schemaVersion": SCHEMA_V2,
        "messageId": v1.get("messageId"),
        "producer": producer,
        "consumer": consumer,
        "sourceSoftware": source_software,
        "targetSoftware": target_software,
        "environment": environment,
        "correlationId": v1.get("correlationId", ""),
        "workUnitId": v1.get("workUnitId", ""),
        "classification": v1.get("classification", "internal"),
        "rightsStatus": v1.get("rightsStatus", "unknown"),
        "createdAt": v1.get("createdAt", ""),
        "idempotencyKey": v1.get("idempotencyKey", ""),
        "migrated_from": SCHEMA_V1,
    }
