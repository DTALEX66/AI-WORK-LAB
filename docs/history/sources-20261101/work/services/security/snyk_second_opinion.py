"""Snyk second opinion (WL-310 / ch 27).

Snyk Agent Scan is the *second* opinion on top of the SkillSpector gate
(ch 26).  ch 27's two load-bearing rules:

* an UNKNOWN MCP must run in an ISOLATED environment — never directly on
  the host;
* a third-party stdio MCP server must NOT be scanned by executing it on the
  host (a host-direct scan would run the very code under test, unsandboxed).

Snyk itself is an external tool; by ch 35 WORK-LAB never vendors it — it
holds only Snyk's verdict (a structured receipt) and cross-checks it
against the gate's own verdict.  The second opinion can AGREE, DISAGREE,
or be ABSENT (Snyk not available) — absence is honest, it does not
override the gate, it just says "no corroboration yet".
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


class ScanMode:
    """How a scan may be run against an extension's code."""

    ISOLATED = "isolated"        # run in a sandbox / container
    HOST_DIRECT = "host_direct"  # run directly on the host (forbidden for stdio MCP)


class SnykSeverity:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    _BLOCKING = frozenset({HIGH, CRITICAL})

    @classmethod
    def blocking(cls, severities: List[str]) -> List[str]:
        return [s for s in severities if s in cls._BLOCKING]


@dataclass
class SnykResult:
    """Structured receipt of an external Snyk Agent Scan run.

    ``available=False`` is the honest "no Snyk data" state; it must never
    be read as "clean" — it means corroboration is missing.
    """

    available: bool
    mode: str = ScanMode.ISOLATED          # how it ran (isolated vs host-direct)
    vulnerabilities: List[Dict[str, Any]] = field(default_factory=list)
    notes: str = ""

    def blocking_severities(self) -> List[str]:
        return [v.get("severity") for v in self.vulnerabilities
                if v.get("severity") in SnykSeverity._BLOCKING]

    @classmethod
    def none(cls) -> "SnykResult":
        return cls(available=False, notes="snyk not available; no corroboration")


@dataclass
class SecondOpinion:
    extension_name: str
    relation: str                 # "agrees" | "disagrees" | "absent"
    requires_isolation: bool       # ch 27: unknown MCP must be isolated
    host_direct_allowed: bool      # ch 27: stdio MCP must not be host-scanned
    reasons: List[str] = field(default_factory=list)

    def receipt_sha256(self) -> str:
        import hashlib
        payload = json.dumps(
            {"n": self.extension_name, "r": self.relation,
             "iso": self.requires_isolation, "host_ok": self.host_direct_allowed,
             "why": self.reasons}, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {"extension_name": self.extension_name, "relation": self.relation,
                "requires_isolation": self.requires_isolation,
                "host_direct_allowed": self.host_direct_allowed,
                "reasons": self.reasons,
                "receipt_sha256": self.receipt_sha256()}


class SnykSecondOpinion:
    """Cross-checks a Snyk receipt against the gate + isolation policy."""

    SCHEMA = "work-lab/snyk-second-opinion/v1"

    def __init__(self, known_mcp: Optional[Set[str]] = None,
                 isolation_required: Optional[Set[str]] = None) -> None:
        # known_mcp: names already registered+approved, so they need no
        # forced isolation.  isolation_required: explicitly quarantined.
        self.known_mcp = set(known_mcp or set())
        self.isolation_required = set(isolation_required or set())

    def evaluate(self, ext: Any,
                 gate_allows: bool,
                 snyk: Optional[SnykResult] = None) -> SecondOpinion:
        reasons: List[str] = []
        is_mcp = ext.type == "mcp"
        is_stdio = bool(getattr(ext, "stdio", False)) or \
            "stdio" in str(getattr(ext, "capability", ""))

        # ch 27 rule 1: an unknown MCP must be isolated.
        requires_isolation = (is_mcp and ext.name not in self.known_mcp) \
            or ext.name in self.isolation_required
        if requires_isolation:
            reasons.append("unknown/registered-forced MCP -> isolated runtime required")

        # ch 27 rule 2: a stdio MCP server must NOT be host-scanned.
        host_direct_allowed = True
        if is_stdio:
            host_direct_allowed = False
            reasons.append("stdio MCP server -> host-direct scan is forbidden")

        # cross-check: is Snyk available?
        if snyk is None or not snyk.available:
            return SecondOpinion(ext.name, "absent", requires_isolation,
                                 host_direct_allowed,
                                 reasons + ["snyk not available; no second opinion yet"])

        # a host-direct scan of a stdio server is itself a policy violation.
        if host_direct_allowed is False and snyk.mode == ScanMode.HOST_DIRECT:
            return SecondOpinion(ext.name, "disagrees", requires_isolation,
                                 host_direct_allowed,
                                 reasons + ["snyk ran host-direct against a stdio server; policy violation"])

        blocking = snyk.blocking_severities()
        if blocking:
            # Snyk found blocking vulns: it disagrees with a gate that
            # would have allowed the extension.
            relation = "disagrees"
            reasons.append(f"snyk blocking findings: {', '.join(blocking)}")
        elif gate_allows:
            relation = "agrees"
            reasons.append("snyk concurs with the gate allow")
        else:
            # gate denied for its own reasons; snyk adds nothing blocking.
            relation = "absent"
            reasons.append("gate already denied; snyk has no blocking findings")

        return SecondOpinion(ext.name, relation, requires_isolation,
                             host_direct_allowed, reasons)
