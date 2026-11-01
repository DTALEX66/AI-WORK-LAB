"""Memory Provider Layer (WL-P0-190 / ch 23): the unified 9-method contract.

ch 23 mandates that WORK-LAB fronts every memory backend behind ONE
interface, so the governance / evaluation / knowledge planes above never
bind to a specific store:

    retain()  recall()  reflect()
    import_session()  import_repo()  import_docs()
    export()  revoke()  health()

The rule this module enforces structurally (ch 24 + the taskpack's
standing no-external-dependency rule):

* a provider that has no live backend in this environment MUST report
  itself as *not available* from :meth:`MemoryProvider.health`, and MUST
  return a typed ``UNAVAILABLE`` result from every mutating op rather
  than raising or — worst of all — fabricating a recall.  No caller may
  confuse "provider X is registered" with "provider X can serve data".
* ``recall`` results carry a *provenance* (which store, which key), so a
  false-recall can be audited later; an unavailable provider never
  invents a hit.
* ``retain`` returns the *record id* it wrote (or refused), never a
  bare success flag, so the caller can revoke exactly what it kept.

The base class is deliberately dependency-free: it holds no I/O.  The
three concrete providers (Hermes builtin, Hindsight POC, Tencent Memory
POC) live in sibling modules and inject their real store handles at
construction time, which is what makes them testable without ever
spinning up an external server.

Loading convention matches services/: no package __init__.py; siblings
load this base through the stable ``sys.modules`` name so
:class:`MemoryRecord` and the result types stay singletons.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

__all__ = [
    "MemoryKind", "MemoryRecord", "RecallHit", "OpResult", "MemoryProvider",
]


class MemoryKind(str, Enum):
    """The three tiers ch 25 keeps apart (Session / Memory / Knowledge).

    A memory *record* is always ``MEMORY`` or ``KNOWLEDGE`` (distilled,
    reusable).  Raw session material must never be retained under this
    type — that is exactly the boundary :mod:`boundary` refuses.
    """
    MEMORY = "memory"        # distilled reusable experience
    KNOWLEDGE = "knowledge"  # verified, promoted asset


@dataclass
class MemoryRecord:
    """One distilled memory / knowledge item a provider stores.

    ``kind`` is the ch 25 tier; ``content`` is the distilled payload
    (NOT a raw session log); ``origin`` records where it came from so
    provenance survives recall.
    """
    record_id: str
    kind: MemoryKind
    content: str
    origin: str = ""
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "kind": self.kind.value,
            "content": self.content,
            "origin": self.origin,
            "tags": list(self.tags),
        }


@dataclass
class RecallHit:
    """One result of a recall, with the provenance needed to audit it."""
    record: MemoryRecord
    score: float
    store: str                 # which provider returned it
    matched_on: str           # the query / tag that produced the hit

    def to_dict(self) -> dict[str, Any]:
        return {
            "record": self.record.to_dict(),
            "score": self.score,
            "store": self.store,
            "matched_on": self.matched_on,
        }


@dataclass
class OpResult:
    """Typed outcome of any provider op.

    ``ok`` is True only when the op actually did the requested effect on a
    *live* store.  ``UNAVAILABLE`` means the provider has no backend in
    this environment — callers must treat it as "cannot serve", never as
    "no such data".
    """

    __slots__ = ("op", "status", "ok", "payload", "notes", "record_id")

    def __init__(self, op: str, status: str, *, ok: bool,
                 payload: Mapping[str, Any] | None = None,
                 notes: Iterable[str] = (),
                 record_id: str | None = None) -> None:
        self.op = op
        self.status = status
        self.ok = ok
        self.payload = dict(payload or {})
        self.notes = list(notes)
        self.record_id = record_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.op, "status": self.status, "ok": self.ok,
            "payload": self.payload, "notes": self.notes,
            "record_id": self.record_id,
        }

    def __repr__(self) -> str:
        return (f"OpResult(op={self.op!r}, status={self.status!r}, ok={self.ok})")


class MemoryProvider:
    """Abstract base for every memory backend WORK-LAB fronts.

    Concrete providers set :attr:`name`, :attr:`kind` (what a *live*
    backend would be) and override :meth:`_available` to report whether a
    store is actually reachable.  All nine unified ops have a safe,
    honest default that degrades to ``UNAVAILABLE`` when no store is
    live, so a caller never gets a crash or a fabricated recall from an
    empty provider.
    """

    name: str = "base"
    kind: str = "abstract"

    def __init__(self) -> None:
        self._store: dict[str, MemoryRecord] = {}   # in-memory default store

    # -- availability ----------------------------------------------------
    def _available(self) -> bool:
        """Override: is there a live backend this provider can serve?"""
        return bool(self._store)

    def health(self) -> dict[str, Any]:
        """The one call every other op is gated on: live or not, and why."""
        return {
            "provider": self.name,
            "kind": self.kind,
            "available": self._available(),
            "record_count": len(self._store),
            "notes": [] if self._available() else ["no live backend in this environment"],
        }

    # -- the nine unified ops -------------------------------------------
    def retain(self, record: MemoryRecord) -> OpResult:
        """Store one distilled record.  Refuses raw-session material (ch 25).

        Uses a duck-type *shape* check rather than ``isinstance``: a record
        may be constructed by a separately-loaded copy of this module (the
        services/ loader registers every module under its own stable name),
        and a hard class check would wrongly reject it.  The shape check
        accepts any object carrying record_id/content/kind and refuses
        raw-session material (a Mapping or a list of events) — the ch 25
        boundary.
        """
        if not self._available():
            return OpResult("retain", "UNAVAILABLE", ok=False,
                            notes=[f"{self.name} has no live backend"])
        # ch 25: raw-session material (an events/tools Mapping, or a list of
        # events) is caught FIRST — it has no record_id/content/kind shape,
        # so a shape check alone would mislabel it BAD_RECORD.
        if isinstance(record, (Mapping, list, tuple)):
            return OpResult("retain", "RAW_SESSION", ok=False,
                            notes=["raw session material cannot be retained as memory (ch 25)"])
        if not (hasattr(record, "record_id") and hasattr(record, "content")
                and hasattr(record, "kind")):
            return OpResult("retain", "BAD_RECORD", ok=False,
                            notes=["retain requires a MemoryRecord"])
        self._store[record.record_id] = record
        return OpResult("retain", "OK", ok=True, record_id=record.record_id)

    def recall(self, query: str, *, top_k: int = 5,
               kind: MemoryKind | None = None) -> list[RecallHit]:
        """Keyword/tag recall.  An unavailable provider returns [] — never a
        fabricated hit — and every hit carries its provenance."""
        if not self._available() or not query:
            return []
        q = str(query).strip().lower()
        hits: list[RecallHit] = []
        for rec in self._store.values():
            if kind is not None and rec.kind is not kind:
                continue
            hay = " ".join([rec.content.lower(), *rec.tags, rec.origin.lower()])
            if q in hay or any(q in t.lower() for t in rec.tags):
                # provenance-first score: tag match > content match
                score = 0.9 if q in {t.lower() for t in rec.tags} else 0.5
                hits.append(RecallHit(rec, score, self.name, str(query)))
        hits.sort(key=lambda h: (-h.score, h.record.record_id))
        return hits[:max(0, top_k)]

    def reflect(self, query: str, *, top_k: int = 3) -> list[str]:
        """One distilled insight per recall hit — the 'reflect' tier.

        Returns a short list of one-line reflections grounded ONLY in what
        recall actually found; an unavailable / empty recall yields [].
        """
        hits = self.recall(query, top_k=top_k)
        return [f"[{h.record.origin or h.record.record_id}] {h.record.content[:160]}"
                for h in hits]

    def import_session(self, session_payload: Any) -> OpResult:
        """Distill a session into memory.  The base refuses raw imports:
        a concrete provider that can distill overrides this and MUST attach
        a distilled MemoryRecord, never the raw log (ch 25)."""
        return OpResult("import_session", "NOT_SUPPORTED", ok=False,
                        notes=[f"{self.name} does not implement session distillation"])

    def import_repo(self, repo_payload: Any) -> OpResult:
        return OpResult("import_repo", "NOT_SUPPORTED", ok=False,
                        notes=[f"{self.name} does not implement repo import"])

    def import_docs(self, docs_payload: Any) -> OpResult:
        return OpResult("import_docs", "NOT_SUPPORTED", ok=False,
                        notes=[f"{self.name} does not implement docs import"])

    def export(self, *, kind: MemoryKind | None = None) -> dict[str, Any]:
        """Serializable dump of what's stored (or {} when unavailable)."""
        if not self._available():
            return {"provider": self.name, "available": False, "records": []}
        records = [
            r.to_dict() for r in self._store.values()
            if kind is None or r.kind is kind
        ]
        return {"provider": self.name, "available": True, "records": records}

    def revoke(self, record_id: str) -> OpResult:
        """Remove exactly what retain() returned the id for."""
        if not self._available():
            return OpResult("revoke", "UNAVAILABLE", ok=False,
                            notes=[f"{self.name} has no live backend"])
        if record_id in self._store:
            del self._store[record_id]
            return OpResult("revoke", "OK", ok=True, record_id=record_id)
        return OpResult("revoke", "NOT_FOUND", ok=False, record_id=record_id)

    def __repr__(self) -> str:
        return (f"{type(self).__name__}(name={self.name!r}, "
                f"available={self._available()}, records={len(self._store)})")
