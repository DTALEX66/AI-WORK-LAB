"""NF-08-G: a second transport channel + non-Git project round trip.

Prove the workflow is NOT locked to GitHub: the same business handoff can
round-trip through both a GitHub channel and a FILE channel with the CORE
dispatch code unchanged.  A third, NON-Git example project completes an
artifact round trip.  Incomplete / malicious inputs (half-upload,
expired or missing attachment, duplicate file, path traversal) never start a
task.

Reuses the non-Git artifact-baseline semantics from NF-03
(``project_binding_registry``) and the v2 dispatch envelope from NF-08-0 — the
channel is a thin transport, not a new dispatch model.

Pure and deterministic: channels are in-memory / path-simulated; no real
GitHub API call, no installed file-sync software, no network.
"""
from __future__ import annotations

import hashlib
import json
import posixpath
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


def _digest(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _stable(*parts: Any) -> str:
    def _enc(o: Any) -> Any:
        if isinstance(o, bytes):
            return "bytes:" + o.hex()
        return repr(o)
    blob = json.dumps(list(parts), sort_keys=True, ensure_ascii=False, default=_enc)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class BusinessHandoff:
    """The business payload a transport carries — identical across channels."""
    task_id: str
    revision: int
    artifact_digest: str
    body: bytes
    material_class: str = "internal"

    def fingerprint(self) -> str:
        return _stable(self.task_id, self.revision, self.artifact_digest,
                       self.body, self.material_class)


class Channel(Protocol):
    """A transport channel.  Both channels must deliver the same handoff so
    the CORE dispatch code is channel-agnostic (the 'no lock to GitHub' row)."""
    name: str

    def send(self, handoff: BusinessHandoff) -> dict[str, Any]: ...
    def receive(self, reference: Mapping[str, Any]) -> dict[str, Any]: ...


class GitHubChannel:
    """A simulated GitHub transport (issue/artifact reference semantics)."""
    name = "github"

    def __init__(self) -> None:
        self._store: dict[str, BusinessHandoff] = {}

    def send(self, handoff: BusinessHandoff) -> dict[str, Any]:
        ref = f"issue://{handoff.task_id}/r{handoff.revision}"
        self._store[ref] = handoff
        return {"reference": ref, "channel": self.name,
                "artifact_digest": handoff.artifact_digest}

    def receive(self, reference: Mapping[str, Any]) -> dict[str, Any]:
        ref = reference.get("reference", "")
        handoff = self._store.get(ref)
        if handoff is None:
            return {"received": False, "reason": f"reference {ref!r} not found"}
        return {"received": True, "channel": self.name, "handoff": handoff}


class FileChannel:
    """A simulated file-based transport (artifact directory + pointer file).

    Path safety: references are resolved inside the store root; an attempt to
    escape it (path traversal) is rejected and NEVER starts a task."""

    name = "file"

    def __init__(self, store_root: str = "/store") -> None:
        self.store_root = store_root.rstrip("/") or "/"
        self._store: dict[str, BusinessHandoff] = {}
        self._pointers: dict[str, str] = {}

    def _safe_ref(self, reference_id: str) -> str | None:
        """Resolve a reference to a safe in-root path; None if it escapes."""
        if not reference_id:
            return None
        candidate = posixpath.normpath(posixpath.join(self.store_root, reference_id))
        root = posixpath.normpath(self.store_root)
        if not (candidate == root or candidate.startswith(root + "/")):
            return None  # traversal out of the store root
        return candidate

    def send(self, handoff: BusinessHandoff) -> dict[str, Any]:
        ref_id = f"artifacts/{handoff.task_id}/r{handoff.revision}.bin"
        safe = self._safe_ref(ref_id)
        if safe is None:
            return {"sent": False, "reason": "path traversal blocked"}
        self._store[safe] = handoff
        self._pointers[safe] = ref_id
        return {"reference": ref_id, "channel": self.name, "stored_path": safe,
                "artifact_digest": handoff.artifact_digest}

    def receive(self, reference: Mapping[str, Any]) -> dict[str, Any]:
        ref_id = reference.get("reference", "")
        # a reference that tries to escape the store root is refused
        safe = self._safe_ref(ref_id)
        if safe is None:
            return {"received": False, "reason": "path traversal blocked; no task started"}
        handoff = self._store.get(safe)
        if handoff is None:
            return {"received": False, "reason": f"artifact {ref_id!r} missing"}
        return {"received": True, "channel": self.name, "handoff": handoff}


class TransportRouter:
    """Runs the SAME business handoff through two channels and proves the core
    dispatch code (the handoff payload + fingerprint) is unchanged — the
    channel is a thin transport."""

    def __init__(self, *channels: Channel) -> None:
        if len(channels) < 2:
            raise ValueError("a second channel is required to prove no GitHub lock")
        self.channels = list(channels)

    def round_trip_consistency(self, handoff: BusinessHandoff) -> dict[str, Any]:
        results = []
        for ch in self.channels:
            sent = ch.send(handoff)
            received = ch.receive({"reference": sent.get("reference", "")})
            got = received.get("handoff")
            results.append({
                "channel": ch.name,
                "consistent": got is not None and got.fingerprint() == handoff.fingerprint(),
                "fingerprint": got.fingerprint() if got else None,
            })
        core_unchanged = all(r["consistent"] for r in results)
        return {"channels": results, "core_dispatch_unchanged": core_unchanged,
                "business_fingerprint": handoff.fingerprint()}


# ---------------------------------------------------------------------------
# input guards: incomplete / malicious inputs never start a task
# ---------------------------------------------------------------------------

def guard_half_upload(payload: Mapping[str, Any], *, expected_size: int) -> dict[str, Any]:
    """A half-uploaded body (shorter than the declared size) must NOT start a
    task; it is held as incomplete until complete."""
    body = payload.get("body", b"")
    complete = len(body) == expected_size
    return {"task_started": False, "complete": complete,
            "reason": "complete; may proceed" if complete else
                      f"half-upload ({len(body)}/{expected_size}); task not started"}


def guard_attachment(attachment: Mapping[str, str], *, now_ts: int,
                     max_age_s: int = 3600) -> dict[str, Any]:
    """An expired or missing attachment does NOT start a task."""
    if not attachment or not attachment.get("digest") or not attachment.get("uploaded_at"):
        return {"task_started": False, "reason": "attachment missing or incomplete"}
    age = now_ts - int(attachment["uploaded_at"])
    if age > max_age_s:
        return {"task_started": False, "reason": f"attachment expired ({age}s > {max_age_s}s)"}
    return {"task_started": True, "reason": "attachment valid"}


def dedupe_files(existing: Mapping[str, str], incoming: Mapping[str, str]) -> dict[str, Any]:
    """Duplicate files (same path + digest already present) are NOT re-started;
    a NEW file with the same path but a different digest is a CONFLICT, not a
    silent overwrite."""
    started: list[str] = []
    duplicates: list[str] = []
    conflicts: list[str] = []
    for path, digest in incoming.items():
        prior = existing.get(path)
        if prior is None:
            started.append(path)
        elif prior == digest:
            duplicates.append(path)
        else:
            conflicts.append(path)
    return {"started": started, "duplicates": duplicates, "conflicts": conflicts,
            "task_started_count": len(started),
            "note": "duplicates dropped; conflicts not silently overwritten"}


class NonGitArtifactRoundTrip:
    """A third, NON-Git project completes an artifact round trip: publish a
    fixed-version artifact, execute from the reference (never the body inline),
    return a receipt bound to the artifact digest.  The baseline kind is
    'artifact' (digest), not 'git' (commit)."""

    def __init__(self, project: str) -> None:
        self.project = project
        self.published: dict[str, dict[str, Any]] = {}
        self.receipts: list[dict[str, Any]] = []

    def publish(self, task_id: str, revision: int, body: bytes) -> dict[str, Any]:
        digest = _digest(body)
        artifact_version = f"artifact:{task_id}:r{revision}:{digest[:12]}"
        # the body is stored ONLY as the fixed-version artifact; callers hold
        # the reference, not the body
        self.published[artifact_version] = {"task_id": task_id, "revision": revision,
                                            "digest": digest, "baseline_kind": "artifact"}
        return {"published": True, "artifact_version": artifact_version, "digest": digest,
                "baseline_kind": "artifact"}

    def execute_from_reference(self, artifact_version: str) -> dict[str, Any]:
        rec = self.published.get(artifact_version)
        if rec is None:
            return {"executed": False, "reason": f"unknown artifact {artifact_version!r}"}
        return {"executed": True, "task_id": rec["task_id"], "revision": rec["revision"],
                "artifact_digest": rec["digest"], "baseline_kind": "artifact",
                "body_inlined": False}

    def return_receipt(self, artifact_version: str, *, execution_completed: bool) -> dict[str, Any]:
        rec = self.published.get(artifact_version)
        if rec is None:
            return {"returned": False, "reason": "no such artifact to return a receipt for"}
        receipt = {"project": self.project, "task_id": rec["task_id"],
                   "task_revision": rec["revision"], "artifact_digest": rec["digest"],
                   "execution_completed": execution_completed, "baseline_kind": "artifact",
                   "status": "RECEIPT_PUBLISHED" if execution_completed else "RECEIPT_PUBLISHED"}
        self.receipts.append(receipt)
        return {"returned": True, "receipt": receipt}
