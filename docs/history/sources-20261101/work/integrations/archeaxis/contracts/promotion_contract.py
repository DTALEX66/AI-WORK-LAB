"""ArcheAxis thin contracts — WORK-LAB V2 three-project boundary seam.

These are the MINIMAL interfaces WORK-LAB keeps across the boundary.
They carry no knowledge truth, no memory store, no promotion decision —
only the "candidate + guard verdict" shape that crosses into
DTALEX66/ArcheAxis-Knowledge-OS, and the thin query surface that asks
ArcheAxis instead of storing locally.

Authority: .project/governance/three-project-boundary.json
Verifier: scripts/ci/verify_three_project_boundary.py

P2/P3 rule: no new caller may import services/memory or services/knowledge
as a local backend. New cross-project access goes through THIS module.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Knowledge side (services/knowledge -> ArcheAxis)
# ---------------------------------------------------------------------------

@dataclass
class KnowledgeCandidate:
    """The ONLY thing WORK-LAB may emit toward ArcheAxis knowledge truth.

    WORK-LAB never emits 'Knowledge Truth' — it emits a candidate plus the
    guard's verdict. ArcheAxis makes the acceptance/classification/status
    decision. Keeping this dataclass here (not in services/knowledge) is
    what stops a second knowledge-truth owner from appearing in WORK-LAB.
    """
    source_id: str
    category: str                 # ch 37 whitelist label (candidate-level)
    evidence_level: str
    guard_verdict: str            # "allow" | "reject"
    guard_reasons: List[str] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)
    payload_digest: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, ensure_ascii=False)


class GuardVerdict:
    ALLOW = "allow"
    REJECT = "reject"


# ---------------------------------------------------------------------------
# Memory side (services/memory -> ArcheAxis)
# ---------------------------------------------------------------------------

@dataclass
class MemoryQuery:
    """Thin query surface — WORK-LAB asks ArcheAxis, it does NOT store."""
    query: str
    session_id: Optional[str] = None
    scope: str = "session"

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, ensure_ascii=False)


@dataclass
class ArcheAxisHandoffEnvelope:
    """TASK M minimum 15-field candidate envelope.

    WORK-LAB EMITS this (candidate + provenance + guard verdict + receipt digest).
    It does NOT write Knowledge Truth, decide the final category, or manage the
    ArcheAxis DB — those stay in DTALEX66/ArcheAxis-Knowledge-OS. Until the
    ArcheAxis API exists, this envelope is the shared contract + adapter seam.
    """
    project_id: str
    task_id: Optional[str] = None
    execution_id: Optional[str] = None
    artifact_id: Optional[str] = None
    source_sha: Optional[str] = None
    source_project: Optional[str] = None
    artifact_type: str = "knowledge_candidate"
    evidence_level: str = "UNVERIFIED"
    provenance: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    content_digest: Optional[str] = None
    classification_hint: Optional[str] = None
    privacy_level: str = "restricted"
    export_permission: str = "denied"          # WORK-LAB default: fail-closed
    receipt_digest: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, ensure_ascii=False)

    def is_valid_envelope(self) -> bool:
        # a candidate must always carry provenance + a well-formed digest
        return bool(self.provenance) and bool(self.content_digest)


__all__ = [
    "KnowledgeCandidate", "GuardVerdict", "MemoryQuery", "ArcheAxisHandoffEnvelope",
]
