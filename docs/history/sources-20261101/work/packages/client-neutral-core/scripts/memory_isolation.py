"""Session, memory, and cache isolation (WL3-330 / MR-11).

Namespaces built from user_id / installation_id / project_id / checkout_id /
task_id / provider binding; task-ephemeral vs project-memory vs user-global
layering; TTL, contamination markers, promotion and forgetting.

Contract rules (taskpack §MR-11 acceptance):
- A-project content never enters B-project context
- private task exit leaves no prompt/response body in Telemetry
- stable global rules may be shared; project evidence never shared
- contaminated or expired digests do not participate in routing
- memory promotion requires evidence and approval policy
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "workflow/memory-isolation/v1"
LAYERS = ("user_global", "project_memory", "task_ephemeral")


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


class Namespace:
    """Deterministic, non-secret namespace from identity components."""

    def __init__(self, user_id: str, installation_id: str, project_id: str,
                 checkout_id: str, task_id: str | None = None,
                 provider_binding: str | None = None) -> None:
        self.components = {
            "user_id": user_id,
            "installation_id": installation_id,
            "project_id": project_id,
            "checkout_id": checkout_id,
            "task_id": task_id or "",
            "provider_binding": provider_binding or "",
        }

    def key(self, scope: str) -> str:
        """scope in user_global / project_memory / task_ephemeral."""
        if scope not in LAYERS:
            raise ValueError(f"unknown layer: {scope}")
        parts = []
        if scope == "user_global":
            parts = ["u", self.components["user_id"], self.components["installation_id"]]
        elif scope == "project_memory":
            parts = ["p", self.components["user_id"], self.components["installation_id"],
                     self.components["project_id"], self.components["checkout_id"]]
        else:  # task_ephemeral
            parts = ["t", self.components["user_id"], self.components["project_id"],
                     self.components["task_id"]]
        return ":".join(_hash(p) for p in parts)

    def isolation_key(self) -> str:
        """Full key including provider binding (routing scoping)."""
        base = self.key("task_ephemeral")
        if self.components["provider_binding"]:
            base += ":" + _hash(self.components["provider_binding"])
        return base


class MemoryStore:
    """Layered memory with TTL, contamination, and promotion gating."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        (self.root / "memory").mkdir(parents=True, exist_ok=True)

    def _path(self, ns: Namespace, scope: str, kind: str) -> Path:
        # Windows forbids ':' in file names; the isolation key is hashed anyway.
        safe = f"{scope}-{kind}-{ns.key(scope).replace(':', '_')}.json"
        return self.root / "memory" / safe

    def read(self, ns: Namespace, scope: str, kind: str,
             now: str | None = None) -> list[dict[str, Any]]:
        path = self._path(ns, scope, kind)
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        current = now or _utc_now()
        entries = data.get("entries", [])
        live = []
        for entry in entries:
            if self._expired(entry, current):
                continue
            if entry.get("contaminated"):
                continue
            live.append(entry)
        return live

    def write(self, ns: Namespace, scope: str, kind: str, entry: dict[str, Any]) -> None:
        path = self._path(ns, scope, kind)
        data = {"entries": []}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {"entries": []}
        entry.setdefault("created_at", _utc_now())
        entry.setdefault("contaminated", False)
        data["entries"].append(entry)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def mark_contaminated(self, ns: Namespace, scope: str, kind: str, entry_id: str) -> None:
        path = self._path(ns, scope, kind)
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        for entry in data.get("entries", []):
            if entry.get("id") == entry_id:
                entry["contaminated"] = True
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _expired(entry: dict[str, Any], now: str) -> bool:
        ttl_seconds = entry.get("ttl_seconds")
        if not ttl_seconds:
            return False
        try:
            created = dt.datetime.fromisoformat(entry.get("created_at", now))
            current = dt.datetime.fromisoformat(now)
            return (current - created).total_seconds() > ttl_seconds
        except ValueError:
            return False


class PromotionGate:
    """Memory promotion requires evidence and approval policy."""

    def __init__(self, approval_policy: str = "ask") -> None:
        self.approval_policy = approval_policy

    def can_promote(self, entry: dict[str, Any]) -> tuple[bool, str]:
        if not entry.get("evidence_hash"):
            return False, "memory_promotion_requires_evidence"
        if entry.get("contaminated"):
            return False, "memory_promotion_blocked_contaminated"
        if self.approval_policy == "never":
            return False, "memory_promotion_requires_approval"
        return True, "memory_promotion_approved"


if __name__ == "__main__":
    import project_temp
    with project_temp.fixture_root(prefix='memory-isolation-selftest-') as tmp:
        ns = Namespace("u1", "i1", "p1", "c1", task_id="t1")
        store = MemoryStore(Path(tmp))
        store.write(ns, "task_ephemeral", "notes", {"id": "n1", "text": "x", "ttl_seconds": 60})
        print("read:", store.read(ns, "task_ephemeral", "notes"))
        gate = PromotionGate()
        print("promote no-evidence:", gate.can_promote({"id": "n1"}))
        print("promote with-evidence:", gate.can_promote({"id": "n1", "evidence_hash": "abc"}))
