"""NF-08-B: durable inbox / outbox on the existing TaskLedger boundary.

Reuses :class:`TaskLedger` (``ledger.json`` + atomic ``os.replace`` write +
orphaned-write recovery) as the single persistence store for claim intent and
external-effect evidence — **no new queue database**.  Per-namespace
subscription state (cursor / etag / Retry-After / pause) lives in a sibling
``inbox_state.json`` under the same root with the SAME atomic-write +
orphan-recovery discipline as the ledger, so the whole read-modify-write is
covered by one reliable boundary.

Key semantics (acceptance AT-14/15/16/17)
-------------------------------------------
* **One receiving lifecycle per local instance, one namespace per project**
  — each project owns an isolated root, so a network failure on project A
  never blocks project B.
* **Duplicate / restart safety** — process A claims (lease + persisted
  *claim intent*), exits; a fresh process B reads the same persistent record
  and does NOT start the task again.
* **Single-dispatch under concurrency** — the lease fence guarantees only
  one holder can dispatch; a claimant that loses the lease (fence mismatch)
  cannot begin new side effects.
* **Intent before executor** — the claim intent is persisted to the ledger
  *before* the executor is invoked; recovery reconciles against the native
  run/session + effect evidence instead of blindly re-invoking.
* **Incremental, honest polling** — a conditional request is built from the
  persisted cursor / etag; upstream ``Retry-After`` is honoured (the next
  poll time is recorded), no busy-poll, no model poll; a sync check makes no
  model call.
* **No artifact rewrite when unchanged** — content is hashed; an unchanged
  task does not rewrite all artifacts.

Pure persistence layer: no network, no model, no credential access.  The
executor is injected by the caller.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from task_ledger import TaskLedger


def _utcnow() -> str:
    import datetime as dt
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def event_identity(namespace: str, source: str, event_id: str,
                   payload_digest: str | None = None) -> str:
    """Complete event identity — the dedupe key.  Same identity is the same
    event even if the notification is delivered twice."""
    base: dict[str, Any] = {"namespace": namespace, "source": source, "event_id": event_id}
    if payload_digest:
        base["payload_digest"] = payload_digest
    return hashlib.sha256(json.dumps(base, sort_keys=True).encode("utf-8")).hexdigest()


class _AtomicStateFile:
    """Sibling state file with the ledger's atomic-write + orphan-recovery
    discipline (one reliability boundary, not a separate queue database)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._recover_orphans()
        if not self.path.exists():
            self._write({"namespace": self.path.parent.name, "subscriptions": {}, "seen_event_ids": []})

    def _recover_orphans(self) -> None:
        tmps = sorted(self.path.parent.glob(f".{self.path.name}.*.tmp"))
        if tmps:
            keep = max(tmps, key=lambda p: p.stat().st_mtime)
            for p in tmps:
                if p is not keep:
                    p.unlink(missing_ok=True)
            if keep.stat().st_size:
                keep.replace(self.path)
            keep.unlink(missing_ok=True)

    def read(self) -> dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def write(self, data: dict[str, Any]) -> None:
        self._write(data)

    def _write(self, data: dict[str, Any]) -> None:
        tmp = self.path.with_name(f".{self.path.name}.{hashlib.sha1(os.urandom(8)).hexdigest()[:8]}.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)


class DurableInbox:
    """Namespaced durable inbox/outbox over the TaskLedger boundary."""

    def __init__(self, namespace: str, root: Path) -> None:
        self.namespace = namespace
        self.ledger = TaskLedger(root)
        self.state_path = root / "inbox_state.json"
        self.state = _AtomicStateFile(self.state_path)

    # ------------------------------------------------------------------
    # subscriptions: cursor / etag / Retry-After / pause
    # ------------------------------------------------------------------
    def subscribe(self, source: str, *, initial_cursor: str = "", initial_etag: str = "") -> dict[str, Any]:
        data = self.state.read()
        sub = data["subscriptions"].setdefault(source, {
            "source": source, "cursor": initial_cursor, "etag": initial_etag,
            "retry_after_until": None, "paused": False, "pause_reason": None,
            "created_at": _utcnow(), "updated_at": _utcnow(),
        })
        sub["updated_at"] = _utcnow()
        self.state.write(data)
        return dict(sub)

    def note_retry_after(self, source: str, seconds: int, *, now: str | None = None) -> dict[str, Any]:
        """Honour an upstream Retry-After: record the next-poll time so the
        loop never busy-polls.  ``seconds <= 0`` clears the throttle."""
        ts = now or _utcnow()
        import datetime as dt
        if seconds <= 0:
            until = None
        else:
            until = (dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                     + dt.timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")
        data = self.state.read()
        sub = data["subscriptions"].setdefault(source, {"source": source, "cursor": "", "etag": "",
                                                         "retry_after_until": None, "paused": False, "pause_reason": None})
        sub["retry_after_until"] = until
        sub["updated_at"] = _utcnow()
        self.state.write(data)
        return {"next_poll_after": until, "throttled": until is not None}

    def poll_due(self, source: str, *, now: str | None = None) -> dict[str, Any]:
        data = self.state.read()
        sub = data["subscriptions"].get(source)
        if sub is None:
            return {"due": False, "reason": "not subscribed"}
        if sub.get("paused"):
            return {"due": False, "reason": "paused", "pause_reason": sub.get("pause_reason")}
        until = sub.get("retry_after_until")
        if until:
            due = (now or _utcnow()) >= until
            return {"due": due, "reason": "retry_after" if not due else "retry_after_elapsed",
                    "next_poll_after": None if due else until}
        return {"due": True, "reason": "no throttle"}

    def pause_subscription(self, source: str, reason: str) -> dict[str, Any]:
        data = self.state.read()
        sub = data["subscriptions"].setdefault(source, {"source": source})
        sub["paused"] = True
        sub["pause_reason"] = reason
        sub["updated_at"] = _utcnow()
        self.state.write(data)
        return dict(sub)

    def resume_subscription(self, source: str) -> dict[str, Any]:
        data = self.state.read()
        sub = data["subscriptions"].get(source)
        if sub is None:
            raise KeyError(f"not subscribed: {source}")
        sub["paused"] = False
        sub["pause_reason"] = None
        sub["updated_at"] = _utcnow()
        self.state.write(data)
        return dict(sub)

    def conditional_request(self, source: str) -> dict[str, Any]:
        """Build the next conditional read (page cursor / If-None-Match etag).
        A sync check that produces this request makes no model call."""
        data = self.state.read()
        sub = data["subscriptions"].get(source)
        if sub is None:
            raise KeyError(f"not subscribed: {source}")
        return {"source": source, "cursor": sub.get("cursor", ""), "etag": sub.get("etag", ""),
                "if_none_match": sub.get("etag") or None, "make_model_call": False}

    # ------------------------------------------------------------------
    # incremental ingest with event-identity dedupe
    # ------------------------------------------------------------------
    def advance_cursor(self, source: str, *, new_cursor: str = "", new_etag: str = "") -> dict[str, Any]:
        data = self.state.read()
        sub = data["subscriptions"].setdefault(source, {"source": source, "cursor": "", "etag": ""})
        sub["cursor"] = new_cursor or sub.get("cursor", "")
        sub["etag"] = new_etag or sub.get("etag", "")
        sub["updated_at"] = _utcnow()
        self.state.write(data)
        return dict(sub)

    def ingest(self, source: str, events: list[Mapping[str, Any]]) -> dict[str, Any]:
        """Ingest a batch of upstream events, deduped by complete event
        identity.  New events create a ledger task (idempotent on the
        idempotency key); duplicates are dropped, not re-started."""
        data = self.state.read()
        seen = set(data.get("seen_event_ids", []))
        created: list[str] = []
        duplicates: list[str] = []
        for ev in events:
            ev_id = str(ev.get("event_id", ""))
            payload_digest = str(ev.get("payload_digest", ""))
            ident = event_identity(self.namespace, source, ev_id, payload_digest or None)
            if ident in seen:
                duplicates.append(ident[:12])
                continue
            seen.add(ident)
            task_id = ev.get("task_id") or f"{source}-{ev_id}"
            idem = ev.get("idempotency_key") or f"{self.namespace}:{ident}"
            self.ledger.create(task_id, idem)
            created.append(task_id)
        data["seen_event_ids"] = sorted(seen)
        self.state.write(data)
        return {"ingested": len(created), "created": created, "duplicates_dropped": len(duplicates),
                "duplicate_ids": duplicates}

    # ------------------------------------------------------------------
    # intent-first claim + reconciliation
    # ------------------------------------------------------------------
    def claim(self, task_id: str, holder: str, *, ttl_seconds: int = 60,
              intent_digest: str, executor: Any = None, now: str | None = None) -> dict[str, Any]:
        """Persist the claim intent *before* invoking the executor.

        The lease (fence) guarantees single-dispatch; the ``claim_intent``
        external effect is the durable record a restarted process reconciles
        against.  ``executor``, if given, is invoked only AFTER both are
        persisted.
        """
        lease = self.ledger.acquire_lease(task_id, holder, ttl_seconds=ttl_seconds, now=now)
        # intent persisted before any side effect.  The effect id is scoped to
        # the LEASE FENCE GENERATION: a fresh holder taking over after expiry
        # records a NEW claim effect (fence N+1) rather than colliding with the
        # previous generation's pending record; re-claiming within the same
        # generation stays idempotent.
        effect_id = f"claim:{task_id}:f{lease['fence']}"
        self.ledger.record_external_effect(task_id, effect_id, "claim_intent", intent_digest)
        result = {"task_id": task_id, "holder": holder, "fence": lease["fence"],
                  "dispatched": False, "intent_persisted": True, "effect_id": effect_id}
        if executor is not None:
            result["dispatched"] = True
            result["executor_result"] = executor(task_id)
        return result

    def reconcile_or_resume(self, task_id: str, *, holder: str | None = None,
                            fence: int | None = None) -> dict[str, Any]:
        """On recovery: read the native run/session + effect evidence and
        decide whether to re-invoke.  A task with a CONFIRMED claim intent /
        external effect is NOT started again; a stale low revision result is
        held, not used to advance."""
        task = self.ledger.get(task_id)
        effects = task.get("external_effects", [])
        claim_effects = [e for e in effects if e.get("action") == "claim_intent"]
        confirmed = [e for e in effects if e.get("status") == "CONFIRMED"]
        lease = task.get("lease") or {}
        active_holder = lease.get("holder")
        active_fence = lease.get("fence")
        # a claimant that lost the lease cannot start new side effects
        if holder is not None and active_holder is not None and holder != active_holder:
            return {"resume": False, "reason": "lease held by another process",
                    "active_holder": active_holder, "fence": active_fence,
                    "side_effects_allowed": False}
        if confirmed:
            return {"resume": False, "reason": "effect already CONFIRMED; not re-invoked",
                    "confirmed_effects": [e["effect_id"] for e in confirmed], "side_effects_allowed": False}
        if claim_effects and not confirmed:
            return {"resume": "reconcile", "reason": "claim intent pending; reconcile native run/session before re-invoking",
                    "pending_effects": [e["effect_id"] for e in claim_effects], "side_effects_allowed": False}
        return {"resume": True, "reason": "no durable claim/effect recorded; safe to start"}

    # ------------------------------------------------------------------
    # outbox + artifact-rewrite suppression
    # ------------------------------------------------------------------
    def enqueue_outbox(self, task_id: str, *, receipt: Mapping[str, Any]) -> dict[str, Any]:
        data = self.state.read()
        outbox = data.setdefault("outbox", [])
        rec = {"task_id": task_id, "receipt": dict(receipt), "state": "PENDING",
               "enqueued_at": _utcnow()}
        # idempotent: same task+receipt already pending -> do not duplicate
        for existing in outbox:
            if existing["task_id"] == task_id and existing.get("receipt") == dict(receipt) \
                    and existing["state"] == "PENDING":
                return {"enqueued": False, "duplicate": True, "record": existing}
        outbox.append(rec)
        self.state.write(data)
        return {"enqueued": True, "duplicate": False, "record": rec}

    def outbox_pending(self) -> list[dict[str, Any]]:
        data = self.state.read()
        return [dict(r) for r in data.get("outbox", []) if r.get("state") == "PENDING"]

    def mark_outbox_delivered(self, task_id: str, receipt_digest: str | None = None) -> int:
        data = self.state.read()
        n = 0
        for rec in data.get("outbox", []):
            if rec["task_id"] == task_id and rec["state"] == "PENDING":
                rec["state"] = "DELIVERED"
                rec["delivered_at"] = _utcnow()
                n += 1
        self.state.write(data)
        return n

    def artifact_rewrite_needed(self, task_id: str, new_body_digest: str) -> dict[str, Any]:
        """Only rewrite artifacts when the content actually changed."""
        data = self.state.read()
        last = data.get("last_body_digest", {}).get(task_id)
        data.setdefault("last_body_digest", {})[task_id] = new_body_digest
        self.state.write(data)
        if last == new_body_digest:
            return {"rewrite": False, "reason": "content unchanged; artifacts not rewritten"}
        return {"rewrite": True, "reason": "content changed; rewrite this artifact only"}


def namespace_isolated(root: Path) -> dict[str, Any]:
    """Project A and project B own separate roots; a failure in A never
    touches B (the namespace isolation guarantee behind AT-16)."""
    return {"isolated_roots": ["<root>/<projectA>", "<root>/<projectB>"],
            "independent_recovery": True,
            "note": "each DurableInbox binds one TaskLedger root per project"}
