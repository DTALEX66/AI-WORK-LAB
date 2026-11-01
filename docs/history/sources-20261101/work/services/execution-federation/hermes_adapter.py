"""Hermes executor adapter (WL-210 / WL-P1-160).

ch 20 says explicitly: Hermes already owns long-term memory, skills,
self-improvement, cron, multi-platform comms, subagents and many
execution backends — WORK-LAB does *not* re-build those.  WORK-LAB only
owns: launch, session, policy, evidence, budget, trace, handoff,
acceptance.  This adapter is the WORK-LAB *wire* onto the Hermes runtime;
it does not implement the runtime.

Design rules honoured here:

* read-only probing — :func:`shutil.which` + directory existence; we never
  spawn a process and never read Hermes credentials / state.db bodies;
* honest capability reporting — :meth:`is_launchable` reflects whether the
  ``hermes`` binary is actually on PATH in *this* environment;
* policy is never the executor's — :meth:`permissions` defers to a
  caller-supplied WORK-LAB Permission Gate (Phase 3), it does not mint
  authorisation itself.

The constructor is dependency-injected so tests can point it at a fake
home / PATH without touching the real machine.
"""
from __future__ import annotations

import importlib.util as _ilu
import shutil
import sys as _sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_ACN = "services_execution_federation_acp_adapter"


def _acp():
    existing = _sys.modules.get(_ACN)
    if existing is not None and hasattr(existing, "ExecutorAcpAdapter"):
        return existing
    spec = _ilu.spec_from_file_location(_ACN, _HERE / "acp_adapter.py")
    module = _ilu.module_from_spec(spec)
    _sys.modules[_ACN] = module
    spec.loader.exec_module(module)
    return module


__all__ = ["HermesAdapter"]


class HermesAdapter(_acp().ExecutorAcpAdapter):
    """The Hermes runtime as a WORK-LAB executor (preferred ACP target)."""

    executor = "hermes"

    #: environment override keys, all optional (dependency-injected).
    def __init__(
        self,
        *,
        hermes_bin: str | None = None,
        search_path: str | None = None,
        home: str | None = None,
        allow_launch: bool = True,
    ) -> None:
        self._hermes_bin = hermes_bin
        self._search_path = search_path
        self._home = home
        self._allow_launch = allow_launch
        self._launchable: bool | None = None   # lazily probed

    # -- probing ---------------------------------------------------------
    def _probe(self) -> bool:
        if self._launchable is not None:
            return self._launchable
        if not self._allow_launch:
            self._launchable = False
            return False
        # explicit binary path wins (a test fixture)
        if self._hermes_bin:
            self._launchable = Path(self._hermes_bin).exists() or (
                shutil.which(self._hermes_bin) is not None
            )
            return self._launchable
        # honour a custom PATH so adapters are testable without a real CLI
        if self._search_path:
            found = shutil.which("hermes", path=self._search_path)
        else:
            found = shutil.which("hermes")
        self._launchable = found is not None
        return self._launchable

    def is_launchable(self) -> bool:
        return self._probe()

    def launch_notes(self) -> list[str]:
        notes: list[str] = []
        if not self.is_launchable():
            notes.append("hermes CLI not found on PATH (no launch in this env)")
        if not self._allow_launch:
            notes.append("launch disabled by policy in this adapter")
        return notes

    def _capabilities(self) -> frozenset:
        acp = _acp()
        caps = {acp.Capability.CAPABILITIES, acp.Capability.PROBE}
        # RESUME is deliberately NOT included: it is an execution promise
        # (Capability.RESUME) whose ACP operation resume() is the base
        # implementation returning NOT_IMPLEMENTED. Advertising it made
        # `supports` a false success surface (AG-06, 2026-10-01; this adapter
        # fixed 2026-10-19). Add it back only with a real native resume.
        if self.is_launchable():
            caps |= {
                acp.Capability.LAUNCH,
                acp.Capability.SESSION,
                acp.Capability.FORK,
                acp.Capability.CANCEL,
                acp.Capability.STREAM,
                acp.Capability.PERSIST,
            }
        # policy / evidence / trace / budget / handoff / acceptance are the
        # WORK-LAB planes that wrap *any* executor — they do not require a
        # launchable CLI, they require the adapter to be registered.
        caps |= {
            acp.Capability.POLICY,
            acp.Capability.EVIDENCE,
            acp.Capability.TRACE,
            acp.Capability.BUDGET,
            acp.Capability.HANDOFF,
            acp.Capability.ACCEPTANCE,
        }
        return frozenset(caps)

    # -- ACP overrides ---------------------------------------------------
    def new(self, *, project_id: str = "", out_dir: str | None = None,
            source_session: Any = None) -> "_acp().ExecResult":
        acp = _acp()
        res = super().new(project_id=project_id, out_dir=out_dir,
                           source_session=source_session)
        # Hermes can open a new session; tag it with the universal id that
        # OTel correlation will join traces on.
        if res.ok:
            res.universal_session_id = f"hermes:{project_id or 'blank'}"
        return res

    def health(self) -> dict[str, Any]:
        base = super().health()
        base["cli_present"] = self.is_launchable()
        return base
