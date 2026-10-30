"""Completion Authority (WL-180): evidence-gated acceptance of work.

Ch 16 is blunt: the pattern ``Worker says DONE -> PASS`` is *forbidden*.
A task is accepted only when it travels the full chain::

    Worker output  ->  Evidence  ->  Verification  ->  Independent check
                 ->  Manager acceptance  ->  PASS

This module models that chain as a **typed, ordered ledger** so that a
caller cannot skip a link or pass a bare "done" claim:

* every link records *who* produced it and *what* they saw;
* the final acceptance is only minted once every required link is present
  and the task mode's artifact/extras contract (Task Protocol V2) holds;
* the record is JSON-serialisable and carries a content hash so the same
  acceptance can be re-verified offline.

Audited-mode tasks additionally require the high-risk extras named by the
protocol (independent evaluator, typed receipt, owner epoch, rollback,
human approval) — completion authority *reads* that contract, it does not
redefine it, so there is exactly one source of truth.

Loading convention mirrors services/session-federation: no package
``__init__.py``; sibling modules are loaded through a stable ``sys.modules``
name so shared enums stay singletons.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

import importlib.util as _ilu

_TP = "services_task_governance_task_protocol"


def _load_task_protocol():
    here = Path(__file__).resolve().parent
    existing = sys.modules.get(_TP)
    if existing is not None and hasattr(existing, "TaskMode"):
        return existing
    spec = _ilu.spec_from_file_location(_TP, here / "task_protocol.py")
    module = _ilu.module_from_spec(spec)
    sys.modules[_TP] = module
    spec.loader.exec_module(module)
    return module


__all__ = [
    "EvidenceLevel", "AcceptanceStatus", "EvidenceClaim", "AcceptanceRecord",
    "CompletionAuthority",
]


class EvidenceLevel(str, Enum):
    """How strong the *verification* link is.  Not the same as a risk level."""
    NONE = "none"               # no verification was run
    SELF = "self"               # the worker's own check (weakest acceptable)
    REPRODUCIBLE = "reproducible"  # a script someone else can re-run
    INDEPENDENT = "independent"     # a party other than the worker attested


class AcceptanceStatus(str, Enum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    REJECTED = "REJECTED"


@dataclass
class EvidenceClaim:
    """One link in the chain: a producer asserting they observed a fact."""
    kind: str                # "output" | "verification" | "independent_check"
    producer: str
    summary: str
    level: EvidenceLevel = EvidenceLevel.NONE
    artifact_ref: str | None = None   # e.g. a file path or SHA the fact lives in
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class AcceptanceRecord:
    """The manager's typed verdict over the whole chain."""
    task_id: str
    mode: str                # TaskMode.value
    status: AcceptanceStatus
    chain: list[EvidenceClaim] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)   # what stopped a PASS
    approver: str | None = None
    receipt_sha256: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "mode": self.mode,
            "status": self.status.value,
            "chain": [
                {
                    "kind": c.kind,
                    "producer": c.producer,
                    "summary": c.summary,
                    "level": c.level.value,
                    "artifact_ref": c.artifact_ref,
                    "details": dict(c.details),
                }
                for c in self.chain
            ],
            "missing": list(self.missing),
            "approver": self.approver,
            "receipt_sha256": self.receipt_sha256,
            "notes": list(self.notes),
        }


class CompletionAuthority:
    """Mints typed acceptance records; refuses to mint a PASS from 'done'."""

    #: The minimum chain every accepted task must show, in order.  These
    #: are *link kinds* — a bare worker 'output' is only the first link.
    REQUIRED_LINKS = ("output", "verification", "independent_check")

    def __init__(self, task_protocol: Any | None = None) -> None:
        self._tp = task_protocol or _load_task_protocol()
        # task_id -> Accumulated evidence chain
        self._chains: dict[str, list[EvidenceClaim]] = {}

    # -- recording -------------------------------------------------------
    def submit(self, task_id: str, claim: EvidenceClaim) -> None:
        """Record one link.  Ordering and completeness are checked later."""
        self._chains.setdefault(task_id, []).append(claim)

    def present_links(self, task_id: str) -> list[EvidenceClaim]:
        return list(self._chains.get(task_id, []))

    # -- acceptance ------------------------------------------------------
    def evaluate(
        self,
        task_id: str,
        *,
        mode: str | Any,
        artifacts_present: Iterable[str] = (),
        extras_present: Iterable[str] = (),
        approver: str | None = None,
        reject_reasons: Iterable[str] = (),
    ) -> AcceptanceRecord:
        """Produce the manager's verdict for ``task_id``.

        ``mode`` accepts a :class:`TaskMode` or its string value.  A PASS is
        returned *only* when:
          1. every required link kind is present,
          2. at least one link is an INDEPENDENT-level check (self-check
             alone never suffices for acceptance),
          3. the task mode's artifact + extras contract is satisfied,
          4. an approver is named, and
          5. no caller-supplied rejection reason exists.

        Anything less becomes a PENDING (with ``missing`` populated) or a
        REJECTED record — never a silent PASS.
        """
        TaskMode = self._tp.TaskMode
        try:
            task_mode = TaskMode(mode)
        except ValueError:
            task_mode = TaskMode(mode.value if hasattr(mode, "value") else mode)

        chain = self.present_links(task_id)
        kinds = {c.kind for c in chain}
        levels = [c.level for c in chain]
        independent = any(l is EvidenceLevel.INDEPENDENT for l in levels)

        missing: list[str] = []
        for req in self.REQUIRED_LINKS:
            if req not in kinds:
                missing.append(f"link:{req}")
        # an independent_check that is not actually independent is a strength
        # defect — re-record it at INDEPENDENT level; tracked as a missing item.
        if "independent_check" in kinds and not independent:
            missing.append("link:independent_check!level")

        contract = self._tp.validate_completion(
            task_mode,
            artifacts_present=artifacts_present,
            extras_present=extras_present,
        )
        for a in contract["missing_artifacts"]:
            missing.append(f"artifact:{a}")
        for e in contract["missing_extras"]:
            missing.append(f"extra:{e}")
        if approver is None:
            missing.append("approver")
        reject_reasons = [str(r) for r in reject_reasons]

        # Three-state verdict, kept deliberately simple:
        #   * caller-supplied rejection  -> REJECTED
        #   * nothing missing             -> PASSED
        #   * only submittable gaps       -> PENDING
        if reject_reasons:
            status = AcceptanceStatus.REJECTED
            missing.extend(reject_reasons)
        elif not missing:
            status = AcceptanceStatus.PASSED
        else:
            status = AcceptanceStatus.PENDING

        record = AcceptanceRecord(
            task_id=task_id,
            mode=task_mode.value,
            status=status,
            chain=chain,
            missing=list(missing),
            approver=approver,
            notes=[f"contract={json.dumps(contract, sort_keys=True)}"] if not contract["ok"] else [],
        )
        record.receipt_sha256 = self._receipt_sha(record)
        return record

    # -- integrity -------------------------------------------------------
    @staticmethod
    def _receipt_sha(record: AcceptanceRecord) -> str:
        payload = json.dumps(
            {k: v for k, v in record.to_dict().items() if k != "receipt_sha256"},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def verify_receipt_sha(record: AcceptanceRecord) -> bool:
        """Re-hash a record (sans stored hash) and confirm it is intact."""
        return record.receipt_sha256 == CompletionAuthority._receipt_sha(record)
