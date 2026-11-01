"""Pi executor adapter (WL-220 / WL-P1-170 PI_EXECUTOR).

ch 21 is explicit that Pi is a *research* executor — minimal agent core,
provider-neutral API, telemetry, lightweight execution — and that **Pi
itself does not provide full file / process / network permission
governance, so it cannot carry WORK-LAB's Policy**.  This adapter
therefore:

* advertises only lightweight execution + telemetry + trace;
* is honest that it is *not* a launchable first-class citizen in a managed
  environment unless explicitly injected as reachable;
* always tags :class:`capabilities` notes with "policy is enforced by the
  WORK-LAB Permission Gate, not by Pi", so no downstream consumer can
  mistake Pi for an authority.
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


__all__ = ["PiAdapter"]


class PiAdapter(_acp().ExecutorAcpAdapter):
    """WORK-LAB wire onto the lightweight Pi research executor."""

    executor = "pi"

    def __init__(self, *, pi_bin: str | None = None,
                 search_path: str | None = None,
                 allow_launch: bool = True) -> None:
        self._pi_bin = pi_bin
        self._search_path = search_path
        self._allow_launch = allow_launch
        self._launchable: bool | None = None

    def _probe(self) -> bool:
        if self._launchable is not None:
            return self._launchable
        if not self._allow_launch:
            self._launchable = False
            return False
        if self._pi_bin:
            self._launchable = (Path(self._pi_bin).exists()
                                or shutil.which(self._pi_bin) is not None)
            return self._launchable
        found = (shutil.which("pi", path=self._search_path)
                 if self._search_path else shutil.which("pi"))
        self._launchable = found is not None
        return self._launchable

    def is_launchable(self) -> bool:
        return self._probe()

    def launch_notes(self) -> list[str]:
        notes = []
        if not self.is_launchable():
            notes.append("pi not on PATH (research executor; launch optional)")
        # ch 21 — the rule every caller must see:
        notes.append("policy is enforced by the WORK-LAB Permission Gate, not by Pi")
        if not self._allow_launch:
            notes.append("launch disabled by policy")
        return notes

    def _capabilities(self) -> frozenset:
        acp = _acp()
        caps = {acp.Capability.CAPABILITIES, acp.Capability.PROBE}
        # lightweight: stream + trace + session; no local policy authority
        caps |= {acp.Capability.SESSION, acp.Capability.TRACE,
                 acp.Capability.EVIDENCE, acp.Capability.HANDOFF}
        if self.is_launchable():
            caps |= {acp.Capability.LAUNCH, acp.Capability.CANCEL,
                     acp.Capability.STREAM}
        # WORK-LAB planes the federation adds on top of any executor:
        caps |= {acp.Capability.POLICY, acp.Capability.BUDGET,
                 acp.Capability.ACCEPTANCE}
        return frozenset(caps)

    def health(self) -> dict[str, Any]:
        base = super().health()
        base["cli_present"] = self.is_launchable()
        base["policy_authority"] = "work-lab-gate"   # never "pi"
        return base
