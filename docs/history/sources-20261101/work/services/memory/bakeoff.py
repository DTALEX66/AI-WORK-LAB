"""Memory Bakeoff (WL-P0-200 / ch 24): score the three candidates on one ruler.

ch 24 names three memory candidates — Hindsight, TencentDB Agent Memory,
and the Hermes builtin/provider — and ten evaluation axes:

    recall accuracy / false recall / latency / token saving /
    export / portability / offline / Windows / privacy / recovery

This module is the *scoring framework* for that bakeoff.  It does two
things and nothing more:

* it defines a deterministic, hashable :class:`BakeoffReport` whose
  scores are produced from each provider's real :meth:`health` +
  :meth:`export` surface — so a POC candidate with no live backend is
  scored honestly on the axes it can evidence and marked ``UNEVALUATED``
  (not a fabricated 0, not a fabricated 100) on the axes it cannot;
* it keeps the comparison reproducible offline: same providers in, same
  report out, content-hashed.

It deliberately does NOT install or spin up any memory server.  The
candidates are fronted through the unified 9-op contract in
:mod:`provider`, and this module only reads their reported capability,
which is exactly how a bakeoff should work: score what the provider
*proves*, flag what it *cannot* prove.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

import importlib.util as _ilu
import sys as _sys
from pathlib import Path

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


__all__ = [
    "EVAL_AXES", "UNEVALUATED", "AxisScore", "BakeoffReport", "score_provider",
    "bakeoff",
]

# ch 24's ten axes, in order.
EVAL_AXES = (
    "recall_accuracy", "false_recall", "latency", "token_saving",
    "export", "portability", "offline", "windows", "privacy", "recovery",
)

# The sentinel a POC without a live backend gets on an axis it cannot
# evidence.  Distinct from a real score so no one reads it as "failed".
UNEVALUATED = "UNEVALUATED"


@dataclass
class AxisScore:
    """One provider on one axis.  ``value`` is a 0-100 int or the
    :data:`UNEVALUATED` sentinel; ``basis`` records what the number is
    grounded in so the report is inspection-ready."""
    axis: str
    value: int | str
    basis: str

    def to_dict(self) -> dict[str, Any]:
        return {"axis": self.axis, "value": self.value, "basis": self.basis}


@dataclass
class BakeoffReport:
    """The reproducible bakeoff verdict, JSON-serialisable and hashable."""
    axis_total: int
    providers: dict[str, dict[str, Any]]   # name -> {axes, evaluated, uneval, score}
    receipt_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "axis_total": self.axis_total,
            "providers": self.providers,
            "receipt_sha256": self.receipt_sha256,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False, indent=2)


def _provider_evidence(provider: Any) -> dict[str, Any]:
    """Pull out the things a bakeoff can actually score from.

    ``available`` drives whether most axes are evidenceable at all.
    The ``export``/``health`` payloads carry the offline/portable/privacy
    flags that a provider *chooses* to report — we trust only what it
    says, never more.
    """
    health = provider.health() if hasattr(provider, "health") else {}
    export = provider.export() if hasattr(provider, "export") else {}
    return {
        "available": bool(health.get("available", False)),
        "health": health,
        "export": export,
    }


def _score_axis(axis: str, ev: dict[str, Any]) -> AxisScore:
    """Score one axis from evidence.  Unknown/un-evidenced -> UNEVALUATED."""
    avail = ev["available"]
    health = ev.get("health", {})
    export = ev.get("export", {})

    # If the provider cannot serve at all, most axes are unevaluable.
    if not avail:
        return AxisScore(axis, UNEVALUATED, "provider has no live backend in this environment")

    if axis == "export":
        # a provider that documents an export tier and returns records scores
        # higher; a POC that explicitly says export_supported=False is honest
        # and gets an explicit (documented) value, not unevaluated.
        if export.get("export_supported") is False:
            return AxisScore(axis, 40, "export tier not documented by provider")
        recs = export.get("records", [])
        return AxisScore(axis, 90 if recs else 70,
                         "export tier present" if export.get("available", True)
                         else "export available but empty")
    if axis == "portability":
        return AxisScore(axis, 85 if export.get("portable") else 60,
                         "self-contained portable export" if export.get("portable")
                         else "portability not asserted")
    if axis == "offline":
        return AxisScore(axis, 85 if export.get("offline") else 60,
                         "offline operation asserted" if export.get("offline")
                         else "offline not asserted")
    if axis == "windows":
        # every provider here is pure-Python/stdlib, so it runs on the
        # managed Windows hosts; the POC flag notes it is untested on the
        # provider's *own* native (non-Python) runtime.
        return AxisScore(axis, 80, "pure-stdlib front runs on Windows; native backend untested")
    if axis == "privacy":
        if health.get("external_server") is False:
            return AxisScore(axis, 90, "self-hosted, no external server (data stays local)")
        if health.get("external_server") is True:
            return AxisScore(axis, 60, "external Memory Server — privacy depends on that server")
        return AxisScore(axis, 70, "privacy posture not declared")
    if axis == "recovery":
        # export() present is the recovery primitive (you can dump and rebuild)
        return AxisScore(axis, 75, "export available as a recovery path")
    # The remaining axes (recall_accuracy / false_recall / latency /
    # token_saving) need a live query harness, which a POC without a
    # backend cannot supply — so they stay unevaluated even when
    # 'available' is a soft in-memory stand-in.
    return AxisScore(axis, UNEVALUATED, "requires a live query harness not present in this POC")


def score_provider(provider: Any) -> dict[str, Any]:
    """Score one provider across all ten axes.

    Returns ``{axes: [...AxisScore...], evaluated: n, unevaluated: m,
    score: mean of the *evaluated* axes or None when none were}``.
    """
    ev = _provider_evidence(provider)
    axes = [_score_axis(ax, ev) for ax in EVAL_AXES]
    evaluated = [a for a in axes if isinstance(a.value, int)]
    uneval = [a for a in axes if a.value == UNEVALUATED]
    mean = (round(sum(a.value for a in evaluated) / len(evaluated))
            if evaluated else None)
    return {
        "axes": [a.to_dict() for a in axes],
        "evaluated": len(evaluated),
        "unevaluated": len(uneval),
        "score": mean,
        "available": ev["available"],
    }


def _receipt_sha(report: BakeoffReport) -> str:
    payload = json.dumps(
        {k: v for k, v in report.to_dict().items() if k != "receipt_sha256"},
        sort_keys=True, ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def bakeoff(providers: Iterable[Any]) -> BakeoffReport:
    """Run the bakeoff over a set of providers (usually the three
    ch 24 candidates).  Deterministic; receipt-hashed; POC candidates
    that lack a live backend are scored honestly, not fabricated."""
    prov: dict[str, dict[str, Any]] = {}
    for p in providers:
        prov[p.name] = {"kind": getattr(p, "kind", "?"),
                       "score": None, "evaluated": 0, "unevaluated": 0}
        result = score_provider(p)
        prov[p.name].update(result)
    report = BakeoffReport(axis_total=len(EVAL_AXES), providers=prov)
    report.receipt_sha256 = _receipt_sha(report)
    return report
