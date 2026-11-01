"""ArcheAxis memory-query seam — WORK-LAB V2 three-project boundary.

WORK-LAB keeps only the QUERY surface (it asks, it does not store).
The memory BACKEND (retain/recall/reflect, long-term store, provider,
import) migrates to DTALEX66/ArcheAxis-Knowledge-OS.

This module is the single allowed import path for any WORK-LAB code that
needs to reach memory. Anything that stores/retains/recalls LENDING is a
boundary violation caught by scripts/ci/verify_three_project_boundary.py.

Authority: .project/governance/three-project-boundary.json
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MemoryQueryContract:
    """Thin ask-only surface. No local persistence, no retain/recall/reflect."""
    query: str
    session_id: Optional[str] = None
    scope: str = "session"
    context_capsule: Optional[Dict[str, Any]] = None

    def to_payload(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "session_id": self.session_id,
            "scope": self.scope,
            "context_capsule": self.context_capsule,
        }

    def source_note(self) -> str:
        return ("WORK-LAB asks ArcheAxis; this contract carries no memory "
                "backend. retain/recall/reflect live in "
                "DTALEX66/ArcheAxis-Knowledge-OS.")


__all__ = ["MemoryQueryContract"]
