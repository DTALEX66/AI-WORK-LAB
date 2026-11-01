"""OpenTelemetry correlation for canonical sessions (WL-P0-080).

The taskpack goal (ch 12 / ch44 item 15) is that every session — no matter
which agent produced it — collapses onto ONE OpenTelemetry conversation id:

    universal_session_id  ==>  gen_ai.conversation.id

so that traces, cost, model calls, tool calls, latency, errors and
benchmarks all key off the same id across Hermes / Codex / DSH / OpenHands
/ Pi.  This module provides that bridge plus the reverse index that lets a
span carrying only an agent's *native* session id resolve back to the
universal id.

It is deliberately dependency-free (no opentelemetry SDK import): it emits
plain attribute dicts and a W3C traceparent that any collector can ingest.
The trace-id is derived *deterministically* from the universal_session_id,
so the same session always lands on the same trace across every agent —
which is exactly the correlation the Done-When requires.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable

import importlib.util as _ilu

# --- OpenTelemetry GenAI + standard semantic attribute names -------------
CONVERSATION_ID_ATTR = "gen_ai.conversation.id"
AGENT_SYSTEM_ATTR = "gen_ai.system"
MODEL_ATTR = "gen_ai.request.model"
INPUT_TOKENS_ATTR = "gen_ai.usage.input_tokens"
OUTPUT_TOKENS_ATTR = "gen_ai.usage.output_tokens"
PROJECT_ATTR = "work_lab.project"
UNIVERSAL_ATTR = "work_lab.universal_session_id"
NATIVE_SOURCE_ATTR = "work_lab.native_source_session_id"
PORTABILITY_ATTR = "work_lab.portability_level"

__all__ = [
    "CONVERSATION_ID_ATTR", "AGENT_SYSTEM_ATTR", "MODEL_ATTR",
    "INPUT_TOKENS_ATTR", "OUTPUT_TOKENS_ATTR", "PROJECT_ATTR",
    "UNIVERSAL_ATTR", "NATIVE_SOURCE_ATTR", "PORTABILITY_ATTR",
    "ConversationCorrelator", "trace_id_for", "traceparent_for",
    "span_id_for", "otel_attributes", "register_native", "resolve_conversation_id",
]


def _load_canonical():
    import sys as _sys
    here = Path(__file__).resolve().parent
    name = "services_session_federation_canonical"
    existing = _sys.modules.get(name)
    if existing is not None and getattr(existing, "CanonicalSession", None) is not None:
        return existing
    spec = _ilu.spec_from_file_location(name, here / "canonical.py")
    module = _ilu.module_from_spec(spec)
    _sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# -- deterministic W3C trace context ------------------------------------
def trace_id_for(universal_session_id: str) -> str:
    """128-bit trace-id derived from the universal session id (W3C hex, 32 chars).

    Determinism is the point: the same session id always maps to the same
    trace, independent of which agent is running.
    """
    digest = hashlib.sha256(universal_session_id.encode("utf-8")).hexdigest()
    return digest[:32]


def span_id_for(*parts: str) -> str:
    """64-bit span-id (W3C hex, 16 chars) derived deterministically."""
    key = "|".join(parts)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return digest[:16]


def traceparent_for(universal_session_id: str, span_part: str = "root") -> str:
    """W3C ``traceparent`` header value for a session's root span.

    Format: ``version-traceid-spanid-flags`` (all lowercase hex).
    """
    trace = trace_id_for(universal_session_id)
    span = span_id_for(universal_session_id, span_part)
    return f"00-{trace}-{span}-00"


# -- attribute mapping ----------------------------------------------------
def otel_attributes(session: "Any") -> dict[str, Any]:
    """Project a ``CanonicalSession`` onto OTel GenAI semantic attributes.

    ``session`` may be a ``CanonicalSession`` or a plain ``to_dict()`` mapping;
    both are accepted so callers with a serialized record can also correlate.
    """
    def _get(key: str, default: Any = None) -> Any:
        if hasattr(session, key):
            return getattr(session, key, default)
        if isinstance(session, dict):
            return session.get(key, default)
        return default

    metadata = _get("metadata") or {}
    model = metadata.get("model")
    input_tokens = _first_present(metadata, "usage_input_tokens", "uncachedInputTokens")
    output_tokens = metadata.get("usage_output_tokens") or metadata.get("outputTokens")

    attrs: dict[str, Any] = {
        CONVERSATION_ID_ATTR: _get("universal_session_id"),
        AGENT_SYSTEM_ATTR: _get("source_agent"),
        UNIVERSAL_ATTR: _get("universal_session_id"),
        NATIVE_SOURCE_ATTR: _get("source_session_id"),
        PROJECT_ATTR: _get("project_id"),
        PORTABILITY_ATTR: (
            _get("portability_level").value
            if hasattr(_get("portability_level"), "value")
            else _get("portability_level")
        ),
    }
    if model:
        attrs[MODEL_ATTR] = model
    if input_tokens is not None:
        attrs[INPUT_TOKENS_ATTR] = input_tokens
    if output_tokens is not None:
        attrs[OUTPUT_TOKENS_ATTR] = output_tokens
    return attrs


def _first_present(metadata: Any, *keys: str) -> Any:
    if isinstance(metadata, dict):
        for key in keys:
            if metadata.get(key) is not None:
                return metadata[key]
    return None


class ConversationCorrelator:
    """Bidirectional bridge between OTel conversation ids and native session ids.

    * forward:  ``otel_attributes(session)`` -> ``gen_ai.conversation.id``
    * reverse:  any native ``(agent, source_session_id)`` -> universal id,
      so a span that only knows its agent's own id can still join the trace.

    The native->universal index is built from the sessions the caller feeds
    in; it is in-memory and deterministic (deterministic trace-id means even
    an unregistered native id can be *predicted* when it is a bare
    ``<agent>:<source_id>`` canonical id).
    """

    def __init__(self) -> None:
        self._native_to_universal: dict[tuple[str, str], str] = {}

    # -- registration -----------------------------------------------------
    def register(self, session: "Any") -> dict[str, Any]:
        """Index one session's native id and return its OTel attributes."""
        attrs = otel_attributes(session)
        agent = attrs.get(AGENT_SYSTEM_ATTR)
        source = attrs.get(NATIVE_SOURCE_ATTR)
        universal = attrs.get(CONVERSATION_ID_ATTR)
        if agent and source and universal:
            self._native_to_universal[(str(agent), str(source))] = str(universal)
        return attrs

    def resolve(self, agent: str, source_session_id: str) -> str | None:
        """Reverse lookup: (agent, native id) -> universal conversation id.

        Falls back to the canonical ``<agent>:<source>`` id when the pair was
        never explicitly registered, keeping correlation total rather than
        lossy.
        """
        hit = self._native_to_universal.get((str(agent), str(source_session_id)))
        if hit:
            return hit
        return f"{agent}:{source_session_id}"

    def known_conversations(self) -> list[str]:
        return sorted(set(self._native_to_universal.values()))


# -- module-level convenience facade --------------------------------------
_DEFAULT_CORRELATOR = ConversationCorrelator()


def register_native(session: "Any") -> dict[str, Any]:
    return _DEFAULT_CORRELATOR.register(session)


def resolve_conversation_id(agent: str, source_session_id: str) -> str | None:
    return _DEFAULT_CORRELATOR.resolve(agent, source_session_id)
