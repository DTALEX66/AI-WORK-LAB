"""DSH (DeepSeek Harness) executor adapter (WL-240).

DSH is one of the seven clients WORK-LAB manages (Hermes / Codex / DSH /
GitHub / Open Design / Open Human / CC Switch).  Its native data root is
``~/.dsh``; the session-federation reader (WL-080 DSH_SESSION_READER)
already normalises the uncompressed projcache projection, so this adapter
exposes *session* capability without the DSH desktop binary on PATH.

Honesty rules: launch is reported only when the DSH entry point is
reachable; when it is not, the adapter still offers session read +
handoff + every WORK-LAB governance plane, and says so.
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


__all__ = ["DshAdapter"]


class DshAdapter(_acp().ExecutorAcpAdapter):
    """WORK-LAB wire onto the DSH desktop runtime."""

    executor = "dsh"

    def __init__(self, *, dsh_root: str | None = None,
                 search_path: str | None = None,
                 allow_launch: bool = True) -> None:
        self._dsh_root = dsh_root
        self._search_path = search_path
        self._allow_launch = allow_launch
        self._launchable: bool | None = None

    def _probe(self) -> bool:
        if self._launchable is not None:
            return self._launchable
        if not self._allow_launch:
            self._launchable = False
            return False
        found = (shutil.which("dsh", path=self._search_path)
                 if self._search_path else shutil.which("dsh"))
        self._launchable = found is not None
        return self._launchable

    def is_launchable(self) -> bool:
        return self._probe()

    def launch_notes(self) -> list[str]:
        notes = []
        if not self.is_launchable():
            notes.append("dsh entry point not on PATH; projcache session read still available")
        if not self._allow_launch:
            notes.append("launch disabled by policy")
        return notes

    def _capabilities(self) -> frozenset:
        acp = _acp()
        caps = {acp.Capability.CAPABILITIES, acp.Capability.PROBE}
        caps |= {acp.Capability.SESSION, acp.Capability.PERSIST,
                 acp.Capability.HANDOFF}
        # RESUME is deliberately NOT declared: it is an execution promise whose
        # ACP operation resume() is the base implementation returning
        # NOT_IMPLEMENTED (AG-06, 2026-10-01). Session reading is covered by
        # SESSION/PERSIST; advertising RESUME was a false success surface.
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
        base["data_root"] = self._dsh_root
        base["data_root_exists"] = (
            Path(self._dsh_root).is_dir() if self._dsh_root else False
        )
        return base
