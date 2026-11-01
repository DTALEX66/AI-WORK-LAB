"""SkillSpector gate (WL-300 / ch 26): the 7-stage extension pipeline.

ch 26 mandates that every Skill / MCP / Hook / Plugin / Agent Package
pass through, in order::

    Source -> Canonical repo -> License -> Hash -> SkillSpector -> Sandbox -> Approval

WORK-LAB OWNS the pipeline (ch 41).  SkillSpector itself is an external
scanner (NVIDIA, Apache-2.0); by the ch 35 external-asset rule it is
NEVER vendored — it must first be registered in the Extension Registry
and approved before its stage can run.  A scanner that is not approved is
a fail-closed DENY at the SkillSpector stage, not a silent pass.  And the
final PASS authority is WORK-LAB's Approval stage, never the scanner's
own verdict (ch 41: "最终谁有资格宣布 PASS").
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Union

# No cross-module import on purpose: services/ modules are loaded by
# spec_from_file_location under stable sys.modules names, and a hard
# `from services.security.extension_registry import ...` would resolve
# only when that sibling is pre-registered.  The gate is self-contained
# and duck-typed on the entry: it needs only the fields every governed
# extension carries.  _GOVERNED_TYPES mirrors extension_registry's
# ExtensionType.ALL (the five ch 26 classes) — tests assert the two agree.
_GOVERNED_TYPES = frozenset(
    {"skill", "mcp", "hook", "plugin", "agent_package"})


class Stage:
    """The seven ch 26 stages, in their fixed order."""

    SOURCE = "source"
    CANONICAL = "canonical_repo"
    LICENSE = "license"
    HASH = "hash"
    SKILLSPECTOR = "skillspector"
    SANDBOX = "sandbox"
    APPROVAL = "approval"

    ORDER = [SOURCE, CANONICAL, LICENSE, HASH, SKILLSPECTOR, SANDBOX, APPROVAL]

    @classmethod
    def index(cls, name: str) -> int:
        return cls.ORDER.index(name)


class Severity:
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    _RANK = {INFO: 0, LOW: 1, MEDIUM: 2, HIGH: 3, CRITICAL: 4}

    @classmethod
    def rank(cls, s: str) -> int:
        return cls._RANK.get(s, 0)

    @classmethod
    def is_blocking(cls, s: str, allow_severities: Set[str]) -> bool:
        """A finding blocks when its severity is NOT in the allow-set."""
        return s not in allow_severities


@dataclass
class Finding:
    category: str           # prompt_injection / data_exfiltration / memory_poisoning
    # / mcp_tool_poisoning / ast / yara / taint / ...
    severity: str
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"category": self.category, "severity": self.severity,
                "message": self.message}


@dataclass
class ScannerResult:
    """What an APPROVED SkillSpector run returns.  None means the scanner
    is not available/approved, which is a fail-closed DENY."""

    approved: bool
    findings: List[Finding] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ScannerResult":
        return cls(approved=bool(d.get("approved")),
                   findings=[Finding(**f) for f in d.get("findings", [])])


@dataclass
class GateVerdict:
    extension_name: str
    allowed: bool
    stage_reached: str                 # furthest stage that PASSED
    reasons: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)

    def receipt_sha256(self) -> str:
        import hashlib
        payload = json.dumps(
            {"n": self.extension_name, "a": self.allowed,
             "s": self.stage_reached, "r": self.reasons, "e": self.evidence},
            sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {"extension_name": self.extension_name, "allowed": self.allowed,
                "stage_reached": self.stage_reached, "reasons": self.reasons,
                "evidence": self.evidence, "receipt_sha256": self.receipt_sha256()}


class SkillspectorGate:
    """Runs the 7-stage pipeline and returns a WORK-LAB verdict."""

    SCHEMA = "work-lab/skillspector-gate/v1"

    def __init__(self, acceptable_licenses: Optional[Set[str]] = None,
                 allow_severities: Optional[Set[str]] = None) -> None:
        # fail-closed defaults: an unknown/misspelled license is not accepted,
        # and only info/low findings are tolerated without blocking.
        self.acceptable_licenses = set(
            acceptable_licenses
            if acceptable_licenses is not None
            else {"Apache-2.0", "MIT", "MPL-2.0", "BSD-2-Clause", "BSD-3-Clause",
                  "ISC", "GPL-3.0"})
        self.allow_severities = set(
            allow_severities
            if allow_severities is not None
            else {Severity.INFO, Severity.LOW})

    def evaluate(self, ext: Any,
                 scanner: Optional[ScannerResult] = None,
                 sandbox_passed: bool = False,
                 approval: Optional[Dict[str, Any]] = None,
                 actual_hash: Optional[str] = None) -> GateVerdict:
        reasons: List[str] = []
        evidence: Dict[str, Any] = {}
        reached = Stage.SOURCE

        def deny(stage: str, why: str) -> GateVerdict:
            reasons.append(f"[{stage}] {why}")
            return GateVerdict(ext.name, False, Stage.ORDER[Stage.index(stage) - 1]
                               if Stage.index(stage) else Stage.SOURCE,
                               reasons, evidence)

        # 1. SOURCE — a well-formed source url.
        if not ext.canonical_url:
            return deny(Stage.SOURCE, "no source url; the pipeline cannot start")
        reached = Stage.SOURCE

        # 2. CANONICAL REPO — must be pinned to a canonical url (not a fork).
        if not ext.canonical_url or ext.type not in _GOVERNED_TYPES:
            return deny(Stage.CANONICAL, "extension type is not a governed class")
        evidence["canonical_url"] = ext.canonical_url
        evidence["commit"] = ext.commit
        reached = Stage.CANONICAL

        # 3. LICENSE — fail-closed: unknown license is not acceptable.
        if ext.license not in self.acceptable_licenses:
            return deny(Stage.LICENSE,
                        f"license {ext.license!r} is not in the acceptable set")
        evidence["license"] = ext.license
        reached = Stage.LICENSE

        # 4. HASH — must be pinned, and must still match if an actual is given.
        if not ext.hash:
            return deny(Stage.HASH, "no sha256 recorded; artifact is not pinned")
        if actual_hash is not None and actual_hash != ext.hash:
            return deny(Stage.HASH,
                        f"hash mismatch: pinned {ext.hash} != actual {actual_hash}")
        evidence["hash"] = ext.hash
        reached = Stage.HASH

        # 5. SKILLSPECTOR — fail-closed if the scanner is not available/approved.
        if scanner is None or not scanner.approved:
            return deny(Stage.SKILLSPECTOR,
                        "SkillSpector scanner not registered+approved; "
                        "extension cannot pass the gate (ch 26 / ch 35)")
        blocking = [f for f in scanner.findings
                   if Severity.is_blocking(f.severity, self.allow_severities)]
        evidence["skillspector"] = {"findings": [f.to_dict() for f in scanner.findings],
                                   "blocking": [f.to_dict() for f in blocking]}
        if blocking:
            return deny(Stage.SKILLSPECTOR,
                        f"{len(blocking)} blocking finding(s): "
                        + "; ".join(f"{f.category}/{f.severity}" for f in blocking))
        reached = Stage.SKILLSPECTOR

        # 6. SANDBOX — must have been run and passed in isolation.
        if not sandbox_passed:
            return deny(Stage.SANDBOX, "sandbox did not pass in isolation")
        evidence["sandbox"] = True
        reached = Stage.SANDBOX

        # 7. APPROVAL — the PASS authority is WORK-LAB, never the scanner.
        if not approval or not approval.get("granted"):
            return deny(Stage.APPROVAL, "no WORK-LAB approval record on file")
        authority = str(approval.get("granted_by", "")).lower().replace(
            "-", "").replace("_", "").replace(" ", "")
        if "skillspector" in authority or "snyk" in authority:
            return deny(Stage.APPROVAL,
                        "approval was granted by the scanner, not WORK-LAB "
                        "(ch 41: the gate owns the PASS authority)")
        evidence["approval"] = {"granted_by": approval.get("granted_by", "")}
        return GateVerdict(ext.name, True, Stage.APPROVAL, reasons, evidence)
