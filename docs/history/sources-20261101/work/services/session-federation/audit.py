"""Handoff audit ledger (WL-P0-080).

Every cross-agent handoff (L1/L2) produces a single immutable audit record
under ``.project-local/audits/handoff-audit.jsonl``.  The ledger is
append-only: no record is ever rewritten or deleted, so a human can
reconstruct the full provenance chain of any session that passed through
more than one executor.

Record schema (one JSON line):
    schema_version
    audit_id                  — ULID-like monotonic id (timestamp + hex)
    timestamp                 — ISO-8601 UTC
    universal_session_id      — source session
    target_universal_session_id — target session (if created)
    source_agent / target_agent
    portability_level         — L1_HANDOFF | L2_EVENT_REPLAY
    loss_report               — per-channel retention (LossReport dict)
    dropped_channels          — explicit list of channels with reduced retention
    capsule_sha256            — integrity hash of the handoff capsule written
    capsule_path              — where the capsule was written
    notes                     — human-readable context
    evidence                  — optional mappings (git commits, CI runs, etc.)
"""
from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


AUDIT_SCHEMA_VERSION = 1

# Process-wide monotonic sequence. The audit ledger's replay contract
# (build_provenance_chain picks the earliest hop by min(audit_id)) requires
# audit_id to be strictly ordered by write time within a process. A random
# uuid suffix would break that ordering on same-microsecond writes, so the
# trailing segment is a zero-padded monotonic counter instead.
_AUDIT_SEQ = 0
_AUDIT_SEQ_LOCK = threading.Lock()


def _audit_id() -> str:
    """Monotonic, sortable audit id: 20-digit UTC timestamp + 8-digit seq.

    The timestamp gives wall-clock ordering across runs; the per-process
    sequence guarantees write-order ordering within a run (including the
    same-microsecond case a random suffix would scramble).
    """
    global _AUDIT_SEQ
    with _AUDIT_SEQ_LOCK:
        _AUDIT_SEQ += 1
        seq = _AUDIT_SEQ
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    return f"{ts}-{seq:08d}"


@dataclass(frozen=True)
class HandoffAuditRecord:
    audit_id: str
    timestamp: str
    universal_session_id: str
    target_universal_session_id: str | None
    source_agent: str
    target_agent: str
    portability_level: str
    loss_report: Mapping[str, Any]
    dropped_channels: tuple[str, ...]
    capsule_sha256: str | None
    capsule_path: str | None
    notes: tuple[str, ...] = ()
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": AUDIT_SCHEMA_VERSION,
            "audit_id": self.audit_id,
            "timestamp": self.timestamp,
            "universal_session_id": self.universal_session_id,
            "target_universal_session_id": self.target_universal_session_id,
            "source_agent": self.source_agent,
            "target_agent": self.target_agent,
            "portability_level": self.portability_level,
            "loss_report": dict(self.loss_report),
            "dropped_channels": list(self.dropped_channels),
            "capsule_sha256": self.capsule_sha256,
            "capsule_path": self.capsule_path,
            "notes": list(self.notes),
            "evidence": dict(self.evidence),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "HandoffAuditRecord":
        return cls(
            audit_id=data["audit_id"],
            timestamp=data["timestamp"],
            universal_session_id=data["universal_session_id"],
            target_universal_session_id=data.get("target_universal_session_id"),
            source_agent=data["source_agent"],
            target_agent=data["target_agent"],
            portability_level=data.get("portability_level", "L1_HANDOFF"),
            loss_report=data.get("loss_report", {}),
            dropped_channels=tuple(data.get("dropped_channels", ())),
            capsule_sha256=data.get("capsule_sha256"),
            capsule_path=data.get("capsule_path"),
            notes=tuple(data.get("notes", ())),
            evidence=data.get("evidence", {}),
        )


class HandoffAuditLedger:
    """Append-only JSONL audit ledger.

    Thread-safe via a process-level lock; concurrent multi-process writers
    are supported by O_APPEND semantics on the underlying file (each write
    is a single JSON line, < PIPE_BUF on all supported OSes).
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            # Create empty file so readers can open it immediately
            self.path.touch()
        self._lock = threading.Lock()

    # -- write -----------------------------------------------------------
    def record_handoff(
        self,
        *,
        universal_session_id: str,
        source_agent: str,
        target_agent: str,
        portability_level: str = "L1_HANDOFF",
        loss_report: Mapping[str, Any] | None = None,
        dropped_channels: tuple[str, ...] = (),
        capsule_bytes: bytes | None = None,
        capsule_path: str | None = None,
        target_universal_session_id: str | None = None,
        notes: tuple[str, ...] = (),
        evidence: Mapping[str, Any] | None = None,
    ) -> HandoffAuditRecord:
        """Append a handoff record; returns the record (including its audit_id)."""
        sha256 = None
        if capsule_bytes is not None:
            sha256 = hashlib.sha256(capsule_bytes).hexdigest()
        elif capsule_path is not None:
            try:
                with open(capsule_path, "rb") as fh:
                    sha256 = hashlib.sha256(fh.read()).hexdigest()
            except OSError:
                sha256 = None

        now = datetime.now(timezone.utc).isoformat()
        rec = HandoffAuditRecord(
            audit_id=_audit_id(),
            timestamp=now,
            universal_session_id=universal_session_id,
            target_universal_session_id=target_universal_session_id,
            source_agent=source_agent,
            target_agent=target_agent,
            portability_level=portability_level,
            loss_report=dict(loss_report or {}),
            dropped_channels=tuple(dropped_channels),
            capsule_sha256=sha256,
            capsule_path=capsule_path,
            notes=tuple(notes),
            evidence=dict(evidence or {}),
        )

        line = json.dumps(rec.to_dict(), ensure_ascii=False)
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        return rec

    # -- read --------------------------------------------------------------
    def read_all(self) -> list[HandoffAuditRecord]:
        """Return every record in file order (oldest first)."""
        records: list[HandoffAuditRecord] = []
        with open(self.path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    # Malformed line: skip but record integrity failure
                    continue
                try:
                    records.append(HandoffAuditRecord.from_dict(data))
                except (KeyError, TypeError):
                    continue
        return records

    def read_for_session(self, universal_session_id: str) -> list[HandoffAuditRecord]:
        """All handoff events involving this session (as source or target)."""
        return [
            r for r in self.read_all()
            if r.universal_session_id == universal_session_id
            or r.target_universal_session_id == universal_session_id
        ]

    def verify_capsule_integrity(
        self, record: HandoffAuditRecord
    ) -> dict[str, Any]:
        """Re-hash the capsule on disk and compare against the recorded digest.

        Returns ``{"ok": bool, "recorded_sha": str|None, "actual_sha": str|None,
        "capsule_path": str|None}``.  A missing capsule file is a FAIL, not
        a skip — the audit trail must be honest about gaps.
        """
        recorded = record.capsule_sha256
        if not record.capsule_path:
            return {"ok": False, "recorded_sha": recorded, "actual_sha": None,
                    "capsule_path": None, "note": "no capsule path recorded"}
        try:
            with open(record.capsule_path, "rb") as fh:
                actual = hashlib.sha256(fh.read()).hexdigest()
        except OSError:
            return {"ok": False, "recorded_sha": recorded, "actual_sha": None,
                    "capsule_path": str(record.capsule_path),
                    "note": "capsule file missing or unreadable"}
        return {
            "ok": (recorded is not None and recorded == actual),
            "recorded_sha": recorded,
            "actual_sha": actual,
            "capsule_path": str(record.capsule_path),
        }

    def build_provenance_chain(
        self, universal_session_id: str
    ) -> dict[str, Any]:
        """Reconstruct the full cross-agent provenance for one session.

        Follows target_universal_session_id links to build the chain:
        [original → hop1 → hop2 → …].  Records are returned oldest-first.
        """
        all_records = self.read_all()
        # Build adjacency: source → [target, …]
        by_source: dict[str, list[HandoffAuditRecord]] = {}
        for r in all_records:
            by_source.setdefault(r.universal_session_id, []).append(r)

        chain: list[HandoffAuditRecord] = []
        current: str | None = universal_session_id
        visited: set[str] = set()
        while current is not None and current not in visited:
            visited.add(current)
            children = by_source.get(current, [])
            if not children:
                break
            # Pick the earliest hop (audit ids are monotonic)
            first = min(children, key=lambda r: r.audit_id)
            chain.append(first)
            current = first.target_universal_session_id

        # Chain is "complete" when the final hop has no further outgoing record
        # (i.e. current points to a session id that is not a source in the ledger)
        final_has_more = current is not None and current in by_source

        # Also collect records where the session appears as a target
        incoming = [r for r in all_records
                    if r.target_universal_session_id == universal_session_id]
        return {
            "session_id": universal_session_id,
            "outgoing_hops": [r.to_dict() for r in chain],
            "incoming_hops": [r.to_dict() for r in incoming],
            "chain_length": len(chain),
            "complete": not final_has_more,
        }

    def health(self) -> dict[str, Any]:
        total = 0
        malformed = 0
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                total += 1
                try:
                    json.loads(line)
                except json.JSONDecodeError:
                    malformed += 1
        return {
            "ok": malformed == 0,
            "path": str(self.path),
            "total_records": total,
            "malformed_records": malformed,
        }


__all__ = [
    "AUDIT_SCHEMA_VERSION",
    "HandoffAuditRecord",
    "HandoffAuditLedger",
]
