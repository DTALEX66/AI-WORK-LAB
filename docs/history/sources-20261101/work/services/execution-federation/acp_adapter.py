"""Unified executor-ACP adapter interface for WORK-LAB Execution Federation.

ch 17 (WL-P0-130 EXECUTOR_ACP_ADAPTER) defines the five operations a
WORK-LAB executor adapter must expose to the federation:

    new   resume   prompt   stream   cancel   fork   permission   capabilities

plus the launch / session / policy / evidence / budget / trace / handoff /
acceptance control planes that ch 20 (WL-P1-160) says WORK-LAB does *not*
re-invent — it wires to each executor's own runtime for those.

The one hard rule: *the executor is never the final authorising source.*
Every decision that affects state crosses the WORK-LAB Permission Gate
(Phase 3) before it reaches an executor.  This module provides:

* :class:`Capability` — the enumeration of what an adapter can do.
* :class:`ExecResult` — the typed result of any ACP operation.
* :class:`ExecutorAcpAdapter` — the abstract base each executor (Hermes,
  Codex, DSH, OpenHands, Pi) implements.

Loading convention matches the rest of services/: no package __init__.py;
sibling modules are loaded via a stable ``sys.modules`` name so the
Capability enum stays a singleton.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

import importlib.util as _ilu

__all__ = [
    "Capability", "Op", "ExecResult", "ExecutorAcpAdapter",
    "launch_status_for",
]


class Op(str, Enum):
    """The eight ACP federation operations a caller may issue."""
    NEW = "new"
    RESUME = "resume"
    PROMPT = "prompt"
    STREAM = "stream"
    CANCEL = "cancel"
    FORK = "fork"
    PERMISSION = "permission"
    CAPABILITIES = "capabilities"


class Capability(str, Enum):
    """What an adapter can actually do today.

    Every adapter returns an honest subset — *not* the full set.  An
    executor whose binary is not on PATH reports :meth:`launchable`
    False rather than silently failing at launch time.
    """
    LAUNCH = "launch"                  # can start a fresh executor process
    SESSION = "session"                # can read/write native session state
    POLICY = "policy"                  # can apply a WORK-LAB permission policy
    EVIDENCE = "evidence"              # can emit evidence artifacts
    BUDGET = "budget"                  # can enforce a cost/budget ceiling
    TRACE = "trace"                    # can emit an OTel trace context
    HANDOFF = "handoff"               # can produce a loss-report handoff
    ACCEPTANCE = "acceptance"         # can record a typed completion record
    RESUME = "resume"                 # can resume a native session
    FORK = "fork"                     # can fork a running session
    CANCEL = "cancel"                 # can cancel a running session
    STREAM = "stream"                 # can stream output back
    CAPABILITIES = "capabilities"     # this query itself is always available
    PERSIST = "persist"               # can write session data to disk
    PROBE = "probe"                   # can do a read-only availability probe


class ExecResult:
    """Typed result of an ACP operation.

    Never raises for a *known* degraded state (tool not installed,
    operation not supported, etc.).  ``ok`` is True only when the
    operation actually produced the requested effect.  ``notes`` carries
    the reason for any degradation so the caller can act on it.
    """

    __slots__ = ("op", "ok", "executor", "status", "payload", "notes",
                 "universal_session_id", "loss_report")

    def __init__(
        self,
        op: Op,
        executor: str,
        *,
        ok: bool = True,
        status: str = "OK",
        payload: Mapping[str, Any] | None = None,
        notes: Iterable[str] = (),
        universal_session_id: str | None = None,
        loss_report: Mapping[str, Any] | None = None,
    ) -> None:
        self.op = op
        self.executor = executor
        self.ok = ok
        self.status = status
        self.payload = dict(payload or {})
        self.notes = list(notes)
        self.universal_session_id = universal_session_id
        self.loss_report = dict(loss_report or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.op.value,
            "executor": self.executor,
            "ok": self.ok,
            "status": self.status,
            "payload": self.payload,
            "notes": self.notes,
            "universal_session_id": self.universal_session_id,
            "loss_report": self.loss_report,
        }

    def __repr__(self) -> str:
        return (f"ExecResult(op={self.op.value!r}, executor={self.executor!r}, "
                f"ok={self.ok}, status={self.status!r})")


class ExecutorAcpAdapter:
    """Abstract base for every WORK-LAB executor adapter.

    Subclasses must set :attr:`executor` (the agent name, e.g. ``"hermes"``)
    and override :meth:`_capabilities` to return the *actual* capability
    set.  All other methods have a safe default (degraded :class:`ExecResult`
    with an explanatory note) so callers never get an ``AttributeError``
    when asking an adapter for something it has not yet implemented.
    """

    executor: str = "base"

    # -- capabilities ----------------------------------------------------
    def _capabilities(self) -> frozenset[Capability]:
        # base: only self-query and probe; concrete adapters extend this.
        return frozenset({Capability.CAPABILITIES, Capability.PROBE})

    def capabilities(self) -> dict[str, Any]:
        """Report what this adapter can honestly do.

        * ``launchable`` — True when the adapter's native binary is on PATH
          or a process-supervisor is already running and reachable.
        * ``supports``   — the capability subset.
        * ``notes``      — human-readable caveats (e.g. "no CLI on PATH").
        """
        return {
            "executor": self.executor,
            "supports": sorted(c.value for c in self._capabilities()),
            "launchable": self.is_launchable(),
            "notes": self.launch_notes(),
        }

    # -- launch probes ----------------------------------------------------
    def is_launchable(self) -> bool:
        """Read-only check: can we start a fresh process?  Never spawns."""
        return Capability.LAUNCH in self._capabilities()

    def launch_notes(self) -> list[str]:
        return []

    # -- ACP operations (safe defaults for unimplemented) -----------------
    def new(self, *, project_id: str = "", out_dir: str | None = None,
            source_session: Any | None = None) -> ExecResult:
        if Capability.LAUNCH not in self._capabilities():
            return ExecResult(Op.NEW, self.executor, ok=False,
                              status="NOT_LAUNCHABLE",
                              notes=[f"{self.executor} is not launchable in this environment"])
        return ExecResult(Op.NEW, self.executor, ok=False, status="NOT_IMPLEMENTED",
                          payload={"project_id": project_id},
                          universal_session_id=None)

    def resume(self, session_id: str, *, out_dir: str | None = None) -> ExecResult:
        if Capability.RESUME not in self._capabilities():
            return ExecResult(Op.RESUME, self.executor, ok=False,
                              status="NOT_SUPPORTED",
                              payload={"session_id": session_id},
                              notes=[f"{self.executor} does not support native resume"])
        return ExecResult(Op.RESUME, self.executor, ok=False, status="NOT_IMPLEMENTED",
                          payload={"session_id": session_id})

    def prompt(self, session_id: str, text: str) -> ExecResult:
        if Capability.STREAM not in self._capabilities():
            return ExecResult(Op.PROMPT, self.executor, ok=False,
                              status="NOT_SUPPORTED",
                              notes=[f"{self.executor} prompt not yet wired"])
        return ExecResult(Op.PROMPT, self.executor, ok=False, status="NOT_IMPLEMENTED",
                          payload={"session_id": session_id, "chars": len(text)})

    def cancel(self, session_id: str) -> ExecResult:
        if Capability.CANCEL not in self._capabilities():
            return ExecResult(Op.CANCEL, self.executor, ok=False,
                              status="NOT_SUPPORTED",
                              notes=[f"{self.executor} cancel not yet wired"])
        return ExecResult(Op.CANCEL, self.executor, ok=False, status="NOT_IMPLEMENTED",
                          payload={"session_id": session_id})

    def fork(self, session_id: str) -> ExecResult:
        if Capability.FORK not in self._capabilities():
            return ExecResult(Op.FORK, self.executor, ok=False,
                              status="NOT_SUPPORTED",
                              notes=[f"{self.executor} fork not yet wired"])
        return ExecResult(Op.FORK, self.executor, ok=False, status="NOT_IMPLEMENTED",
                          payload={"source": session_id})

    # -- lifecycle / helpers ---------------------------------------------
    def health(self) -> dict[str, Any]:
        """Read-only liveness: binary on PATH / data dir present / version."""
        return {
            "executor": self.executor,
            "launchable": self.is_launchable(),
            "notes": self.launch_notes(),
        }

    def __repr__(self) -> str:
        caps = self._capabilities()
        return f"{type(self).__name__}(executor={self.executor!r}, caps={len(caps)})"
