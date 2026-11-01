"""OpenHands executor adapter (WL-200 / OPENHANDS_POC).

ch 19 positions OpenHands as a *FleetBackend / RemoteExecutionBackend /
AutomationBackend* POC — it is deliberately **not** a Policy / Evidence /
Knowledge authority.  The adapter therefore advertises only the execution
surface (launch when the backend is reachable, session, stream, cancel)
and defers all governance to the WORK-LAB planes (policy gate, completion
authority, evidence ledger).

The constructor is DI-friendly: a ``reachable`` flag (or a backend URL the
test can stand up) drives launchability; the default reports *not
launchable* so the federation registry never silently claims a remote
backend it has not been told about.
"""
from __future__ import annotations

import importlib.util as _ilu
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


__all__ = ["OpenHandsAdapter"]


class OpenHandsAdapter(_acp().ExecutorAcpAdapter):
    """WORK-LAB wire onto the OpenHands fleet / remote backend (POC)."""

    executor = "openhands"

    def __init__(self, *, backend_url: str | None = None,
                 reachable: bool | None = None,
                 allow_launch: bool = True) -> None:
        # ``reachable`` is the injected probe result.  When None we fall
        # back to "does a backend URL exist" — a URL alone means the
        # backend is *configured*, not necessarily reachable; we say that.
        self._backend_url = backend_url
        self._reachable = reachable
        self._allow_launch = allow_launch

    def is_launchable(self) -> bool:
        if not self._allow_launch:
            return False
        if self._reachable is not None:
            return self._reachable
        # no explicit probe: a configured URL is not proof of reachability
        return False

    def launch_notes(self) -> list[str]:
        notes: list[str] = []
        if not self.is_launchable():
            if self._backend_url:
                notes.append(f"backend {self._backend_url!r} configured but not probed reachable")
            else:
                notes.append("no OpenHands backend configured for this adapter")
        if not self._allow_launch:
            notes.append("launch disabled by policy")
        return notes

    def _capabilities(self) -> frozenset:
        acp = _acp()
        caps = {acp.Capability.CAPABILITIES, acp.Capability.PROBE}
        # OpenHands POC: execution surface only; governance is WORK-LAB's.
        caps |= {acp.Capability.SESSION, acp.Capability.PERSIST,
                 acp.Capability.HANDOFF}
        # RESUME is deliberately NOT declared (AG-06, 2026-10-01): resume() is
        # the base implementation returning NOT_IMPLEMENTED, so declaring the
        # capability would advertise an effect that cannot happen.
        if self.is_launchable():
            caps |= {acp.Capability.LAUNCH, acp.Capability.FORK,
                     acp.Capability.CANCEL, acp.Capability.STREAM}
        # policy/evidence/trace are WORK-LAB planes (not OpenHands authority)
        caps |= {acp.Capability.POLICY, acp.Capability.EVIDENCE,
                 acp.Capability.TRACE, acp.Capability.BUDGET,
                 acp.Capability.ACCEPTANCE}
        return frozenset(caps)

    def health(self) -> dict[str, Any]:
        base = super().health()
        base["backend_url"] = self._backend_url
        base["probed_reachable"] = self._reachable
        return base
