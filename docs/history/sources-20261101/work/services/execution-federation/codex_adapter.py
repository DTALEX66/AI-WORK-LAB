"""Codex executor adapter (WL-230).

Codex is a first-class WORK-LAB executor: it has a native session store
(``~/.codex/sessions``) that the session-federation reader already
normalises (WL-070 CODEX_SESSION_READER), so this adapter exposes the
*session* capability for free.  Launch capability is reported honestly:
the ``codex`` CLI is frequently *not* on PATH in a managed environment,
in which case the adapter refuses to claim launch rather than fail at
runtime.

The native resume path is an L1 *handoff* (a new Codex session seeded from
the portable triple), never a native L3 resume — matching the portability
contract in services/session-federation.
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


__all__ = ["CodexAdapter"]


class CodexAdapter(_acp().ExecutorAcpAdapter):
    """WORK-LAB wire onto the Codex CLI executor."""

    executor = "codex"

    def __init__(self, *, codex_bin: str | None = None,
                 search_path: str | None = None,
                 home: str | None = None,
                 allow_launch: bool = True) -> None:
        self._codex_bin = codex_bin
        self._search_path = search_path
        self._home = home
        self._allow_launch = allow_launch
        self._launchable: bool | None = None

    def _probe(self) -> bool:
        if self._launchable is not None:
            return self._launchable
        if not self._allow_launch:
            self._launchable = False
            return False
        if self._codex_bin:
            self._launchable = (Path(self._codex_bin).exists()
                                or shutil.which(self._codex_bin) is not None)
            return self._launchable
        found = (shutil.which("codex", path=self._search_path)
                 if self._search_path else shutil.which("codex"))
        self._launchable = found is not None
        return self._launchable

    def is_launchable(self) -> bool:
        return self._probe()

    def launch_notes(self) -> list[str]:
        notes = []
        if not self.is_launchable():
            notes.append("codex CLI not on PATH; session reader + handoff still available")
        if not self._allow_launch:
            notes.append("launch disabled by policy")
        return notes

    def _capabilities(self) -> frozenset:
        acp = _acp()
        caps = {acp.Capability.CAPABILITIES, acp.Capability.PROBE}
        # Session READING works off the native store even without the CLI.
        # RESUME is deliberately NOT included: it is an execution promise
        # (Capability.RESUME) whose ACP operation resume() is the base
        # implementation returning NOT_IMPLEMENTED. Advertising it made
        # `supports` a false success surface (AG-06, 2026-10-01). Add it back
        # only together with a real native resume implementation.
        caps |= {acp.Capability.SESSION, acp.Capability.PERSIST,
                 acp.Capability.HANDOFF}
        if self.is_launchable():
            caps |= {acp.Capability.LAUNCH, acp.Capability.FORK,
                     acp.Capability.CANCEL, acp.Capability.STREAM}
        caps |= {acp.Capability.POLICY, acp.Capability.EVIDENCE,
                 acp.Capability.TRACE, acp.Capability.BUDGET,
                 acp.Capability.ACCEPTANCE}
        return frozenset(caps)

    def health(self) -> dict[str, Any]:
        base = super().health()
        base["cli_present"] = self.is_launchable()
        base["session_store_readable"] = bool(self._home)
        return base
