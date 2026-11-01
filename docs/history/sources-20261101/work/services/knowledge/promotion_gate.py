"""Knowledge promotion gate (WL-P1-290 / ch 37): what may reach ArcheAxis.

ch 37 is the final content gate before anything crosses into the ArcheAxis
knowledge store (a different project's long-term asset).  It is the
enforcement of ch 44 item 19 — "ArcheAxis 只接收验证后的知识" — and sits
ONE LAYER ABOVE the Phase-6 memory boundary: that boundary already refuses
raw session material from becoming memory; this gate decides, for a
distilled record, whether it may actually be promoted to knowledge.

ch 37 is a whitelist + blacklist::

    ALLOW (eight categories, each pre-verified):
        verified lesson / accepted decision / stable workflow /
        benchmark result / failure taxonomy / provider reliability /
        approved skill / architecture knowledge

    FORBID (five kinds of material, detected in the content):
        raw bash / all-chat / secrets / unverified candidate / temp logs

A candidate is ALLOWED only when its category is on the whitelist, it is
marked verified, AND its content contains none of the five forbidden kinds.
Any single miss is a REJECT — the gate is fail-closed, because this is the
last door into a store another project owns.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


class KnowledgeCategory:
    """ch 37's eight allowed knowledge categories."""

    VERIFIED_LESSON = "verified_lesson"
    ACCEPTED_DECISION = "accepted_decision"
    STABLE_WORKFLOW = "stable_workflow"
    BENCHMARK_RESULT = "benchmark_result"
    FAILURE_TAXONOMY = "failure_taxonomy"
    PROVIDER_RELIABILITY = "provider_reliability"
    APPROVED_SKILL = "approved_skill"
    ARCHITECTURE_KNOWLEDGE = "architecture_knowledge"

    ALLOWED = (VERIFIED_LESSON, ACCEPTED_DECISION, STABLE_WORKFLOW,
               BENCHMARK_RESULT, FAILURE_TAXONOMY, PROVIDER_RELIABILITY,
               APPROVED_SKILL, ARCHITECTURE_KNOWLEDGE)
    _MEMBERS = frozenset(ALLOWED)

    @classmethod
    def is_allowed(cls, cat: str) -> bool:
        return cat in cls._MEMBERS


class ForbiddenKind:
    """ch 37's five forbidden material kinds (content, not category)."""

    RAW_BASH = "raw_bash"
    ALL_CHAT = "all_chat"
    SECRETS = "secrets"
    UNVERIFIED_CANDIDATE = "unverified_candidate"
    TEMP_LOG = "temp_log"

    ALL = (RAW_BASH, ALL_CHAT, SECRETS, UNVERIFIED_CANDIDATE, TEMP_LOG)
    _MEMBERS = frozenset(ALL)


# content detectors (best-effort, conservative — a false ALLOW into another
# project's store is far worse than a false reject that a re-distill fixes).
_SECRET_PATTERNS = [
    re.compile(r"(?i)\baws_access_key_id\s*[:=]\s*AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)\bprivate[_ ]key\b|-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*['\"][A-Za-z0-9+/=_-]{16,}['\"]"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}"),
]
# raw bash: a shell transcript is a run of command lines, each opening with a
# prompt token ending in "$" (user@host:~$  /  /tmp$  /  PS>) or a
# PowerShell "> " continuation.  Two-or-more such prompt-then-command lines
# is a transcript, not a one-line documented command in prose.  The char
# class must include @ and : (host: path prefixes); this is the door into
# another project's store, so under-detection is worse than over-detection.
_RAW_BASH_PROMPT = re.compile(r"(?m)^\s*(?:[\w.@:~/-]*[~]?\$|PS\d*>)\s+\S")
# temp logs: timestamp + a single log-level token at line start.  One level
# per line (not two); three-or-more such lines is a log dump.
_LOG_LINE = re.compile(
    r"(?m)^\[?\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?::\d{3})?\s+"
    r"(?:INFO|WARN|ERROR|DEBUG|TRACE|FATAL|CRIT|NOTICE|WARNING)\b")


@dataclass
class KnowledgeCandidate:
    """One distilled record being considered for promotion to knowledge."""

    candidate_id: str
    category: str
    content: str
    verified: bool
    provenance: str = ""            # e.g. "codex:s1" / a memory record id
    from_memory_boundary: bool = False  # did it already pass the Phase-6 gate?

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PromotionVerdict:
    candidate_id: str
    allowed: bool
    reasons: List[str] = field(default_factory=list)
    forbidden_kinds: List[str] = field(default_factory=list)

    def receipt_sha256(self) -> str:
        payload = json.dumps(
            {"n": self.candidate_id, "a": self.allowed,
             "why": self.reasons, "f": self.forbidden_kinds},
            sort_keys=True, ensure_ascii=False).encode("utf-8")
        import hashlib
        return hashlib.sha256(payload).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {"candidate_id": self.candidate_id, "allowed": self.allowed,
                "reasons": self.reasons, "forbidden_kinds": self.forbidden_kinds,
                "receipt_sha256": self.receipt_sha256()}


class KnowledgePromotionGate:
    """ch 37's final ALLOW/REJECT before ArcheAxis."""

    SCHEMA = "work-lab/knowledge-promotion/v1"

    # -- content detectors ------------------------------------------------
    def _forbidden_in(self, content: str, verified: bool) -> List[str]:
        found: List[str] = []
        low = content

        # UNVERIFIED_CANDIDATE: not marked verified (the whole point of ch37)
        if not verified:
            found.append(ForbiddenKind.UNVERIFIED_CANDIDATE)

        # SECRETS
        if any(p.search(low) for p in _SECRET_PATTERNS):
            found.append(ForbiddenKind.SECRETS)

        # RAW_BASH: prompt lines / a shell transcript
        if len(_RAW_BASH_PROMPT.findall(low)) >= 2 or re.search(r"(?m)^bash -c ", low):
            found.append(ForbiddenKind.RAW_BASH)

        # ALL_CHAT: a whole conversation, not a distilled one-liner.  Heuristic:
        # many alternating user/assistant turns, or a JSON list of messages.
        turn_hits = len(re.findall(r"(?i)\b(user|assistant|system|role)\s*[:=]\s*['\"]?", low))
        looks_like_message_array = bool(
            re.search(r"\[\s*\{[^{}]*\"?(role|content)\"?[^{}]*\}", low))
        if turn_hits >= 4 or looks_like_message_array:
            found.append(ForbiddenKind.ALL_CHAT)

        # TEMP_LOG: many timestamped log lines
        if len(_LOG_LINE.findall(low)) >= 3:
            found.append(ForbiddenKind.TEMP_LOG)

        return found

    # -- the decision -------------------------------------------------------
    def promote(self, cand: KnowledgeCandidate) -> PromotionVerdict:
        reasons: List[str] = []
        allowed = True

        # 1. category whitelist
        if not KnowledgeCategory.is_allowed(cand.category):
            allowed = False
            reasons.append(f"category {cand.category!r} is not one of ch 37's "
                          f"eight allowed knowledge categories")

        # 2. content blacklist
        forbidden = self._forbidden_in(cand.content, cand.verified)
        if forbidden:
            allowed = False
            reasons.append("forbidden material detected: " + ", ".join(forbidden))
        else:
            forbidden = []

        # 3. provenance hygiene: a promotion INTO another project's store
        #    must carry provenance so ArcheAxis can trace it back.
        if allowed and not (cand.provenance or cand.from_memory_boundary):
            allowed = False
            reasons.append("no provenance / memory-boundary provenance record; "
                           "ArcheAxis requires a traceable source")

        return PromotionVerdict(cand.candidate_id, allowed, reasons, forbidden)

    def batch(self, candidates: List[KnowledgeCandidate]) -> Dict[str, Any]:
        verdicts = [self.promote(c) for c in candidates]
        allowed = [v.candidate_id for v in verdicts if v.allowed]
        return {"schema": self.SCHEMA, "count": len(candidates),
                "allowed": allowed,
                "rejected": [v.candidate_id for v in verdicts if not v.allowed],
                "verdicts": [v.to_dict() for v in verdicts]}
