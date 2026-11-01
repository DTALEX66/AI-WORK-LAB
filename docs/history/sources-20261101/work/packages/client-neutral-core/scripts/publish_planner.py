"""NF-08-A: cloud/planner publication planning + per-action permission audit.

Pure, network-free design layer for "a planner with a supported write
interface can publish a selected result to the target project's authoritative
location".  Real publication (server write + read-back) is a separate
authorization-gated step and stays BLOCKED here; this module only produces
the plan and the audit verdicts, so no credential is read or displayed.

Key semantics
-------------
* **Material-class routing** picks the storage target per project and per
  material class; private material never lands in a public target.
* **Large bodies go to a fixed-version artifact first**; the issue / entry
  point carries only a small summary + reference.
* **Per-action permission audit** — file-write, issue-write, comment-write
  are each checked; one ``push=False`` must NOT infer every other action.
* **Read-back verification** — after publication the server ID / revision /
  digest is read back; without write permission the status is
  ``PUBLISH_PENDING_AUTHORIZATION`` (never claimed as success).
* **Idempotency** — a repeated request does not create a duplicate task; a
  lost response is resolved by querying first, then resending.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

PUBLISH_ACTIONS = ("file_write", "issue_write", "comment_write")

# a material class maps to the MINIMUM target visibility it may land in.
MATERIAL_VISIBILITY = {
    "public": {"public", "private"},
    "internal": {"private"},
    "private": {"private"},
    "classified": {"private"},
}

TARGET_PUBLIC = "public"
TARGET_PRIVATE = "private"


class PublishAudit:
    """Per-action write-permission audit against a capability map."""

    def __init__(self, capability_map: Mapping[str, Any]):
        # capability_map: {action_name: "granted" | "denied" | "unknown"}
        # plus optional {"push": bool} which must NOT leak into other actions.
        self._cap = dict(capability_map)

    def _action_state(self, action: str) -> str:
        # push is its own dimension and must not be used to infer file/issue/
        # comment write — each action is read independently.
        if action in self._cap:
            return self._cap[action]
        return "unknown"

    def audit(self, required_actions: tuple[str, ...] = PUBLISH_ACTIONS) -> dict[str, str]:
        verdicts = {a: self._action_state(a) for a in required_actions}
        return verdicts

    def can_proceed(self, required_actions: tuple[str, ...] = PUBLISH_ACTIONS) -> dict[str, Any]:
        verdicts = self.audit(required_actions)
        granted = all(v == "granted" for v in verdicts.values())
        denied = [a for a, v in verdicts.items() if v == "denied"]
        unknown = [a for a, v in verdicts.items() if v == "unknown"]
        status = "PUBLISH_READY" if granted else "PUBLISH_PENDING_AUTHORIZATION"
        return {
            "status": status,
            "verdicts": verdicts,
            "denied": denied,
            "unknown": unknown,
            # without full write permission we must not claim sync success
            "claimed_success": granted,
        }


def _stable(*parts: Any) -> str:
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def route_target(project: str, material_class: str,
                 public_targets: Mapping[str, str],
                 private_targets: Mapping[str, str]) -> dict[str, Any]:
    """Pick the storage target for a project + material class.

    Private / classified / internal material is routed to the private target;
    public material may use the public target.  A private material routed to a
    public target is REJECTED (canary guard), never published.
    """
    if material_class not in MATERIAL_VISIBILITY:
        return {"routed": False, "reason": f"unknown material class {material_class!r}"}
    allowed = MATERIAL_VISIBILITY[material_class]
    # private/never-public classes can only land in a private target
    if "public" not in allowed:
        target = private_targets.get(project)
        if target is None:
            return {"routed": False,
                    "reason": "no private target registered for this project; "
                              "private material will not be auto-published to public"}
        return {"routed": True, "target": target, "visibility": TARGET_PRIVATE,
                "material_class": material_class}
    # public-class material
    public = public_targets.get(project)
    private = private_targets.get(project)
    if public:
        return {"routed": True, "target": public, "visibility": TARGET_PUBLIC,
                "material_class": material_class}
    if private:
        return {"routed": True, "target": private, "visibility": TARGET_PRIVATE,
                "material_class": material_class}
    return {"routed": False, "reason": "no target registered for this project"}


def reject_private_canary_in_public(target_visibility: str,
                                    material_class: str) -> dict[str, Any]:
    """A private / internal / classified canary must not be published to a
    public target.  Returns a hard rejection, not a silent fallback."""
    if target_visibility == TARGET_PUBLIC and material_class in ("internal", "private", "classified"):
        return {"accepted": False,
                "reason": f"{material_class} material is not publishable to a "
                          "public target; route to the private target instead"}
    return {"accepted": True}


def build_publication_plan(*,
                           project: str,
                           task_id: str,
                           body: str,
                           material_class: str,
                           public_targets: Mapping[str, str],
                           private_targets: Mapping[str, str],
                           large_body_threshold: int = 2048,
                           created_at: str = "") -> dict[str, Any]:
    """Build an ordered publication plan.

    Large bodies are saved as a fixed-version artifact FIRST; the issue /
    entry point carries only a small summary + reference to that artifact.
    """
    routing = route_target(project, material_class, public_targets, private_targets)
    if not routing["routed"]:
        return {"planned": False, "reason": routing["reason"]}
    target_visibility = routing["visibility"]
    canary = reject_private_canary_in_public(target_visibility, material_class)
    if not canary["accepted"]:
        return {"planned": False, "reason": canary["reason"]}

    artifact_version = f"v1:{_stable(project, task_id, body)}"
    steps: list[dict[str, Any]] = []
    # step 1: fixed-version artifact first (always, so large bodies are not inlined)
    steps.append({"seq": 1, "action": "file_write",
                  "what": "fixed_version_artifact",
                  "ref": artifact_version,
                  "size": len(body),
                  "large_body": len(body) > large_body_threshold})
    # step 2: issue / entry point with summary + reference (small, not the body)
    summary = body[:128].rstrip()
    steps.append({"seq": 2, "action": "issue_write",
                  "what": "entry_point",
                  "summary": summary,
                  "artifact_ref": artifact_version,
                  "truncates_body": len(body) > 128})
    # step 3: optional comment pointer for review
    steps.append({"seq": 3, "action": "comment_write",
                  "what": "review_pointer",
                  "artifact_ref": artifact_version,
                  "optional": True})

    return {
        "planned": True,
        "project": project,
        "task_id": task_id,
        "target": routing["target"],
        "visibility": target_visibility,
        "material_class": material_class,
        "artifact_version": artifact_version,
        "body_digest": _stable(body),
        "steps": steps,
        "created_at": created_at,
        "idempotency_key": _stable(project, task_id, artifact_version),
    }


def verify_readback(plan: Mapping[str, Any],
                    server: Mapping[str, Any]) -> dict[str, Any]:
    """Read back the published artifact from the server and verify identity.

    The server response must carry a task/issue ID, a revision and a digest
    that matches the plan's body digest.  A mismatch is a FAILURE, not success.
    """
    published_id = server.get("id")
    revision = server.get("revision")
    digest = server.get("digest")
    if published_id is None or revision is None or digest is None:
        return {"verified": False,
                "status": "READBACK_INCOMPLETE",
                "reason": "server read-back missing id/revision/digest"}
    if digest != plan.get("body_digest"):
        return {"verified": False,
                "status": "DIGEST_MISMATCH",
                "server_digest": digest,
                "expected": plan.get("body_digest")}
    return {"verified": True,
            "status": "PUBLISHED",
            "id": published_id,
            "revision": revision,
            "artifact_ref": plan.get("artifact_version")}


class PublicationStore:
    """Idempotent publication state: a repeated request never creates a
    duplicate task; a lost response is resolved by querying, then resending."""

    def __init__(self) -> None:
        self._by_key: dict[str, dict[str, Any]] = {}
        self._seq = 0

    def request_id_for(self, idempotency_key: str) -> str:
        return f"pub_{idempotency_key[:16]}"

    def publish(self, plan: Mapping[str, Any]) -> dict[str, Any]:
        key = plan["idempotency_key"]
        existing = self._by_key.get(key)
        if existing is not None:
            # idempotent: same request returns the same published handle
            return {"created": False, "duplicate": True,
                    "handle": existing["handle"], "id": existing["id"]}
        self._seq += 1
        rid = self.request_id_for(key)
        record = {"handle": rid, "id": rid, "task_id": plan["task_id"],
                  "revision": 1, "status": "published",
                  "artifact_ref": plan["artifact_version"]}
        self._by_key[key] = record
        return {"created": True, "duplicate": False, "handle": rid, "id": rid}

    def reconcile_lost_response(self, plan: Mapping[str, Any]) -> dict[str, Any]:
        """Response lost: query by idempotency key first, only resend if absent."""
        key = plan["idempotency_key"]
        if key in self._by_key:
            rec = self._by_key[key]
            return {"resent": False, "already": True, "id": rec["id"],
                    "note": "matched an existing publication; not resent"}
        out = self.publish(plan)
        out["resent"] = True
        out["already"] = False
        return out
