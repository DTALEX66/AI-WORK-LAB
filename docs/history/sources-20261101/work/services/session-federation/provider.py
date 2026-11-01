"""SessionProvider contract (WL-P0-020).

Every executor adapter implements this interface against its *native,
read-only* session storage.  Providers must never mutate source sessions
(WL-P0-030).  Mutation, index writes and handoff artefacts belong to the
federation layer and land under ``.project-local/``.
"""
from __future__ import annotations

import importlib.util as _ilu
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path as _Path
from typing import Any, Iterable, Mapping, Protocol, runtime_checkable


def _load_canonical():
    """Load canonical.py from the same directory (works under spec-loading too).

    The module is registered in sys.modules before exec so that dataclass
    introspection (which resolves ``cls.__module__`` through sys.modules)
    works even when the loader is not the normal import system.
    """
    here = _Path(__file__).resolve().parent
    name = "services_session_federation_canonical"
    import sys as _sys
    existing = _sys.modules.get(name)
    if existing is not None and getattr(existing, "CanonicalSession", None) is not None:
        return existing
    spec = _ilu.spec_from_file_location(name, here / "canonical.py")
    module = _ilu.module_from_spec(spec)
    _sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_canonical = _load_canonical()
CanonicalSession = _canonical.CanonicalSession
LossReport = _canonical.LossReport


@dataclass(frozen=True)
class SessionRef:
    """Minimal L0 discovery record: *where* a native session lives."""

    source_agent: str
    source_session_id: str
    native_path: str
    project_id: str
    workspace_id: str
    started_at: str | None = None
    ended_at: str | None = None
    native_hash: str | None = None
    model: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_agent": self.source_agent,
            "source_session_id": self.source_session_id,
            "native_path": self.native_path,
            "project_id": self.project_id,
            "workspace_id": self.workspace_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "native_hash": self.native_hash,
            "model": self.model,
        }


@runtime_checkable
class SessionProvider(Protocol):
    """Read-only session discovery/normalisation contract.

    ``discover`` must not raise on an empty/missing store — return an
    empty sequence instead (fail-soft read, fail-closed writes stay in
    the federation layer).
    """

    source_agent: str

    @abstractmethod
    def discover(self, project_id: str) -> Iterable[SessionRef]:
        """L0: enumerate native session locations for a project."""

    @abstractmethod
    def read(self, ref: SessionRef) -> CanonicalSession:
        """Normalise one native session into the canonical model.

        Must be pure/readonly: no writes under the native store.
        """

    @abstractmethod
    def health(self) -> dict[str, Any]:
        """Return provider health: available paths, last verified hash, errors."""

    def search(self, project_id: str, query: str) -> Iterable[SessionRef]:
        """Optional keyword filter over discovered refs; default = all."""
        return list(self.discover(project_id))

    def export(self, session: CanonicalSession, directory: str) -> dict[str, Any]:
        """Write handoff artifacts (handoff.json / capsule.md / loss-report.json)
        under ``directory`` (must be inside .project-local/).  Default writes
        the canonical JSON only; adapters may add native exporters."""
        import json
        from pathlib import Path

        target = Path(directory)
        target.mkdir(parents=True, exist_ok=True)
        out = target / f"{session.source_agent}-{session.source_session_id}.json"
        out.write_text(session.to_json(), encoding="utf-8")
        return {"exported": str(out), "format": "canonical-json", "schema_version": session.to_dict()["schema_version"]}

    def import_session(self, payload: Mapping[str, Any], directory: str) -> CanonicalSession:
        """Rehydrate a canonical session from exported JSON (round-trip)."""
        return CanonicalSession.from_dict(payload)

    # -- handoff (L1 semantic) -----------------------------------------
    def handoff(self, session: CanonicalSession, directory: str) -> dict[str, Any]:
        """Produce the L1 handoff triple: handoff.json, capsule.md, loss-report.json.

        The loss report must reflect what the target agent will NOT get;
        a provider that only supports L1 must report L2/L3 channels as
        unavailable rather than claiming a lossless transfer.
        """
        import json
        from pathlib import Path

        PortabilityLevel = _canonical.PortabilityLevel
        render_capsule = _canonical.render_capsule

        target = Path(directory)
        target.mkdir(parents=True, exist_ok=True)
        level = session.portability_level
        loss = LossReport()
        if level is not PortabilityLevel.L3_NATIVE_RESUME:
            loss.native_state_available = False
        if level is PortabilityLevel.L2_EVENT_REPLAY:
            loss.reasoning = None
        handoff_doc = {
            "schema": "handoff-v1",
            "universal_session_id": session.universal_session_id,
            "from_agent": session.source_agent,
            "level": level.value,
            "session": session.to_dict(),
            "loss_report": loss.to_dict(),
        }
        handoff_path = target / "handoff.json"
        handoff_path.write_text(json.dumps(handoff_doc, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        capsule_path = target / "capsule.md"
        try:
            capsule_path.write_text(render_capsule(session), encoding="utf-8")
        except ValueError:
            # L0-only discovery: no semantic capsule is possible.
            capsule_path.write_text(
                f"(L0 discovery only — no semantic content for {session.universal_session_id})\n",
                encoding="utf-8",
            )
        loss_path = target / "loss-report.json"
        loss_path.write_text(json.dumps(loss.to_dict(), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return {
            "handoff": str(handoff_path),
            "capsule": str(capsule_path),
            "loss_report": str(loss_path),
            "level": level.value,
        }

    def resume_native(self, session: CanonicalSession) -> str:
        """L3: return the exact native resume command for this provider.

        Providers without native resume raise NotImplementedError — callers
        must then downgrade to L1 handoff.  The returned string is a
        template containing ``{session_id}`` unless the provider binds it.
        """
        raise NotImplementedError(f"{self.source_agent} has no native resume")

    def watch(self, project_id: str) -> Iterable[SessionRef]:
        """Poll-based watch: re-run discovery; streaming is out of scope for v1."""
        return list(self.discover(project_id))


__all__ = ["SessionRef", "SessionProvider"]
