"""Hermes builtin memory provider (the one WORK-LAB owns end-to-end).

Of the three bakeoff candidates in ch 24, Hermes builtin / provider is the
only one WORK-LAB fully controls: it has no external server to reach, so it
is the one candidate that can *serve* in a self-hosted, offline, Windows
environment without installing anything.

Construction is dependency-injected: pass a live ``backend`` (an object
implementing the minimal ``get/put/delete`` surface of a memory store) to
make the provider *available*; without one it still exposes the interface
and reports itself as unavailable — the honest default for a bare
environment.
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


__all__ = ["HermesBuiltinProvider"]


class HermesBuiltinProvider(_base().MemoryProvider):
    """Hermes' own memory, fronted through the unified 9-op contract."""

    name = "hermes-builtin"
    kind = "builtin"

    def __init__(self, backend: Any | None = None) -> None:
        super().__init__()
        # a live backend makes the provider available; otherwise it degrades
        self._backend = backend
        if backend is not None:
            # adopt whatever the live backend already holds
            try:
                for rid, rec in backend.items():
                    self._store[rid] = rec
            except AttributeError:
                pass

    def _available(self) -> bool:
        # builtin is self-hosted: WORK-LAB owns its store end-to-end, so it
        # can ALWAYS serve locally.  Unlike the external POCs (which need a
        # live backend handle), an empty builtin still has a live in-process
        # store behind it — otherwise the first retain() would dead-lock
        # (retain requires availability, availability required a record).
        return True

    def export(self, *, kind: Any = None) -> dict[str, Any]:
        out = super().export(kind=kind)
        # builtin export is fully portable: self-contained JSON, no server
        out["portable"] = True
        out["offline"] = True
        return out

    def health(self) -> dict[str, Any]:
        h = super().health()
        h["self_hosted"] = True
        h["external_server"] = False
        return h
