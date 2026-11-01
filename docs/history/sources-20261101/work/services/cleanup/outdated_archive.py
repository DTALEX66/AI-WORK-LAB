"""Outdated archive audit (WL-420 / ch 40): freeze-list + archive decisions.

ch 40 freezes ten self-built generic surfaces and redirects each to one of
five owned forms::

    STOP building:  Generic Agent Runtime / Generic Coding Agent /
                    Generic Chat/TUI / Full Agent Canvas / Generic Memory DB /
                    Generic RAG Memory / Generic Skills Runtime /
                    Generic Sandbox Runtime / Generic Model SDK /
                    Independent RSI Engine
    INSTEAD:        Adapter / Provider / Protocol / Policy / Registry

This is an AUDIT, not an archiver.  Given the inventory of what a repo
actually contains (path + label + size, the kind of rows the repo-slimming
auditor already produces), it maps each frozen generic surface to the
redirect it must take and to an archive DISPOSITION (archive / keep-as-
adapter / delete-after-migration).  Nothing is moved or deleted here — a
disposition is a decision, and the deletion path is gated by the same
user-authorization + regenerable-only rules as spill cleanup.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


class ArchiveDisposition:
    ARCHIVE = "archive"                      # move to an archive area, keep
    KEEP_AS_ADAPTER = "keep_as_adapter"       # re-frame as a thin adapter
    MIGRATE_THEN_DELETE = "migrate_then_delete"  # safe after a user verifies
    KEEP = "keep"                            # not actually frozen / still core

    ALL = (ARCHIVE, KEEP_AS_ADAPTER, MIGRATE_THEN_DELETE, KEEP)
    _MEMBERS = frozenset(ALL)


# ch 40's frozen generic surfaces, keyed by a path/label fragment.  The
# redirect is the ch 40 five-form replacement.
FROZEN_SURFACES: Dict[str, str] = {
    "generic-agent-runtime": "Adapter",
    "generic-coding-agent": "Adapter",
    "generic-chat-tui": "Registry",
    "full-agent-canvas": "Registry",
    "generic-memory-db": "Provider",
    "generic-rag-memory": "Provider",
    "generic-skills-runtime": "Registry",
    "generic-sandbox-runtime": "Policy",
    "generic-model-sdk": "Protocol",
    "independent-rsi-engine": "Protocol",
}

# path fragments that identify each frozen surface in a repo
_SURFACE_PATH_HINTS: Dict[str, str] = {
    "generic-agent-runtime": ("agent_runtime", "generic-runtime", "agents/core"),
    "generic-coding-agent": ("coding_agent", "generic-coder"),
    "generic-chat-tui": ("chat_tui", "tui/chat", "chat-ui"),
    "full-agent-canvas": ("agent_canvas", "full-canvas", "canvas/agent"),
    "generic-memory-db": ("memory_db", "generic_memory", "mem/db"),
    "generic-rag-memory": ("rag_memory", "generic_rag", "rag/embed"),
    "generic-skills-runtime": ("skills_runtime", "generic_skills", "skills/rt"),
    "generic-sandbox-runtime": ("sandbox_runtime", "generic_sandbox", "sandbox/rt"),
    "generic-model-sdk": ("model_sdk", "generic_model", "models/sdk"),
    "independent-rsi-engine": ("rsi_engine", "independent_rsi", "evolution/engine"),
}


@dataclass
class ArchiveDecision:
    path: str
    surface: str                 # which frozen surface it maps to, or "generic"
    redirect: str                # Adapter / Provider / Protocol / Policy / Registry
    disposition: str
    reversible: bool
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OutdatedArchiver:
    """Read-only mapping of a repo's frozen generic surfaces to ch 40's
    redirect + archive disposition.  Never moves or deletes."""

    SCHEMA = "work-lab/outdated-archive/v1"

    def __init__(self, user_authorized: Optional[List[str]] = None,
                 extra_freeze: Optional[Dict[str, str]] = None) -> None:
        self._authorized = set(user_authorized or set())
        # a repo can add its own frozen surfaces on top of ch 40's list
        self._surfaces = dict(FROZEN_SURFACES)
        if extra_freeze:
            self._surfaces.update(extra_freeze)
        self._hints = dict(_SURFACE_PATH_HINTS)
        for name, redirect in (extra_freeze or {}).items():
            self._hints.setdefault(name, (name,))

    # -- matching ---------------------------------------------------------
    def identify(self, path: str) -> Optional[str]:
        """Return the frozen-surface key a path belongs to, or None.

        Paths use hyphens, hint fragments use underscores, so both sides are
        normalised (separator + hyphen -> underscore) before matching.
        """
        def _norm(s: str) -> str:
            return s.lower().replace(os.sep, "/").replace("-", "_")
        low = _norm(path)
        for surface, hints in self._hints.items():
            if any(_norm(h) in low for h in hints):
                return surface
        return None

    def decide(self, path: str) -> ArchiveDecision:
        surface = self.identify(path) or "generic"
        redirect = self._surfaces.get(surface, "Registry")
        if surface == "generic":
            # not one of the ch 40 frozen names: default to a plain archive,
            # reversible, no auto-delete.
            return ArchiveDecision(path, "generic", redirect,
                                   ArchiveDisposition.KEEP, True,
                                   "not a ch 40 frozen surface; keep")
        # frozen generic surface: re-frame as the redirect form.
        if path in self._authorized:
            return ArchiveDecision(path, surface, redirect,
                                   ArchiveDisposition.MIGRATE_THEN_DELETE, True,
                                   "frozen surface, user-authorized to migrate then "
                                   "remove once the adapter is live")
        return ArchiveDecision(path, surface, redirect,
                               ArchiveDisposition.KEEP_AS_ADAPTER, True,
                               f"frozen: redirect to a {redirect} adapter; keep the "
                               "bytes until the adapter is verified, no auto-delete")

    # -- batch + report ----------------------------------------------------
    def archive(self, inventory: List[str]) -> Dict[str, Any]:
        decisions = [self.decide(p) for p in inventory]
        summary: Dict[str, int] = {d: 0 for d in ArchiveDisposition.ALL}
        for d in decisions:
            summary[d.disposition] += 1
        frozen = [d for d in decisions if d.surface != "generic"]
        report = {
            "schema": self.SCHEMA,
            "inventory_count": len(inventory),
            "frozen_found": len(frozen),
            "summary": summary,
            "decisions": [d.to_dict() for d in decisions],
        }
        return report

    @staticmethod
    def receipt_sha256(report: Dict[str, Any]) -> str:
        import hashlib
        payload = json.dumps(report, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
