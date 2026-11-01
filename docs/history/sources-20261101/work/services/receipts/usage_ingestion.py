"""Cross-agent usage ingestion adapter pack (NX-310).

Reads agent-local public usage/log/structured output through read-only,
incremental, budgeted ingestion and normalizes into versioned observer events.
Never reads Prompt/Response bodies, credentials, or token-refresh code.

Data flow:
    Agent local usage -> read-only probe + incremental read
    -> workflow producer (clean/dedup/sanitize/normalize)
    -> versioned event -> Observer store/projection/UI (strictly read-only).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# Field allowlists for each agent reader. Only these are emitted.
ALLOWLIST_FIELDS = (
    "provider", "model", "operation", "inputTokens", "outputTokens",
    "cacheReadTokens", "cacheWriteTokens", "latencyMs", "outcome", "errorClass",
    "taskDigest", "sourceDigest", "runId", "taskId", "projectId",
)

# Fields that must NEVER be read or emitted (message bodies, secrets, etc.).
PRIVACY_BLOCKED = re.compile(
    r"(?i)(prompt|response|message|session|cookie|authorization|password|secret|"
    r"api[_-]?key|bearer|token\b(?!.*tokens?$)|\.env|\.pem|\.key)",
)

# Agent coverage matrix: which agents have an official/local public usage source.
AGENT_COVERAGE: dict[str, dict[str, Any]] = {
    "hermes": {"source": "local-usage-json", "status": "supported", "coverage": "full"},
    "codex": {"source": "local-usage-json", "status": "supported", "coverage": "full"},
    "claude-code": {"source": "local-usage-json", "status": "supported", "coverage": "partial"},
    "cursor": {"source": "unsupported-no-official-source", "status": "unknown", "coverage": "unknown"},
    "workbuddy": {"source": "unsupported-no-official-source", "status": "unknown", "coverage": "unknown"},
    "kimi": {"source": "historical-usage-only", "status": "retired", "coverage": "none", "lifecycle": "RETIRED", "note": "Kimi retired from active routing (2026-08-15); historical usage remains identifiable but no new task resolves to it."},
    "qwen": {"source": "unsupported-no-official-source", "status": "unknown", "coverage": "unknown"},
}


@dataclass
class IngestionConfig:
    """Read-only, budgeted ingestion settings."""

    max_file_size_bytes: int = 5 * 1024 * 1024  # 5 MB budget
    max_lines: int = 100_000
    allowlist: tuple[str, ...] = ALLOWLIST_FIELDS
    max_read_offset: int = 0  # 0 = read from cursor (incremental)


def _is_blocked(key: str) -> bool:
    """Blocked if the field key carries prompt/response/secret/session semantics."""
    return bool(PRIVACY_BLOCKED.search(key))


def _sanitize_record(raw: dict[str, Any]) -> dict[str, Any]:
    """Keep only allowlisted, non-blocked fields; drop the rest."""
    out: dict[str, Any] = {}
    for key, value in raw.items():
        if key not in ALLOWLIST_FIELDS:
            continue
        if _is_blocked(key):
            continue
        out[key] = value
    return out


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:16]


def _resolved_path(path: Path) -> Path:
    """The real location behind `path`, links followed. A seam the containment tests convict through."""
    return Path(os.path.realpath(path))


def _is_link(path: Path) -> bool:
    """True for a symlink AND for the Windows junction/mount point `is_symlink()` does not report.

    Measured here (CPython 3.11, NTFS): a directory junction answers `is_symlink() == False` while
    `st_file_attributes` carries the reparse bit. That is why containment of the resolved target, not this
    predicate alone, is what convicts a link sitting above the file the adapter was handed.
    """
    if path.is_symlink():
        return True
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if not reparse:
        return False
    try:
        info = path.lstat()
    except OSError:
        return False
    return bool(getattr(info, "st_file_attributes", 0) & reparse)


class UsagePathRefused(ValueError):
    """A usage path this reader would not open, named by the rule that refused it.

    A ValueError subclass, because every caller already treats a refused source as a ValueError; the reason
    key travels with it so the refusal stays attributable instead of becoming a generic "cannot read".
    """

    def __init__(self, reason: str, detail: str) -> None:
        self.reason = reason
        super().__init__(f"{reason}: {detail}")


class UsageReader:
    """Read-only incremental reader for a single agent's public usage file."""

    def __init__(
        self,
        agent_id: str,
        path: Path,
        config: IngestionConfig | None = None,
        *,
        root: Path | None = None,
    ) -> None:
        if agent_id not in AGENT_COVERAGE:
            raise ValueError(f"unknown agent id: {agent_id}")
        self.agent_id = agent_id
        # The declared path is kept as handed in: containment is only measurable against what the caller
        # asked for. Once it is resolved first, a link's target IS the "declared" location and every escape
        # reads as compliant.
        self.declared_path = Path(path)
        self.path = Path(os.path.realpath(path))
        self.root = root
        self.config = config or IngestionConfig()
        self.refusals: dict[str, int] = {}
        self.resolved_path: Path | None = None
        coverage = AGENT_COVERAGE[agent_id]
        if coverage["status"] == "unknown":
            raise ValueError(f"agent {agent_id} has no official public usage source (unsupported/unknown)")

    def _refuse(self, reason: str, detail: str) -> UsagePathRefused:
        """Count the refusal under its reason key, then hand back the exception to raise.

        Raised-only refusals are invisible to a caller that catches the error, and both shipped callers (the
        NX-310 verifier and the worker) do catch; the count is what keeps the refusal attributable.
        """
        self.refusals[reason] = self.refusals.get(reason, 0) + 1
        return UsagePathRefused(reason, detail)

    def _containment_root(self) -> Path:
        """The tree the declared path must stay inside (the "immediate parent tree" the old comment named).

        An anchor that is itself a link cannot be its own boundary -- its target would trivially contain
        everything under it -- so the default walks up past links to the first ancestor that is not one.
        That default is honestly limited: a link planted further up, with ordinary directories beneath it,
        moves the anchor along with it and reads as compliant. A caller that means a hard boundary declares
        it with ``root=`` -- and against a declared root, an ancestor link is convicted by containment,
        because the root itself never resolves into the link.
        """
        if self.root is not None:
            return _resolved_path(Path(self.root))
        anchor = self.declared_path.parent
        while anchor.parent != anchor and _is_link(anchor):
            anchor = anchor.parent
        return _resolved_path(anchor)

    def _resolve(self) -> Path:
        """Resolve the declared path and refuse it if it escapes its containment root.

        This is the body the docstring promised and the code never had: `self.path` was already resolved in
        ``__init__``, so re-resolving it here proved nothing. The link checks and the containment compare run
        again at read time, against the declared path, because that is the only moment the promise can be
        kept.
        """
        declared = self.declared_path
        if not declared.exists():
            raise FileNotFoundError(f"usage file missing: {declared}")
        if _is_link(declared):
            raise self._refuse("symlink_candidate_refused", "the usage file itself is a link")
        try:
            resolved = _resolved_path(declared)
            root = self._containment_root()
        except (OSError, RuntimeError) as exc:
            raise self._refuse("path_unresolvable", type(exc).__name__) from exc
        if not resolved.is_relative_to(root):
            raise self._refuse("symlink_outside_root", "resolved target escapes the containment root")
        # The origin is recorded, not laundered: `resolved_path` is where the bytes live, which is the
        # answer to "did we read through a link that stayed inside the root".
        self.resolved_path = resolved
        return resolved

    def _stays_inside(self) -> bool:
        """Re-measure containment immediately before the bytes are taken.

        Windows has no `O_NOFOLLOW` and no stdlib fd-to-final-path call, so this narrows the check-vs-read
        window rather than closing it: a link repointed after this call and before the read is undetectable
        with stdlib. The fd identity compare in `read_incremental` covers a swap that lands before the open,
        which is the larger half of the window.
        """
        return _resolved_path(self.declared_path).is_relative_to(self._containment_root())

    def read_incremental(self, cursor: int = 0) -> tuple[list[dict[str, Any]], int]:
        """Read records after `cursor`; return (events, new_cursor).

        Budgets file size and line count; isolates malformed lines (skips + notes).
        """
        path = self._resolve()
        try:
            checked = os.stat(path)
        except OSError as exc:
            raise self._refuse("file_unreadable", type(exc).__name__) from exc
        try:
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        except OSError as exc:
            raise self._refuse("file_unreadable", type(exc).__name__) from exc
        events: list[dict[str, Any]] = []
        malformed = 0
        new_cursor = cursor
        try:
            opened = os.fstat(fd)
            if (checked.st_dev, checked.st_ino) != (opened.st_dev, opened.st_ino):
                raise self._refuse("file_identity_moved_before_read", "the fd is not the checked file")
            if not self._stays_inside():
                raise self._refuse("symlink_outside_root", "escape seen at read time")
            # The budget is measured on the opened fd, so the size that was checked is the size that is read.
            if opened.st_size > self.config.max_file_size_bytes:
                raise ValueError(f"usage file exceeds size budget: {self.path}")
            with os.fdopen(fd, "r", encoding="utf-8", errors="replace", closefd=False) as handle:
                for line_number, line in enumerate(handle, start=1):
                    if line_number <= cursor:
                        continue
                    if line_number - cursor > self.config.max_lines:
                        break
                    if not line.strip():
                        continue
                    try:
                        raw = json.loads(line)
                    except json.JSONDecodeError:
                        malformed += 1
                        continue
                    if not isinstance(raw, dict):
                        malformed += 1
                        continue
                    record = _sanitize_record(raw)
                    if not record:
                        malformed += 1
                        continue
                    record["agentId"] = self.agent_id
                    record["sourceDigest"] = _digest(line)
                    record["observedAt"] = datetime.now(timezone.utc).isoformat()
                    events.append(record)
                    new_cursor = line_number
        finally:
            os.close(fd)
        if malformed:
            events.append({
                "agentId": self.agent_id, "malformedLines": malformed,
                "coverage": "partial", "observedAt": datetime.now(timezone.utc).isoformat(),
            })
        return events, new_cursor

    def probe(self) -> dict[str, Any]:
        """Read-only capability/coverage probe (no writes, no auth)."""
        coverage = AGENT_COVERAGE[self.agent_id]
        exists = self.path.exists() and self.path.stat().st_size > 0
        return {
            "agentId": self.agent_id, "status": "supported" if exists else "no-data",
            "coverage": coverage["coverage"] if exists else "unknown",
            "source": coverage["source"], "path": str(self.path),
        }


def coverage_matrix() -> dict[str, dict[str, Any]]:
    return AGENT_COVERAGE


def normalize_event(record: dict[str, Any]) -> dict[str, Any]:
    """Produce a versioned observer event from a sanitized usage record."""
    return {
        "schemaVersion": "work-lab/observer-event/v2",
        "eventType": "agent-usage",
        "agentId": record.get("agentId", "unknown"),
        "usage": {
            "provider": record.get("provider"),
            "model": record.get("model"),
            "operation": record.get("operation"),
            "inputTokens": record.get("inputTokens"),
            "outputTokens": record.get("outputTokens"),
            "cacheReadTokens": record.get("cacheReadTokens"),
            "cacheWriteTokens": record.get("cacheWriteTokens"),
            "latencyMs": record.get("latencyMs"),
            "outcome": record.get("outcome"),
            "errorClass": record.get("errorClass"),
            "taskDigest": record.get("taskDigest"),
        },
        "coverage": {"state": "full" if "malformedLines" not in record else "partial"},
        "observedAt": record.get("observedAt"),
        "privacy": {"messageBodies": False, "credentials": False, "session": False},
    }
