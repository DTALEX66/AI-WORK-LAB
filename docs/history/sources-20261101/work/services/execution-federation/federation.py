"""Executor federation registry — one control plane over all executors.

ch 0 (final positioning) makes WORK-LAB the *client-neutral control plane*
over seven clients.  The Execution Federation Plane (ch 1, ch 17) says the
federation itself is what WORK-LAB owns: a single registry that can

* enumerate every registered executor and its honest capabilities,
* route an ACP operation (new / resume / prompt / stream / cancel / fork /
  permission / capabilities) to the right adapter, and
* aggregate a federation-wide health snapshot for the governance /
  evidence / evaluation planes above it.

The registry is deliberately *passive*: it never launches, spawns, reads
credentials, or applies policy on its own.  Policy decisions flow through
the WORK-LAB Permission Gate (Phase 3); the registry only *tells you what
each executor can do* so the gate and the completion authority can reason
over the whole fleet at once.

Loading convention matches the rest of services/ — no package
``__init__.py``; the base adapter is loaded through the stable module name
so the shared enums stay singletons.
"""
from __future__ import annotations

import importlib.util as _ilu
import sys as _sys
from pathlib import Path
from typing import Any, Mapping, Protocol

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


class _ExecutorLike(Protocol):
    """Structural protocol: anything with these members is a valid adapter."""
    executor: str
    def capabilities(self) -> dict[str, Any]: ...
    def new(self, **kw: Any) -> Any: ...
    def resume(self, session_id: str, **kw: Any) -> Any: ...
    def health(self) -> dict[str, Any]: ...


__all__ = ["ExecutorFederation", "default_federation"]


class ExecutorFederation:
    """Routes ACP operations to registered executor adapters.

    Adapters are registered explicitly; nothing in this module *creates*
    an adapter, so a registry built with an empty :class:`ExecutorFederation`
    answers :meth:`health` with zero executors rather than inventing a
    fleet that does not exist.
    """

    def __init__(self, adapters: Mapping[str, Any] | None = None) -> None:
        self._adapters: dict[str, Any] = dict(adapters or {})
        self._last_result: dict[str, Any] = {}

    # -- fleet composition ------------------------------------------------
    def register(self, adapter: Any) -> None:
        """Register one adapter under its declared executor name.

        Refuses to silently replace an existing adapter of a different type
        (that is almost always a wiring bug, not an upgrade).
        """
        name = adapter.executor
        existing = self._adapters.get(name)
        if existing is not None and not isinstance(existing, type(adapter)):
            # a deliberate same-type re-register is allowed (refresh);
            # a cross-type one is not.
            raise ValueError(
                f"executor {name!r} already registered as "
                f"{type(existing).__name__}; refusing to shadow with "
                f"{type(adapter).__name__}"
            )
        self._adapters[name] = adapter

    def get(self, name: str) -> Any | None:
        return self._adapters.get(name)

    def executors(self) -> list[str]:
        return sorted(self._adapters)

    def __contains__(self, name: str) -> bool:
        return name in self._adapters

    def __len__(self) -> int:
        return len(self._adapters)

    # -- ACP routing ------------------------------------------------------
    def new(self, executor: str, **kw: Any) -> Any:
        return self._route(executor, "new", lambda a: a.new(**kw))

    def resume(self, executor: str, session_id: str, **kw: Any) -> Any:
        return self._route(executor, "resume", lambda a: a.resume(session_id, **kw))

    def prompt(self, executor: str, session_id: str, text: str) -> Any:
        return self._route(executor, "prompt", lambda a: a.prompt(session_id, text))

    def cancel(self, executor: str, session_id: str) -> Any:
        return self._route(executor, "cancel", lambda a: a.cancel(session_id))

    def fork(self, executor: str, session_id: str) -> Any:
        return self._route(executor, "fork", lambda a: a.fork(session_id))

    def capabilities(self, executor: str | None = None) -> dict[str, Any]:
        """Single executor, or the whole fleet when ``executor`` is None."""
        if executor is None:
            return {name: a.capabilities() for name, a in self._adapters.items()}
        return self._route(executor, "capabilities", lambda a: a.capabilities())

    def _route(self, executor: str, op: str, apply) -> Any:
        acp = _acp()
        adapter = self._adapters.get(executor)
        if adapter is None:
            known = ", ".join(self.executors()) or "(none)"
            result = acp.ExecResult(
                acp.Op.CAPABILITIES, executor, ok=False,
                status="UNKNOWN_EXECUTOR",
                notes=[f"executor {executor!r} not registered (known: {known})"],
            )
        else:
            result = apply(adapter)
        self._last_result[executor] = result
        return result

    # -- fleet-wide snapshot --------------------------------------------
    def health(self) -> dict[str, Any]:
        """Aggregate health: per-executor + a fleet-level launch summary.

        ``launchable_fleet`` is the set of executors that can *start* a
        process in this environment — the number the governance plane uses
        to decide whether a task must be federated to a launchable
        executor or degrades to handoff-only.
        """
        per = {name: a.health() for name, a in self._adapters.items()}
        launchable = [
            name for name, a in self._adapters.items() if a.is_launchable()
        ]
        session_only = [
            name for name, a in self._adapters.items()
            if not a.is_launchable() and a.executor != "pi"
        ]
        return {
            "executors": len(self._adapters),
            "per_executor": per,
            "launchable_fleet": launchable,
            "session_only_fleet": session_only,
            "notes": [
                "policy authority is always the WORK-LAB Permission Gate, "
                "never the executor"
            ],
        }


def default_federation() -> ExecutorFederation:
    """A registry pre-populated with the five WORK-LAB executors.

    Every adapter is constructed with its default probe settings, so the
    returned fleet is *honest to the environment it is built in* — on a
    machine where only ``hermes`` is on PATH, only ``hermes`` reports
    launchable; the other four are session / governance wires only.
    """
    fed = ExecutorFederation()
    for mod_name, attr in [
        ("hermes_adapter", "HermesAdapter"),
        ("codex_adapter", "CodexAdapter"),
        ("dsh_adapter", "DshAdapter"),
        ("openhands_adapter", "OpenHandsAdapter"),
        ("pi_adapter", "PiAdapter"),
    ]:
        spec = _ilu.spec_from_file_location(
            f"services_execution_federation_{mod_name}", _HERE / f"{mod_name}.py"
        )
        module = _ilu.module_from_spec(spec)
        _sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        fed.register(getattr(module, attr)())
    return fed
