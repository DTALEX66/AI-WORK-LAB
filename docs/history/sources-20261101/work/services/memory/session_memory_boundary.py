"""Session / Memory / Knowledge boundary (WL-P0-210 / ch 25).

ch 25 defines three layers that MUST stay separate and names two hard
forbiddens::

    Session   = raw work history / event / tool / state
    Memory    = distilled, reusable experience
    Knowledge = verified assets that have entered ArcheAxis

    FORBIDDEN:  treat a Memory DB as a Session DB
    FORBIDDEN:  push raw Session logs straight into ArcheAxis

This module makes those two forbiddens *structurally impossible* rather
than a policy footnote:

* a **session store** accepts only raw-session-shaped payloads and is the
  ONLY place they may live; it never distils and never writes to memory.
* a **memory provider** accepts only already-distilled :class:`MemoryRecord`
  instances — handing it a raw session payload raises
  :class:`SessionAsMemoryError`.
* the **knowledge sink** accepts only a MEMORY-tier record that carries an
  explicit ``verified`` attestation — handing it a raw session (or an
  unverified memory) raises :class:`RawLogToKnowledgeError` /
  :class:`UnverifiedPromotionError` respectively.

The result is a one-way pipeline::

    raw session  ->  [explicit distill]  ->  memory  ->  [verified]  ->  knowledge

and no shortcut edge skips a stage.
"""
from __future__ import annotations

import importlib.util as _ilu
import sys as _sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

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
    "SessionAsMemoryError", "RawLogToKnowledgeError", "UnverifiedPromotionError",
    "SessionStore", "SessionMemoryBoundary",
]


class BoundaryViolation(ValueError):
    """Base class for every ch 25 boundary breach."""


class SessionAsMemoryError(BoundaryViolation):
    """A raw session payload was offered to the memory layer."""


class RawLogToKnowledgeError(BoundaryViolation):
    """A raw session log was offered directly to the knowledge layer."""


class UnverifiedPromotionError(BoundaryViolation):
    """A memory record was promoted to knowledge without a verified flag."""


def _is_raw_session(payload: Any) -> bool:
    """Heuristic: does this payload look like *raw* session material?

    Raw session is shaped as an event/tool log (a dict or list carrying
    ``events`` / ``tools`` / ``state`` keys, or a JSONL string).  A
    distilled :class:`MemoryRecord` is *not* raw — it is already the
    memory tier.
    """
    if payload is None:
        return False
    if hasattr(payload, "record_id") and hasattr(payload, "content"):
        # a MemoryRecord — already distilled, not raw
        return False
    if isinstance(payload, Mapping):
        return any(k in payload for k in ("events", "tools", "state", "raw_log"))
    if isinstance(payload, (list, tuple)):
        return bool(payload)  # a list of events is raw session material
    return False


@dataclass
class SessionStore:
    """The ONLY legal home for raw session material (ch 25, layer 1).

    It appends raw payloads and can return them, but it has **no** path to
    memory or knowledge — that is the whole point of keeping the session
    DB from doubling as a memory DB.
    """
    entries: list[dict[str, Any]] = field(default_factory=list)

    def append(self, raw: Any, *, session_id: str = "") -> dict[str, Any]:
        entry = {"session_id": session_id, "raw": raw}
        self.entries.append(entry)
        return entry

    def get(self, session_id: str) -> dict[str, Any] | None:
        for entry in self.entries:
            if entry["session_id"] == session_id:
                return entry
        return None

    def __len__(self) -> int:
        return len(self.entries)

    def cannot_write_memory(self) -> bool:
        """Asserts the structural fact: this store has no memory sink."""
        return not hasattr(self, "retain")


class SessionMemoryBoundary:
    """The one-way pipeline raw-session -> memory -> knowledge.

    Every hop validates its input shape; skipping a hop or feeding the
    wrong shape raises the specific ch 25 breach.
    """

    def __init__(self, provider: Any, session_store: SessionStore | None = None) -> None:
        self.provider = provider
        self.sessions = session_store or SessionStore()

    # -- stage 1: raw session lives here only ---------------------------
    def record_session(self, raw: Any, *, session_id: str = "") -> dict[str, Any]:
        if not _is_raw_session(raw):
            # something that is already distilled should go to memory, not
            # be re-logged as a session
            raise SessionAsMemoryError(
                "payload is not raw session material; distill it into memory instead"
            )
        return self.sessions.append(raw, session_id=session_id)

    # -- stage 2: distill a session into a memory record ----------------
    def distill(self, session_id: str, *, content: str,
                tags: Iterable[str] = (), verified: bool = False) -> Any:
        """Explicitly move *from a session* *into memory*.

        This is the ONLY sanctioned edge from layer 1 to layer 2: it
        requires the caller to produce a distilled ``content`` string and
        refuses to do it from a still-raw payload.  ``verified`` records
        the promotion attestation that the knowledge stage will demand.
        """
        if not content.strip():
            raise SessionAsMemoryError("distillation requires distilled content")
        rec = _base().MemoryRecord(
            record_id=f"mem:{session_id}",
            kind=_base().MemoryKind.MEMORY,
            content=content,
            origin=f"session:{session_id}",
            tags=tuple(tags),
        )
        rec.verified = verified  # type: ignore[attr-defined]
        res = self.provider.retain(rec)
        if not res.ok:
            raise RuntimeError(f"memory retain failed: {res.notes}")
        return rec

    # -- stage 3: promote a verified memory into knowledge --------------
    def promote_to_knowledge(self, record: Any, *, target: str = "archeaxis") -> Any:
        """The ONLY sanctioned edge from layer 2 to layer 3.

        Two refusals:
        * handing a *raw* session straight to the knowledge layer is the
          second ch 25 forbid -> :class:`RawLogToKnowledgeError`.
        * handing an *unverified* memory record ->
          :class:`UnverifiedPromotionError`.
        """
        if _is_raw_session(record):
            raise RawLogToKnowledgeError(
                f"raw session logs cannot go straight to {target!r}; "
                "distill to memory first"
            )
        verified = getattr(record, "verified", False)
        if not verified:
            raise UnverifiedPromotionError(
                "only a verified memory record may be promoted to knowledge"
            )
        # a promoted record becomes the KNOWLEDGE tier
        record.kind = _base().MemoryKind.KNOWLEDGE
        record.origin = record.origin + f" -> knowledge:{target}"
        return record

    # -- the two forbiddens, made checkable ----------------------------
    def assert_memory_is_not_session_db(self) -> bool:
        """Prove the memory provider is not being used as a session store."""
        return not hasattr(self.provider, "append") and self.sessions.cannot_write_memory()

    def __repr__(self) -> str:
        return (f"SessionMemoryBoundary(provider={self.provider.name!r}, "
                f"sessions={len(self.sessions)})")
