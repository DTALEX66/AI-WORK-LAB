"""Hindsight memory POC provider (ch 24 bakeoff candidate).

ch 24 records that Hindsight supports retain / recall / reflect across a
large set of coding agents and offers Windows + local/self-hosted
operation.  This POC provider fronts Hindsight through the same unified
9-op contract as the Hermes builtin so the bakeoff can score them on
identical axes.

Honesty rules for a POC:
* the provider only *serves* when handed a live Hindsight store handle
  (``backend``).  A bare POC with no backend reports UNAVAILABLE from
  every mutating op and [] from recall — it does NOT fabricate a recall
  and does NOT claim Hindsight is running when it is not.
* the POC implements the three Hindsight-native tiers (retain/recall/
  reflect); the import_* and export tiers are reported as
  NOT_SUPPORTED so the bakeoff scores Hindsight's real surface, not an
  imagined one.
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


__all__ = ["HindsightPoc"]


class HindsightPoc(_base().MemoryProvider):
    """Hindsight as a bakeoff POC candidate."""

    name = "hindsight"
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
        h["external_server"] = self._backend is None and not self._store
        h["supports"] = ["retain", "recall", "reflect"]
        return h

    # POC surface: retain/recall/reflect only; import/export are NOT
    # part of Hindsight's documented tier and stay NOT_SUPPORTED.
    def export(self, *, kind: Any = None) -> dict[str, Any]:
        # Hindsight POC: export is not a documented tier; report it as
        # unsupported rather than inventing a format.
        return {
            "provider": self.name,
            "available": self._available(),
            "records": [],
            "export_supported": False,
            "note": "Hindsight POC does not document an export tier",
        }
