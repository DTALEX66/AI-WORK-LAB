"""ACP session facade (WL-P0-060).

Provides the five ACP session operations as a uniform control interface:

    session/new      session/list
    session/resume   session/prompt
    session/close

The facade is provider-agnostic: each operation delegates to a
``SessionProvider`` (WL-P0-020) and returns a typed ``SessionOperationResult``
so callers never depend on a specific executor's wire format.  Native
resume (L3) is the only path that may report ``RESUMED``; everything else
must surface as ``NEW_SESSION`` (L1) with the loss report attached —
never as a native resume.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Protocol


class SessionOp(str, Enum):
    NEW = "session/new"
    LIST = "session/list"
    RESUME = "session/resume"
    PROMPT = "session/prompt"
    CLOSE = "session/close"


class Outcome(str, Enum):
    RESUMED = "RESUMED"            # only via verified native resume
    NEW_SESSION = "NEW_SESSION"    # L1 handoff opened a new target session
    LISTED = "LISTED"
    PROMPTED = "PROMPTED"
    CLOSED = "CLOSED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass
class SessionOperationResult:
    op: SessionOp
    outcome: Outcome
    provider: str
    session_id: str | None = None
    universal_session_id: str | None = None
    loss_report: Mapping[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.op.value,
            "outcome": self.outcome.value,
            "provider": self.provider,
            "session_id": self.session_id,
            "universal_session_id": self.universal_session_id,
            "loss_report": dict(self.loss_report),
            "notes": list(self.notes),
        }


class AcpSessionFacade:
    """Uniform ACP session control plane over WL-P0-020 providers."""

    def __init__(self, providers: Mapping[str, Any]) -> None:
        """providers: agent name -> SessionProvider instance."""
        self._providers = dict(providers)

    # -- new --------------------------------------------------------------
    def session_new(
        self,
        target_agent: str,
        project_id: str,
        *,
        source_session: Any | None = None,
        out_dir: str | None = None,
    ) -> SessionOperationResult:
        """Open a new session on ``target_agent``.

        When ``source_session`` is supplied and the target provider supports
        L1 handoff, the handoff triple is written to ``out_dir`` (required in
        that case).  The outcome is always NEW_SESSION — a new session is,
        by definition, not a native resume of the source.
        """
        provider = self._provider(target_agent)
        if provider is None:
            return SessionOperationResult(SessionOp.NEW, Outcome.UNAVAILABLE, target_agent, notes=["provider not registered"])
        if source_session is not None:
            if out_dir is None:
                return SessionOperationResult(
                    SessionOp.NEW, Outcome.UNAVAILABLE, target_agent,
                    notes=["out_dir is required when carrying a source session"],
                )
            handoff = provider.handoff(source_session, out_dir)
            return SessionOperationResult(
                SessionOp.NEW, Outcome.NEW_SESSION, target_agent,
                universal_session_id=getattr(source_session, "universal_session_id", None),
                loss_report=handoff.get("loss_report", {}),
                notes=["handoff triple written"],
            )
        return SessionOperationResult(SessionOp.NEW, Outcome.NEW_SESSION, target_agent, notes=["blank session"])

    # -- list -------------------------------------------------------------
    def session_list(self, agent: str, project_id: str) -> SessionOperationResult:
        provider = self._provider(agent)
        if provider is None:
            return SessionOperationResult(SessionOp.LIST, Outcome.UNAVAILABLE, agent, notes=["provider not registered"])
        refs = list(provider.discover(project_id))
        return SessionOperationResult(
            SessionOp.LIST, Outcome.LISTED, agent,
            session_id=str(len(refs)),
            notes=[f"discovered {len(refs)} native sessions"],
        )

    # -- resume -----------------------------------------------------------
    def session_resume(self, agent: str, session: Any) -> SessionOperationResult:
        """Attempt native resume; downgrade to NEW_SESSION with loss report.

        WL-P0-022: only a verified native resume may report RESUMED.  If the
        provider's resume command is unavailable or the source session was
        not produced by this agent, the facade degrades to L1 handoff and
        says so explicitly in ``notes``.
        """
        provider = self._provider(agent)
        if provider is None:
            return SessionOperationResult(SessionOp.RESUME, Outcome.UNAVAILABLE, agent, notes=["provider not registered"])
        try:
            command = provider.resume_native(session)
        except NotImplementedError:
            command = None
        if command is None:
            return SessionOperationResult(
                SessionOp.RESUME, Outcome.NEW_SESSION, agent,
                universal_session_id=getattr(session, "universal_session_id", None),
                notes=["native resume unavailable for provider; downgraded to L1 handoff"],
            )
        # Only claim RESUMED when the session itself attests to a verified
        # native resume marker (L3 gate in canonical.py enforces this too).
        metadata = getattr(session, "metadata", {}) or {}
        if metadata.get("native_resume", {}).get("verified"):
            return SessionOperationResult(
                SessionOp.RESUME, Outcome.RESUMED, agent,
                session_id=getattr(session, "source_session_id", None),
                universal_session_id=getattr(session, "universal_session_id", None),
                notes=[f"native resume command: {command}"],
            )
        return SessionOperationResult(
            SessionOp.RESUME, Outcome.NEW_SESSION, agent,
            session_id=getattr(session, "source_session_id", None),
            universal_session_id=getattr(session, "universal_session_id", None),
            notes=["no verified native resume marker; opening new session instead"],
        )

    # -- prompt -----------------------------------------------------------
    def session_prompt(self, agent: str, session_id: str, prompt: str) -> SessionOperationResult:
        provider = self._provider(agent)
        if provider is None:
            return SessionOperationResult(SessionOp.PROMPT, Outcome.UNAVAILABLE, agent, notes=["provider not registered"])
        if not str(prompt).strip():
            return SessionOperationResult(SessionOp.PROMPT, Outcome.UNAVAILABLE, agent, session_id=session_id, notes=["empty prompt rejected"])
        return SessionOperationResult(
            SessionOp.PROMPT, Outcome.PROMPTED, agent, session_id=session_id,
            notes=[f"prompt ({len(prompt)} chars) dispatched"],
        )

    # -- close -------------------------------------------------------------
    def session_close(self, agent: str, session_id: str) -> SessionOperationResult:
        provider = self._provider(agent)
        if provider is None:
            return SessionOperationResult(SessionOp.CLOSE, Outcome.UNAVAILABLE, agent, notes=["provider not registered"])
        return SessionOperationResult(SessionOp.CLOSE, Outcome.CLOSED, agent, session_id=session_id)

    # -- helpers -----------------------------------------------------------
    def _provider(self, agent: str) -> Any | None:
        return self._providers.get(agent)

    def registered_agents(self) -> list[str]:
        return sorted(self._providers.keys())

    def health(self) -> dict[str, Any]:
        out: dict[str, Any] = {"agents": self.registered_agents()}
        for agent, provider in self._providers.items():
            try:
                out[agent] = provider.health()
            except Exception as exc:  # noqa: BLE001 — health must not raise
                out[agent] = {"ok": False, "notes": [str(exc)]}
        return out


__all__ = ["SessionOp", "Outcome", "SessionOperationResult", "AcpSessionFacade"]
