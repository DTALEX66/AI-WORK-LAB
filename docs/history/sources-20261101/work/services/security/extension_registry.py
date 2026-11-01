"""Extension Registry (WL-320 / ch 26 + ch 35 + ch 41 "must own").

WORK-LAB fronts every external extension — Skill, MCP, Hook, Plugin,
Agent Package — behind one registry that it OWNS (ch 41's Capability
Registry).  ch 35 (external-asset rule) is the load-bearing constraint:
a third-party repo / model / runtime is NEVER vendored.  The registry
stores only the eight identifying fields and an install recipe::

    name, canonical_url, version, commit, hash,
    license, install_recipe, capability

plus WORK-LAB governance state.  It is a single-writer, idempotent
registry: registering the same (name, type, version) twice is a no-op
that must reproduce the same entry, and any entry whose recorded hash
no longer matches its canonical source is quarantined, not silently
trusted.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


class ExtensionType:
    """The five extension classes ch 26 requires the pipeline to gate."""

    SKILL = "skill"
    MCP = "mcp"
    HOOK = "hook"
    PLUGIN = "plugin"
    AGENT_PACKAGE = "agent_package"

    ALL = (SKILL, MCP, HOOK, PLUGIN, AGENT_PACKAGE)
    _MEMBERS = frozenset(ALL)

    @classmethod
    def is_valid(cls, t: str) -> bool:
        return t in cls._MEMBERS


class QuarantineError(Exception):
    """Raised when an entry fails its hash/registration invariant."""


@dataclass
class ExtensionEntry:
    """One registered external extension — ch 35's eight fields + state."""

    name: str
    type: str                      # an ExtensionType member
    canonical_url: str
    version: str
    commit: str = ""               # pinned for deterministic install
    hash: str = ""                 # sha256 of the canonical artifact
    license: str = "unknown"
    install_recipe: str = ""       # how to (re)produce it; NOT the body
    capability: str = ""           # the capability it provides
    registered: bool = True        # governance state
    quarantined: bool = False

    def key(self) -> tuple:
        """Identity for idempotent registration."""
        return (self.name, self.type, self.version)

    def to_manifest(self) -> Dict[str, Any]:
        """ch 35 portable manifest: EXACTLY the eight identifying fields.

        No extension body is ever emitted — only the recipe to rebuild it
        from its canonical source.  ``type`` is intentionally absent: it is
        this registry's classification dimension (and part of the identity
        key), not one of ch 35's external-asset fields.
        """
        return {
            "name": self.name,
            "canonical_url": self.canonical_url,
            "version": self.version,
            "commit": self.commit,
            "hash": self.hash,
            "license": self.license,
            "install_recipe": self.install_recipe,
            "capability": self.capability,
        }


class ExtensionRegistry:
    """Single-writer, idempotent, hash-checked extension registry."""

    SCHEMA = "work-lab/extension-registry/v1"

    def __init__(self) -> None:
        self._entries: Dict[tuple, ExtensionEntry] = {}
        self._last_error: Optional[str] = None

    # -- write (idempotent) -------------------------------------------------
    def register(self, entry: ExtensionEntry) -> ExtensionEntry:
        """Register or reproduce.  Re-registering the same key with an
        IDENTICAL entry is a no-op; with a DIFFERENT one the entry is
        quarantined (drift), never silently overwritten."""
        if not ExtensionType.is_valid(entry.type):
            raise QuarantineError(f"unknown extension type: {entry.type!r}")
        key = entry.key()
        existing = self._entries.get(key)
        if existing is None:
            self._entries[key] = entry
            self._last_error = None
            return entry
        if _stable(existing) == _stable(entry):
            return existing                       # true idempotent no-op
        existing.quarantined = True
        self._last_error = (
            f"re-register of {key} drifted from the stored entry; "
            "the original is quarantined, not overwritten")
        return existing

    def unregister(self, name: str, type: str, version: str) -> bool:
        return self._entries.pop((name, type, version), None) is not None

    # -- read / verify ------------------------------------------------------
    def get(self, name: str, type: str, version: str) -> Optional[ExtensionEntry]:
        return self._entries.get((name, type, version))

    def verify_hash(self, entry: ExtensionEntry,
                    actual_hash: str) -> bool:
        """ch 35: the recorded hash must still match the canonical source.
        A mismatch quarantines the entry — the registry never trusts an
        artifact whose hash moved."""
        ok = bool(entry.hash) and entry.hash == actual_hash
        if entry.hash and not ok:
            entry.quarantined = True
            self._last_error = (
                f"hash mismatch for {entry.key()}: recorded "
                f"{entry.hash} != actual {actual_hash}; quarantined")
        return ok

    def list(self, type: Optional[str] = None) -> List[ExtensionEntry]:
        rows = [e for e in self._entries.values()
                if type is None or e.type == type]
        rows.sort(key=lambda e: (e.type, e.name, e.version))
        return rows

    def manifest(self) -> List[Dict[str, Any]]:
        """ch 35 portable manifest: the eight fields, sorted, no bodies."""
        return [e.to_manifest() for e in self.list()]

    def __len__(self) -> int:
        return len(self._entries)

    def last_error(self) -> Optional[str]:
        return self._last_error


def _stable(e: ExtensionEntry) -> str:
    """Deterministic identity string for the idempotency check."""
    payload = json.dumps(e.to_manifest(), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
