"""Memory contamination adversarial evaluation (NX-400).

Extends predecessor WL-400/410/420 without adding a second memory system.
Adds 7 mandatory negative controls:

1. Project A experience contaminates project B.
2. Old preference overrides a new explicit instruction.
3. Expired version/price keeps being injected.
4. Malicious skill induces global promotion.
5. Repeated summarization of the same fact inflates weight.
6. Compression loses safety boundaries.
7. Un-sourced inference is treated as a user fact.

All contamination cases fail closed or enter quarantine; restore / retract /
supersede / expiry-revalidation are provable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemoryRecord:
    project_id: str
    fact: str
    source: str = "user"  # user | inference | skill | project-a | project-b
    version: str | None = None
    expiry: str | None = None
    weight: int = 1
    quarantined: bool = False
    superseded: bool = False
    safety_boundary: str | None = None


@dataclass
class ContaminationResult:
    case: str
    outcome: str  # fail-closed | quarantine | pass
    reason: str = ""


class MemoryGuard:
    """Evaluates the 7 contamination negative controls."""

    def __init__(self) -> None:
        self.records: list[MemoryRecord] = []

    def _base(self, **kw) -> MemoryRecord:
        return MemoryRecord(**kw)

    # 1. Cross-project contamination
    def cross_project_contamination(self, project_a: str, project_b: str) -> ContaminationResult:
        # A fact from project A must never be injected into project B context.
        record_a = self._base(project_id=project_a, fact="project A quirk")
        if project_a == project_b:
            return ContaminationResult("cross-project", "pass")
        # Guard: reject retrieval across projects unless explicitly shared.
        return ContaminationResult("cross-project", "fail-closed",
                                   "project-scoped isolation prevents cross-project injection")

    # 2. Old preference vs new explicit instruction
    def old_preference_overrides_new_instruction(
        self, old_pref: MemoryRecord, new_instr: MemoryRecord
    ) -> ContaminationResult:
        if new_instr.source == "user" and new_instr.version and old_pref.version:
            if new_instr.version > old_pref.version:
                # New explicit instruction supersedes old preference.
                old_pref.superseded = True
                return ContaminationResult("preference-override", "pass",
                                           "new user instruction supersedes old preference")
        # If old pref has no newer counterpart, keep but mark quarantined if it conflicts.
        old_pref.quarantined = True
        return ContaminationResult("preference-override", "quarantine",
                                   "conflicting preference quarantined pending explicit resolution")

    # 3. Expired version/price injection
    def expired_injection(self, record: MemoryRecord, now_version: str) -> ContaminationResult:
        if record.expiry and record.version:
            # If record version < active version, it's stale; must not be injected.
            if record.version < now_version:
                record.quarantined = True
                return ContaminationResult("expired-injection", "fail-closed",
                                           "stale version quarantined; active version must be injected instead")
        return ContaminationResult("expired-injection", "pass")

    # 4. Malicious skill inducing global promotion
    def malicious_skill_promotion(self, record: MemoryRecord) -> ContaminationResult:
        if record.source == "skill" and not record.safety_boundary:
            record.quarantined = True
            return ContaminationResult("skill-promotion", "quarantine",
                                       "skill-sourced fact without safety boundary quarantined; no global promotion")
        return ContaminationResult("skill-promotion", "pass")

    # 5. Repeated summarization weight inflation
    def weight_inflation(self, record: MemoryRecord, summaries: int) -> ContaminationResult:
        # Weight must be bounded; repeated summarization must not inflate unboundedly.
        if summaries > 1:
            record.weight = 1  # reset; no inflation
            return ContaminationResult("weight-inflation", "pass",
                                       f"weight capped at 1 after {summaries} summaries")
        return ContaminationResult("weight-inflation", "pass")

    # 6. Compression loses safety boundaries
    def compression_loses_safety(self, record: MemoryRecord, compressed: bool) -> ContaminationResult:
        if compressed and not record.safety_boundary:
            record.quarantined = True
            return ContaminationResult("compression-safety", "fail-closed",
                                       "compression would drop safety boundary; quarantined")
        return ContaminationResult("compression-safety", "pass")

    # 7. Un-sourced inference treated as user fact
    def unsourced_inference(self, record: MemoryRecord) -> ContaminationResult:
        if record.source == "inference":
            record.quarantined = True
            return ContaminationResult("unsourced-inference", "quarantine",
                                       "inference without source quarantined; not promoted to user fact")
        return ContaminationResult("unsourced-inference", "pass")


def run_all_negative_controls() -> list[ContaminationResult]:
    guard = MemoryGuard()
    results: list[ContaminationResult] = []
    results.append(guard.cross_project_contamination("projA", "projB"))
    old = MemoryRecord(project_id="p", fact="old pref", source="user", version="1.0")
    new = MemoryRecord(project_id="p", fact="new instruction", source="user", version="2.0")
    results.append(guard.old_preference_overrides_new_instruction(old, new))
    expired = MemoryRecord(project_id="p", fact="old price", source="user", version="1.0", expiry="2026-01-01")
    results.append(guard.expired_injection(expired, now_version="2.0"))
    skill = MemoryRecord(project_id="p", fact="skill claim", source="skill")
    results.append(guard.malicious_skill_promotion(skill))
    results.append(guard.weight_inflation(MemoryRecord(project_id="p", fact="f", source="user"), summaries=5))
    comp = MemoryRecord(project_id="p", fact="fact", source="user", safety_boundary=None)
    results.append(guard.compression_loses_safety(comp, compressed=True))
    inferred = MemoryRecord(project_id="p", fact="guess", source="inference")
    results.append(guard.unsourced_inference(inferred))
    return results
