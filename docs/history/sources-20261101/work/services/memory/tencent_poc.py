"""TencentDB Agent Memory POC provider (ch 24 bakeoff candidate).

ch 24 records that TencentDB Agent Memory supports Hermes, Codex and
DeepSeek Harness sharing ONE Memory Server, and exposes four tiers:
Chat Memory / Skill / Wiki / CodeGraph.  This POC fronts that through
the same unified 9-op contract as the other two candidates so the
bakeoff scores all three on identical axes.

Honesty rules (same as every POC here):
* a bare POC with no live ``backend`` handle reports UNAVAILABLE from
  mutating ops and [] from recall — it never claims the Tencent Memory
  Server is up when it has not been handed a live handle;
* the POC exposes the *four documented tiers* as tag namespaces on
  MemoryRecord so a recall can be scoped to Chat / Skill / Wiki /
  CodeGraph, but it does NOT invent extra ops beyond what ch 24 lists.
"""
from __future__ import annotations

import importlib.util as _ilu
import sys as _sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_MOD = "services_memory_provider"


def _base():
    existing = _sys.modules.get(_MOD)
    if existing is not None and hasattr(existing, "MemoryProvider"):
        return existing
    spec = _ilu.spec_from_file_location(_MOD, _HERE / "provider.py")
    module = _ilu.module_from_spec(spec)
    _sys.modules[_MOD] = module
    spec.loader.exec_module(module)
    return module


__all__ = ["TencentMemoryPoc", "TIER_TAGS"]

# The four documented tiers, as tag namespaces a recall can scope to.
TIER_TAGS = ("chat_memory", "skill", "wiki", "codegraph")


class TencentMemoryPoc(_base().MemoryProvider):
    """TencentDB Agent Memory as a bakeoff POC candidate."""

    name = "tencent-memory"
    kind = "poc"

    def __init__(self, backend: Any | None = None) -> None:
        super().__init__()
        self._backend = backend
        if backend is not None:
            try:
                for rid, rec in backend.items():
                    self._store[rid] = rec
            except AttributeError:
                pass

    def _available(self) -> bool:
        return self._backend is not None or bool(self._store)

    def health(self) -> dict[str, Any]:
        h = super().health()
        h["poc"] = True
        h["external_server"] = True       # it IS a shared Memory Server
        h["shared_by"] = ["hermes", "codex", "dsh"]
        h["tiers"] = list(TIER_TAGS)
        return h
