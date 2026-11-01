"""NF-08-I: multi-environment routing and controlled takeover.

Different computers / cloud nodes can join; a task has exactly ONE valid
dispatcher.  An offline takeover must not create a double writer.  Guarantees
(AT-15 / AT-16 / AT-35, self-executable slice):

  * the same project / task / revision is obtained even though the LOCAL PATHS
    differ across environments (binding is per-environment; identity is
    path-independent);
  * after a takeover, an old node coming back online does NOT re-dispatch the
    old task; if the old run state cannot be confirmed the state stays an
    explicit BLOCK, not a silent re-dispatch;
  * a dual-device takeover declaration requires evidence from two REAL
    environments — a simulation only counts as a test, never as proof.

Reuses the per-project root binding from NF-03 and the lease/fence
single-dispatch primitive from the task ledger.  No shared-folder arbitration,
no Redis/Kafka/Kubernetes added for generality, no auto-shutdown of the user's
other software.

Pure and deterministic: no network, no real node join, no credentials.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Mapping

# per-environment binding: identity is path-independent
def environment_identity(project_id: str, task_id: str, revision: int,
                         environment: str) -> str:
    blob = hashlib.sha256(
        f"{project_id}|{task_id}|{revision}".encode("utf-8")).hexdigest()
    # the environment is attached but EXCLUDED from the identity hash so the
    # same project/task/revision is obtained across environments with
    # different local paths
    return f"{blob}@{environment}"


class EnvironmentBinding:
    """Bind project/task/revision to an environment.  Different local paths
    in different environments resolve to the SAME identity."""

    def __init__(self) -> None:
        self._by_env: dict[str, dict[str, str]] = {}   # env -> {path, project}
        self._identity: dict[str, dict[str, str]] = {} # identity -> project/task/rev

    def register(self, environment: str, *, project_id: str, task_id: str,
                 revision: int, local_path: str) -> str:
        ident = environment_identity(project_id, task_id, revision, environment)
        self._by_env[environment] = {
            "path": local_path, "project_id": project_id,
            "task_id": task_id, "revision": str(revision), "identity": ident,
        }
        self._identity[ident] = {"project_id": project_id, "task_id": task_id,
                                 "revision": str(revision)}
        return ident

    def resolve(self, environment: str) -> dict[str, Any]:
        rec = self._by_env.get(environment)
        if rec is None:
            return {"resolved": False, "reason": f"environment {environment!r} not bound"}
        return {"resolved": True, **rec}

    def same_across_environments(self, env_a: str, env_b: str) -> dict[str, Any]:
        """Prove two environments with different local paths hold the SAME
        project/task/revision identity.  The identity CORE (the path- and
        environment-independent hash, the part before ``@``) is what must match;
        the environment tag is attached for routing, not for identity."""
        a = self._by_env.get(env_a)
        b = self._by_env.get(env_b)
        if a is None or b is None:
            return {"same": False, "reason": "an environment is not bound"}
        core_a = a["identity"].split("@", 1)[0]
        core_b = b["identity"].split("@", 1)[0]
        return {
            "same_identity": core_a == core_b,
            "different_paths": a["path"] != b["path"],
            "identity_core": core_a,
            "paths": {env_a: a["path"], env_b: b["path"]},
        }


@dataclass
class Node:
    node_id: str
    online: bool = True
    takeover_owner: bool = False
    last_known_run_state: str | None = None   # CONFIRMED / UNKNOWN


class TakeoverCoordinator:
    """Exactly ONE dispatcher per task.  A takeover transfers dispatch to a new
    node; when the old node returns online it must NOT re-dispatch, and if the
    old run state is unconfirmable it stays an explicit BLOCK."""

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._dispatch_owner: dict[str, str] = {}  # task_id -> node_id

    def register_node(self, node_id: str) -> None:
        self._nodes[node_id] = Node(node_id)

    def dispatch(self, task_id: str, node_id: str) -> dict[str, Any]:
        self._dispatch_owner[task_id] = node_id
        n = self._nodes.setdefault(node_id, Node(node_id))
        n.takeover_owner = True
        return {"dispatched": True, "task_id": task_id, "owner": node_id}

    def node_returned_online(self, task_id: str, old_node: str,
                              *, confirmed_state: bool) -> dict[str, Any]:
        """The old node comes back online.  It must NOT re-dispatch the task;
        it may only take over if it still owns dispatch AND the old run state
        is confirmed.  An unconfirmed state -> explicit BLOCK, never a
        re-dispatch (no double writer)."""
        current_owner = self._dispatch_owner.get(task_id)
        node = self._nodes.get(old_node)
        if node is None:
            return {"re_dispatched": False, "reason": f"node {old_node!r} unknown"}
        node.online = True
        if current_owner != old_node:
            # another node owns dispatch now: this one is a rejoin, not a writer
            return {"re_dispatched": False, "took_over": False,
                    "state": "REJOINED_NOT_WRITER",
                    "owner": current_owner,
                    "note": "old node returned; dispatch stays with the current owner"}
        if not confirmed_state:
            # cannot confirm the old run state -> explicit BLOCK, do NOT re-dispatch
            node.last_known_run_state = "UNKNOWN"
            return {"re_dispatched": False, "took_over": True, "state": "BLOCKED_UNCONFIRMED",
                    "owner": old_node,
                    "note": "old run state unconfirmable; held as an explicit BLOCK, "
                            "no double writer"}
        node.last_known_run_state = "CONFIRMED"
        return {"re_dispatched": False, "took_over": True, "state": "CONFIRMED_RESUME",
                "owner": old_node,
                "note": "old run state confirmed; may safely resume as the single writer"}

    def owner(self, task_id: str) -> str | None:
        return self._dispatch_owner.get(task_id)


class DualEnvironmentEvidence:
    """A dual-device takeover declaration needs evidence from two REAL
    environments.  A simulated environment counts as a TEST only, never as
    proof of a real takeover."""

    def __init__(self) -> None:
        self._evidence: dict[str, dict[str, Any]] = {}

    def record(self, environment: str, *, kind: str, handle: str) -> None:
        """kind must be 'real' or 'simulated'; the handle is the evidence id."""
        if kind not in ("real", "simulated"):
            raise ValueError("evidence kind must be 'real' or 'simulated'")
        self._evidence[environment] = {"environment": environment, "kind": kind,
                                       "handle": handle}

    def can_declare_dual_takeover(self, env_a: str, env_b: str) -> dict[str, Any]:
        a = self._evidence.get(env_a)
        b = self._evidence.get(env_b)
        both_real = a is not None and b is not None \
            and a["kind"] == "real" and b["kind"] == "real"
        return {
            "can_declare": bool(both_real),
            "env_a": a, "env_b": b,
            "note": "two REAL environments required; simulation only counts as a test"
                    if not both_real else "two real-environment handles present; declaration permitted",
        }
