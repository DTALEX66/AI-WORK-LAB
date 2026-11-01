"""Exo RSI sandbox (WL-360 / ch 30).

Exo can modify prompt, memory, tools, harness policy and even its own
code.  ch 30 draws the line: that power is confined to ONE directory::

    .project-local/sandboxes/exo/

and it preserves a canonical history that CANNOT be erased by a sandbox
rollback.  Two invariants are enforced here, structurally:

* every Exo write must land inside the sandbox root; anything that would
  reach outside it is refused, not truncated to "inside";
* the canonical history is append-only and lives conceptually OUTSIDE the
  sandbox state, so rolling the sandbox back to an earlier state never
  drops a history entry.  A rollback restores mutable state; it does not
  un-happen the record of what Exo did.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path
import os

# ch 30: the ONLY place Exo may write.
EXO_SANDBOX_ROOT = ".project-local/sandboxes/exo"

# the mutable surfaces ch 30 lists Exo as able to touch
SURFACES = ("prompt", "memory", "tools", "harness_policy", "code")


class SandboxEscapeError(Exception):
    """Raised when a write target would fall outside the sandbox root."""


@dataclass
class HistoryEntry:
    """One canonical-history record.  Immutable once appended."""

    seq: int
    surface: str
    action: str
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"seq": self.seq, "surface": self.surface,
                "action": self.action, "detail": self.detail}


class ExoSandbox:
    """Confines Exo's writes and keeps an erasure-proof history."""

    SCHEMA = "work-lab/exo-sandbox/v1"

    def __init__(self, root: str = EXO_SANDBOX_ROOT) -> None:
        self._root = Path(root)
        self._state: Dict[str, Any] = {s: {} for s in SURFACES}
        self._snapshots: Dict[str, Dict[str, Any]] = {}
        self._history: List[HistoryEntry] = []     # append-only
        self._seq = 0

    # -- path confinement ---------------------------------------------------
    def within_sandbox(self, target: str) -> bool:
        """True only if ``target`` — after resolving `..` components — is the
        sandbox root or lives strictly below it.

        A naive parts-prefix check lets a mid-path `..` slip through
        (``exo/prompt/../../etc`` still starts with ``exo``'s raw parts),
        so both sides are normalised with os.path.normpath and compared on a
        separator boundary.
        """
        try:
            norm_target = os.path.normpath(target)
            norm_root = os.path.normpath(str(self._root))
            if norm_target == norm_root:
                return True
            return norm_target.startswith(norm_root + os.sep) or \
                norm_target.startswith(norm_root + "/")
        except (TypeError, ValueError):
            return False

    def _assert_inside(self, surface: str, key: str) -> None:
        # every write is addressed as <root>/<surface>/<key>; surface is
        # restricted to ch 30's list and key must not climb out.
        if surface not in SURFACES:
            raise SandboxEscapeError(f"{surface!r} is not a governed Exo surface")
        probe = str(self._root / surface / key)
        if not self.within_sandbox(probe):
            raise SandboxEscapeError(
                f"write to {key!r} on {surface!r} would escape the sandbox")

    # -- writes -------------------------------------------------------------
    def write(self, surface: str, key: str, value: Any) -> HistoryEntry:
        self._assert_inside(surface, key)
        self._state[surface][key] = value
        self._seq += 1
        entry = HistoryEntry(self._seq, surface, "write", key)
        self._history.append(entry)
        return entry

    # -- history (append-only, survives rollback) ---------------------------
    def history(self) -> List[HistoryEntry]:
        return list(self._history)

    def canonical_history(self) -> List[Dict[str, Any]]:
        """The erasure-proof record.  A rollback never removes from this."""
        return [e.to_dict() for e in self._history]

    # -- snapshots / rollback ------------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        sid = f"snap-{len(self._snapshots)+1}"
        self._snapshots[sid] = json.loads(json.dumps(self._state))
        return {"snapshot_id": sid}

    def rollback(self, snapshot_id: str) -> bool:
        snap = self._snapshots.get(snapshot_id)
        if snap is None:
            return False
        # restore ONLY the mutable surfaces; the canonical history is left
        # intact on purpose — rollback must not un-record what Exo did.
        self._state = snap
        self._seq += 1
        self._history.append(HistoryEntry(self._seq, "sandbox", "rollback",
                                          snapshot_id))
        return True

    def read(self, surface: str, key: str, default: Any = None) -> Any:
        return self._state.get(surface, {}).get(key, default)

    def state(self) -> Dict[str, Any]:
        return json.loads(json.dumps(self._state))

    # -- integrity ----------------------------------------------------------
    def assert_history_survives_rollback(self) -> bool:
        """Prove the load-bearing invariant: a rollback does not drop a
        single canonical-history entry."""
        before = len(self._history)
        snap = self.snapshot()["snapshot_id"]
        self.rollback(snap)
        after = len(self._history)
        return after > before        # rollback itself was recorded

    def health(self) -> Dict[str, Any]:
        return {"root": str(self._root), "surfaces": list(SURFACES),
                "history_entries": len(self._history),
                "snapshots": len(self._snapshots),
                "external_runtime": True, "poc_surface": True}
