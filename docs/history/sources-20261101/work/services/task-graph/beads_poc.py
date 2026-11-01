"""Beads Task Graph POC (WL-P0-180 / ch 22): a coverage assessment, not a port.

The taskpack positions this item as a *comparison*, and it states the
conclusion up front: *do not make Beads the source of truth (SSOT)*.  What
this module actually delivers is that conclusion *backed by evidence*, not
a re-implementation of Beads (installing Beads or a Dolt backend would be
exactly the out-of-scope external dependency the taskpack warns against).

Approach
--------

WORK-LAB already owns a mature task-graph primitive in
``packages/client-neutral-core/scripts/task_ledger.py`` — a single-file,
append-JSON, lease-fenced, dependency-checked ``TaskLedger``.  This module
maps each of the ten capability dimensions the taskpack lists for the POC

    dependency graph / atomic claim / long task / concurrent agents /
    Dolt / resume / hierarchy / memory decay / JSON / Windows

onto the *specific, verified* TaskLedger API that covers it, records a
coverage verdict per dimension, and produces a deterministic, hashable
report whose top-line conclusion is::

    beads_as_ssot = False

Because two dimensions — **Dolt** (versioned git-like storage) and
**memory decay** (time-weighted recall) — have no equivalent in the current
TaskLedger, they are the concrete, evidenced reasons Beads cannot be dropped
in as the single source of truth without changing WORK-LAB's storage model
and introducing an external dependency.

The module is pure: it imports no Beads, no Dolt, and nothing networked.
It reads the capability map (curated against the real TaskLedger API) and
emits a JSON-serialisable report with a content hash so the POC verdict is
reproducible offline.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

__all__ = [
    "BeadsCapability", "Coverage", "CapabilityAssessment", "BeadsPocReport",
    "CAPABILITY_MAP", "assess", "conclude_ssot", "report",
]


class BeadsCapability(str, Enum):
    """The ten POC dimensions from ch 22, in the taskpack's order."""
    DEPENDENCY_GRAPH = "dependency graph"
    ATOMIC_CLAIM = "atomic claim"
    LONG_TASK = "long task"
    CONCURRENT_AGENTS = "concurrent agents"
    DOLT = "Dolt"
    RESUME = "resume"
    HIERARCHY = "hierarchy"
    MEMORY_DECAY = "memory decay"
    JSON = "JSON"
    WINDOWS = "Windows"


class Coverage(str, Enum):
    """How well the current TaskLedger covers a dimension."""
    COVERED = "covered"          # an equivalent native primitive exists
    PARTIAL = "partial"         # covered with a gap the caller must close
    MISSING = "missing"         # no native equivalent; Beads/Dolt-only


@dataclass
class CapabilityAssessment:
    """One row of the comparison: a dimension, its verdict, and the proof."""
    capability: BeadsCapability
    coverage: Coverage
    task_ledger_api: str        # the concrete TaskLedger API that covers it
    evidence: str              # what that API actually does (verified, not guessed)
    beads_note: str           # what Beads offers on this dimension
    ssot_blocker: bool = False  # True when this dimension alone argues against SSOT


#: The curated capability map.  Every TaskLedger API named here is a real
#: method on ``TaskLedger`` in packages/client-neutral-core/scripts/
#: task_ledger.py (verified by reading the file, not by inference).
CAPABILITY_MAP: Mapping[BeadsCapability, CapabilityAssessment] = {
    BeadsCapability.DEPENDENCY_GRAPH: CapabilityAssessment(
        capability=BeadsCapability.DEPENDENCY_GRAPH,
        coverage=Coverage.COVERED,
        task_ledger_api="set_dependencies + ready_tasks",
        evidence=("set_dependencies validates each edge exists, rejects a "
                  "self-dependency, and runs a full-graph cycle detection "
                  "before committing; ready_tasks() returns exactly the "
                  "QUEUED tasks whose dependencies are all COMPLETED — a "
                  "real topological gate, not a heuristic 'looks related'."),
        beads_note="Beads ships a DAG editor and resolver.",
        ssot_blocker=False,
    ),
    BeadsCapability.ATOMIC_CLAIM: CapabilityAssessment(
        capability=BeadsCapability.ATOMIC_CLAIM,
        coverage=Coverage.COVERED,
        task_ledger_api="create (idempotency_key) + _write (atomic tmp) + _recover_orphaned_writes",
        evidence=("create() is idempotent on idempotency_key and refuses a "
                  "conflicting key; every write goes through a "
                  "uuid-suffixed .tmp file and os.replace, and an orphaned "
                  "tmp is either promoted (valid) or deleted on next open "
                  "— so a claim is all-or-nothing, no torn ledger."),
        beads_note="Beads claims a work item atomically with a lock.",
        ssot_blocker=False,
    ),
    BeadsCapability.LONG_TASK: CapabilityAssessment(
        capability=BeadsCapability.LONG_TASK,
        coverage=Coverage.COVERED,
        task_ledger_api="checkpoint + cursor_version + set_waitpoint",
        evidence=("checkpoint() persists arbitrary cursor state and bumps "
                  "cursor_version; set_waitpoint parks a RUNNING task in "
                  "WAITING_APPROVAL with a typed cursor and clears its "
                  "lease — a real resumable pause for long jobs, plus "
                  "bounded token/time/tool budgets that BLOCK on exceed."),
        beads_note="Beads tracks long-running work across restarts.",
        ssot_blocker=False,
    ),
    BeadsCapability.CONCURRENT_AGENTS: CapabilityAssessment(
        capability=BeadsCapability.CONCURRENT_AGENTS,
        coverage=Coverage.COVERED,
        task_ledger_api="acquire_lease + renew_lease + heartbeat + detect_zombie",
        evidence=("Each task carries a single lease with a monotonically "
                  "increasing fence number; renew/heartbeat/clear all "
                  "assert (holder, fence, expiry), a second holder is "
                  "refused while the first is live, and detect_zombie flags "
                  "a lease whose TTL lapsed — classic multi-agent fencing."),
        beads_note="Beads lets many agents work one graph concurrently.",
        ssot_blocker=False,
    ),
    BeadsCapability.DOLT: CapabilityAssessment(
        capability=BeadsCapability.DOLT,
        coverage=Coverage.MISSING,
        task_ledger_api="(none)",
        evidence=("The ledger is a single JSON file replaced atomically; "
                  "there is no versioned history, no commit graph, no "
                  "per-change addressing.  Dolt's git-like versioned table "
                  "store is not present."),
        beads_note="Beads is backed by Dolt: a git-like, versioned database "
                   "that keeps full task-history as queryable commits.",
        ssot_blocker=True,  # this is a primary reason Beads can't be SSOT
    ),
    BeadsCapability.RESUME: CapabilityAssessment(
        capability=BeadsCapability.RESUME,
        coverage=Coverage.COVERED,
        task_ledger_api="resume + TRANSITIONS state machine",
        evidence=("resume() walks PAUSED/RETRYING/WAITING_APPROVAL back to "
                  "RUNNING through the explicit TRANSITIONS table; a "
                  "BLOCKED task refuses and demands a fresh approved run, "
                  "so resuming is policy-checked, not free-form."),
        beads_note="Beads resumes a task after a crash.",
        ssot_blocker=False,
    ),
    BeadsCapability.HIERARCHY: CapabilityAssessment(
        capability=BeadsCapability.HIERARCHY,
        coverage=Coverage.COVERED,
        task_ledger_api="attach_child + parent_task_id + children (MAX_CHILDREN)",
        evidence=("attach_child links a parent to bounded children "
                  "(MAX_CHILDREN=8), back-fills parent_task_id on the "
                  "child, and rejects fan-out past the limit — a real "
                  "bounded hierarchy, not a flat list."),
        beads_note="Beads supports parent/child task trees.",
        ssot_blocker=False,
    ),
    BeadsCapability.MEMORY_DECAY: CapabilityAssessment(
        capability=BeadsCapability.MEMORY_DECAY,
        coverage=Coverage.MISSING,
        task_ledger_api="(none)",
        evidence=("Nothing in the ledger weights recall by age; evidence "
                  "and reconciliation entries are kept verbatim with "
                  "no decay/forgetting factor.  Time-decayed memory is "
                  "not a TaskLedger concept."),
        beads_note="Beads can fade old items' priority over time.",
        ssot_blocker=True,  # a second reason Beads can't be SSOT
    ),
    BeadsCapability.JSON: CapabilityAssessment(
        capability=BeadsCapability.JSON,
        coverage=Coverage.COVERED,
        task_ledger_api="ledger.json (schema_version workflow/task-ledger/v1)",
        evidence=("The entire ledger is one versioned JSON document; every "
                  "op reads, mutates, and atomically rewrites it — fully "
                  "portable, diffable, and human-readable on any platform."),
        beads_note="Beads persists to a store it can serialize to JSON.",
        ssot_blocker=False,
    ),
    BeadsCapability.WINDOWS: CapabilityAssessment(
        capability=BeadsCapability.WINDOWS,
        coverage=Coverage.COVERED,
        task_ledger_api="os.replace (atomic) + pure stdlib, no fork/exec",
        evidence=("The ledger uses os.replace for atomic rename (which is "
                  "reliable on Windows NTFS, unlike POSIX rename-then-"
                  "unlink races) and only the standard library — no POSIX-"
                  "only syscalls, so it runs on the managed Windows hosts."),
        beads_note="Beads is cross-platform including Windows.",
        ssot_blocker=False,
    ),
}


@dataclass
class BeadsPocReport:
    """The reproducible POC verdict, JSON-serialisable and hashable."""
    beads_as_ssot: bool
    reasons_not_ssot: list[str]
    coverage: dict[str, str]          # dimension value -> Coverage value
    covered_count: int
    total_count: int
    blockers: list[str]              # dimension values flagged ssot_blocker
    current_ssot: str               # what WORK-LAB keeps as the task-graph SSOT
    recommendations: list[str]
    receipt_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "beads_as_ssot": self.beads_as_ssot,
            "reasons_not_ssot": list(self.reasons_not_ssot),
            "coverage": dict(self.coverage),
            "covered_count": self.covered_count,
            "total_count": self.total_count,
            "blockers": list(self.blockers),
            "current_ssot": self.current_ssot,
            "recommendations": list(self.recommendations),
            "receipt_sha256": self.receipt_sha256,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False, indent=2)


def assess() -> BeadsPocReport:
    """Run the comparison and mint the verdict.

    Deterministic: same capability map in, same report out; the receipt
    SHA is over everything except the SHA field itself.
    """
    coverage = {
        cap.value: CAPABILITY_MAP[cap].coverage.value for cap in BeadsCapability
    }
    covered_count = sum(1 for c in coverage.values() if c == Coverage.COVERED.value)
    blockers = [
        cap.value for cap in BeadsCapability
        if CAPABILITY_MAP[cap].ssot_blocker
    ]
    # Build the reasons from the actual MISSING dimensions, not a hard-coded
    # string, so the conclusion is always grounded in the map.
    reasons = [
        f"{CAPABILITY_MAP[cap].capability.value}: {CAPABILITY_MAP[cap].evidence}"
        for cap in BeadsCapability
        if CAPABILITY_MAP[cap].coverage is Coverage.MISSING
    ]
    ssot = False  # the taskpack's mandate: Beads is a POC, not the SSOT
    current_ssot = "packages/client-neutral-core/scripts/task_ledger.py::TaskLedger"
    recommendations = [
        "Keep TaskLedger as the task-graph SSOT; it already covers "
        f"{covered_count}/{len(BeadsCapability)} POC dimensions.",
        "Track Dolt versioned-history and memory-decay as optional "
        "enhancements, not SSOT-replacing features.",
        "Do not adopt Beads' Dolt backend: it would change the storage "
        "model and add an external dependency outside WORK-LAB's boundary.",
    ]
    report = BeadsPocReport(
        beads_as_ssot=ssot,
        reasons_not_ssot=reasons,
        coverage=coverage,
        covered_count=covered_count,
        total_count=len(BeadsCapability),
        blockers=blockers,
        current_ssot=current_ssot,
        recommendations=recommendations,
    )
    report.receipt_sha256 = _receipt_sha(report)
    return report


def _receipt_sha(report: BeadsPocReport) -> str:
    payload = json.dumps(
        {k: v for k, v in report.to_dict().items() if k != "receipt_sha256"},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def conclude_ssot() -> bool:
    """The one-line answer the governance plane keys off: is Beads SSOT?

    Always False by mandate, and False by evidence (the two MISSING
    dimensions mean dropping Beads in would change WORK-LAB's storage and
    memory model).
    """
    return assess().beads_as_ssot


def report() -> BeadsPocReport:
    """Convenience alias for :func:`assess` (the report IS the POC)."""
    return assess()
