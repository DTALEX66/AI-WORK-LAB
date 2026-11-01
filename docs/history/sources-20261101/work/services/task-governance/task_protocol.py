"""Task Protocol V2 (WL-170): three delivery modes + risk-based upgrades.

The taskpack (ch 15) defines how a task is *shaped* before work starts:

* **Native**    — single session, small task.  No portable artifacts.
* **Portable**  — crosses session / agent / model / machine.  Emits the
                  portable triple ``contract.json`` + ``events.jsonl`` +
                  ``capsule.md``.
* **Audited**   — high-risk tasks (release / migration / delete / security /
                  license / evolution).  The portable triple PLUS
                  ``independent evaluator`` + ``typed receipt`` +
                  ``owner epoch`` + ``rollback`` + ``human approval``.

This module is *pure policy*: it classifies a task, enumerates exactly what
the chosen mode demands, and validates that a claimed completion actually
carries those artifacts.  It is the shared contract that Completion
Authority (ch 16) and the Permission Gate (ch 18) both check against —
nobody downstream re-invents the list.

Loading convention (services/ has no package __init__.py): sibling modules
reference each other through the stable ``sys.modules`` name so enums and
types stay singletons.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Iterable, Mapping

__all__ = [
    "TaskMode", "HIGH_RISK_TOPICS", "PORTABLE_ARTIFACTS", "AUDITED_EXTRAS",
    "classify", "audit_risk", "required_artifacts", "required_extras",
    "validate_completion",
]


class TaskMode(str, Enum):
    NATIVE = "native"
    PORTABLE = "portable"
    AUDITED = "audited"


# Ch 15: the six topics that force the Audited mode.
HIGH_RISK_TOPICS = frozenset(
    ["release", "migration", "delete", "security", "license", "evolution"]
)

# Ch 15 (Portable): the three artifacts a cross-boundary task must emit.
PORTABLE_ARTIFACTS = ("contract.json", "events.jsonl", "capsule.md")

# Ch 15 (Audited): the five extras on top of the portable triple.
AUDITED_EXTRAS = (
    "independent_evaluator",
    "typed_receipt",
    "owner_epoch",
    "rollback",
    "human_approval",
)


def audit_risk(topic_hints: Iterable[str]) -> list[str]:
    """Which high-risk topics do the hints hit?  (Empty = no forced audit.)"""
    hints = {str(h).strip().lower() for h in topic_hints}
    return sorted(HIGH_RISK_TOPICS & hints)


def classify(
    topic_hints: Iterable[str] = (),
    *,
    cross_session: bool = False,
    cross_agent: bool = False,
    cross_model: bool = False,
    cross_machine: bool = False,
) -> TaskMode:
    """Pick the minimum mode a task needs.  Risk always dominates.

    Any cross-boundary flag lifts a task to Portable.  A hit on a high-risk
    topic lifts it to Audited (which implies Portable's artifacts).
    """
    mode = TaskMode.NATIVE
    if cross_session or cross_agent or cross_model or cross_machine:
        mode = TaskMode.PORTABLE
    if audit_risk(topic_hints):
        mode = TaskMode.AUDITED
    return mode


def required_artifacts(mode: TaskMode) -> tuple[str, ...]:
    """File artifacts the mode demands (Audited inherits Portable's)."""
    if mode in (TaskMode.PORTABLE, TaskMode.AUDITED):
        return PORTABLE_ARTIFACTS
    return ()


def required_extras(mode: TaskMode) -> tuple[str, ...]:
    """Non-file audit extras (only Audited carries these)."""
    return AUDITED_EXTRAS if mode is TaskMode.AUDITED else ()


def validate_completion(
    mode: TaskMode,
    *,
    artifacts_present: Iterable[str] = (),
    extras_present: Iterable[str] = (),
) -> dict[str, Any]:
    """Check a claimed completion against the mode's contract.

    Returns a dict: ``{"ok": bool, "missing_artifacts": [...],
    "missing_extras": [...], "expected_mode": mode}``.  Callers (Completion
    Authority / the CI gate) treat any non-empty missing list as a refusal.
    """
    have = {str(a).strip() for a in artifacts_present}
    have_extras = {str(e).strip() for e in extras_present}
    missing_artifacts = [a for a in required_artifacts(mode) if a not in have]
    missing_extras = [e for e in required_extras(mode) if e not in have_extras]
    ok = not missing_artifacts and not missing_extras
    return {
        "ok": ok,
        "expected_mode": mode,
        "missing_artifacts": missing_artifacts,
        "missing_extras": missing_extras,
    }
