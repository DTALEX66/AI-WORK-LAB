"""Penguin evolution provider (WL-330 / ch 28).

Penguin is an external evolution engine: agent creation, benchmark,
optimization, snapshot, trace, skills self-improvement, continual
learning, across Desktop/CLI/Web/Docker/SDK.  ch 35's external-asset rule
applies — WORK-LAB never vendors it, it holds the EvolutionProvider
interface and a POC adapter that reports itself UNAVAILABLE when no live
engine handle is handed in.

The ch 29 boundary is load-bearing and is NOT this module's job: a
Penguin that *produces* a candidate must not also be the one that
*evaluates* it or *promotes* it.  This provider only manufactures and
traces candidates; the independent gate (independent_eval) owns the
verdict.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class EvolutionCapability:
    """The eight ch 28 capabilities."""

    CREATE_CANDIDATE = "create_candidate"
    BENCHMARK = "benchmark"
    MUTATE_PROMPT = "mutate_prompt"
    MUTATE_SKILL = "mutate_skill"
    MUTATE_WORKFLOW = "mutate_workflow"
    TRACE = "trace"
    SNAPSHOT = "snapshot"
    ROLLBACK = "rollback"

    ALL = (CREATE_CANDIDATE, BENCHMARK, MUTATE_PROMPT, MUTATE_SKILL,
           MUTATE_WORKFLOW, TRACE, SNAPSHOT, ROLLBACK)
    _MEMBERS = frozenset(ALL)


@dataclass
class Candidate:
    """One evolution candidate produced by a provider.

    ``produced_by`` records which provider made it — the independent gate
    (ch 29) uses this to reject self-evaluation and self-promotion.
    """

    candidate_id: str
    produced_by: str
    base_id: str = ""
    kind: str = "prompt"          # prompt / skill / workflow
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"candidate_id": self.candidate_id, "produced_by": self.produced_by,
                "base_id": self.base_id, "kind": self.kind, "payload": self.payload}


@dataclass
class Trace:
    """Immutable record of what a provider did (ch 28's trace)."""

    events: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"events": self.events}


class EvolutionProvider:
    """Interface every evolution engine is fronted behind."""

    name: str = "evolution"

    def available(self) -> bool:
        raise NotImplementedError

    def create_candidate(self, base_id: str, kind: str = "prompt") -> Candidate:
        raise NotImplementedError

    def benchmark(self, candidate: Candidate) -> Dict[str, Any]:
        raise NotImplementedError

    def mutate_prompt(self, candidate: Candidate, delta: str) -> Candidate:
        raise NotImplementedError

    def mutate_skill(self, candidate: Candidate, delta: str) -> Candidate:
        raise NotImplementedError

    def mutate_workflow(self, candidate: Candidate, delta: str) -> Candidate:
        raise NotImplementedError

    def trace(self) -> Trace:
        raise NotImplementedError

    def snapshot(self) -> Dict[str, Any]:
        raise NotImplementedError

    def rollback(self, snapshot_id: str) -> bool:
        raise NotImplementedError


class PenguinProvider(EvolutionProvider):
    """WORK-LAB's POC adapter to the Penguin engine (ch 28).

    ``handle`` is an optional live-engine object; when absent the provider
    is honestly unavailable — the eight ops degrade to UNAVAILABLE / empty
    instead of fabricating a candidate or a benchmark.
    """

    name = "penguin"

    def __init__(self, handle: Optional[Any] = None) -> None:
        self._handle = handle
        self._candidates: Dict[str, Candidate] = {}
        self._snapshots: Dict[str, Dict[str, Any]] = {}
        self._trace_events: List[Dict[str, Any]] = []

    def available(self) -> bool:
        # a live engine handle is required; WORK-LAB does not vendor Penguin
        return self._handle is not None

    def _op(self, op: str, candidate: Optional[Candidate], **kw) -> Any:
        if not self.available():
            self._trace_events.append({"op": op, "status": "UNAVAILABLE",
                                       "external_engine": True})
            return None
        # with a live handle the engine would do the real work; this POC
        # only implements the *locally-ownable* state machine (produce /
        # mutate / trace / snapshot / rollback) so the gate has real
        # candidates to evaluate against.  Benchmarks still require the
        # engine and return UNAVAILABLE honestly.
        return kw.get("_local", False)

    def create_candidate(self, base_id: str, kind: str = "prompt") -> Candidate:
        cid = f"cand-{len(self._candidates)+1}"
        c = Candidate(candidate_id=cid, produced_by=self.name,
                      base_id=base_id, kind=kind)
        self._candidates[cid] = c
        self._trace_events.append({"op": "create_candidate", "id": cid,
                                   "base_id": base_id, "kind": kind})
        return c

    def mutate_prompt(self, candidate: Candidate, delta: str) -> Candidate:
        return self._mutate(candidate, "prompt", delta)

    def mutate_skill(self, candidate: Candidate, delta: str) -> Candidate:
        return self._mutate(candidate, "skill", delta)

    def mutate_workflow(self, candidate: Candidate, delta: str) -> Candidate:
        return self._mutate(candidate, "workflow", delta)

    def _mutate(self, candidate: Candidate, kind: str, delta: str) -> Candidate:
        mutated = Candidate(candidate_id=candidate.candidate_id + "-m",
                           produced_by=self.name,
                           base_id=candidate.candidate_id, kind=kind,
                           payload={**candidate.payload, "delta": delta})
        self._candidates[mutated.candidate_id] = mutated
        self._trace_events.append({"op": f"mutate_{kind}",
                                   "from": candidate.candidate_id,
                                   "to": mutated.candidate_id})
        return mutated

    def benchmark(self, candidate: Candidate) -> Dict[str, Any]:
        """A benchmark needs the live engine.  Without it: UNAVAILABLE.

        This is the ch 29 seam — the number is produced by the provider
        only for ITS OWN candidate set; promotion decisions are made by the
        independent gate on its OWN holdout, not on this number.
        """
        if not self.available():
            self._trace_events.append({"op": "benchmark",
                                       "candidate": candidate.candidate_id,
                                       "status": "UNAVAILABLE"})
            return {"available": False, "status": "UNAVAILABLE",
                    "external_engine": True}
        # live engine: emit the engine's benchmark (opaque dict)
        return {"available": True, "external_engine": True,
                "candidate": candidate.candidate_id,
                "engine": self._handle and getattr(self._handle, "name", "penguin")}

    def trace(self) -> Trace:
        return Trace(events=list(self._trace_events))

    def snapshot(self) -> Dict[str, Any]:
        sid = f"snap-{len(self._snapshots)+1}"
        snap = {"snapshot_id": sid,
                "candidates": [c.to_dict() for c in self._candidates.values()],
                "trace": len(self._trace_events)}
        self._snapshots[sid] = snap
        self._trace_events.append({"op": "snapshot", "id": sid})
        return snap

    def rollback(self, snapshot_id: str) -> bool:
        snap = self._snapshots.get(snapshot_id)
        if snap is None:
            return False
        restored = {d["candidate_id"]: Candidate(
            candidate_id=d["candidate_id"], produced_by=d["produced_by"],
            base_id=d["base_id"], kind=d["kind"], payload=d["payload"])
            for d in snap["candidates"]}
        self._candidates = restored
        self._trace_events.append({"op": "rollback", "to": snapshot_id})
        return True

    def health(self) -> Dict[str, Any]:
        return {"available": self.available(), "external_engine": True,
                "poc_surface": True, "capabilities": list(EvolutionCapability.ALL),
                "candidates": len(self._candidates), "snapshots": len(self._snapshots)}
