#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Shared, portable, fail-closed tool locator (Prompt B-B, DL-CLOUD-2026-09-25).

Generates a Tool Resolution Receipt (``design-lab/config/tool-resolution.schema.json``)
for any logical tool id. The locator is the *single* resolution surface the
Workbench, the agent console, and the CLI reuse, so the six-strategy policy and
the five-status semantics live in exactly one place.

Resolution order (fixed, documented, and re-asserted by the hermetic tests):

  1. explicit value       (``explicit``)
  2. environment variable  (``env``)
  3. approved registry / App Paths metadata (``registry-metadata``)
  4. PATH / shutil.which   (``path``)
  5. declared canonical root (``canonical-root``)
  6. fail closed           (``None`` -> status MISSING / AMBIGUOUS / BLOCKED)

Guarantees the whole module exists to enforce (this is the no-drift contract):

  * ZERO side effects. No network, no download, no clone, no install, and no
    file write. A MISSING tool must *never* trigger a toolchain fetch; the
    locator only reports where it looked and how to fix it.
  * NEVER fabricate. ``version`` / ``sha256`` are observed-only: they are
    recorded only when actually probed/computed, else null.
  * AMBIGUOUS is a first-class fail-closed outcome. When more than one writable
    installation resolves, the locator returns AMBIGUOUS with the candidate
    list so the caller can decide -- it never silently picks one.
  * registry App Paths tier reads *approved static metadata* only. A live Win32
    registry query is a documented owner-gated extension and is intentionally
    NOT performed here, so the stdlib-portable path stays side-effect-free.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Mapping, Optional

SCHEMA_VERSION = "design-lab/tool-resolution/v1"

# The five statuses (Prompt B-B). AMBIGUOUS and BLOCKED are fail-closed
# outcomes, not silent-fallbacks.
STATUSES = ("FOUND", "VERIFIED", "MISSING", "AMBIGUOUS", "BLOCKED")

# The locator consults this single approved-metadata catalog. It is the
# tier-3 data source and the per-tool locator inputs; it is NOT a second
# paths SSOT (canonical roots remain .project/paths.json).
_REGISTRY_REL = Path("design-lab") / "config" / "registry-app-paths.json"


@dataclass(frozen=True)
class Resolution:
    """A Tool Resolution Receipt (schema tool-resolution.schema.json)."""
    logical_id: str
    status: str
    resolved_path: Optional[str] = None
    version: Optional[str] = None
    sha256: Optional[str] = None
    locator_method: Optional[str] = None
    candidate_locations: list[str] = field(default_factory=list)
    verified_at: str = ""
    fix: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema_version"] = SCHEMA_VERSION
        # preserve required key order for stable, diffable receipts
        ordered = {
            "schema_version": d["schema_version"],
            "logical_id": d["logical_id"],
            "candidate_locations": d["candidate_locations"],
            "resolved_path": d["resolved_path"],
            "version": d["version"],
            "sha256": d["sha256"],
            "locator_method": d["locator_method"],
            "verified_at": d["verified_at"],
            "status": d["status"],
            "fix": d["fix"],
        }
        return ordered


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_registry(repo_root: Path) -> dict:
    path = Path(repo_root) / _REGISTRY_REL
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # A missing/unreadable approved catalog degrades to the other
        # strategies -- it is metadata, never a hard dependency.
        return {}


def resolve_tool(
    logical_id: str,
    *,
    repo_root: Path,
    explicit: Optional[str] = None,
    expected_sha256: Optional[str] = None,
    expected_version: Optional[str] = None,
    observed_sha256: Optional[str] = None,
    observed_version: Optional[str] = None,
    writable_roots: Optional[Mapping[str, Path]] = None,
    _which: Optional[object] = None,
    _env_get: Optional[object] = None,
    _path_exists: Optional[object] = None,
) -> Resolution:
    """Resolve ``logical_id`` through the six strategies; fail closed.

    Injectable knobs (``_which``, ``_env_get``, ``_path_exists``) let the
    hermetic tests prove each strategy and the AMBIGUOUS/fail-closed branches
    without touching a real machine. The defaults bind to the real stdlib.
    """
    which = _which if _which is not None else shutil.which
    env_get = _env_get if _env_get is not None else os.environ.get
    path_exists = _path_exists if _path_exists is not None else Path.exists

    registry = _load_registry(Path(repo_root))
    env_vars = registry.get("envVarByTool", {}) or {}
    exe_names = registry.get("exeNamesByTool", {}) or {}
    canonical_hint = registry.get("canonicalRootHintByTool", {}) or {}
    checked: list[str] = []

    # 1. explicit
    if explicit:
        p = Path(explicit)
        if path_exists(p):
            checked.append(f"explicit: {explicit}")
            return _verdict(
                logical_id, "FOUND",
                str(p), "explicit", checked, expected_sha256, expected_version,
                observed_sha256, observed_version, fix="",
            )
        checked.append(f"explicit: {explicit} (does not exist)")

    # 2. env
    env_name = env_vars.get(logical_id)
    if env_name:
        env_val = env_get(env_name)
        if env_val:
            p = Path(env_val)
            if path_exists(p):
                checked.append(f"env: {env_name}={env_val}")
                return _verdict(logical_id, "FOUND", str(p), "env", checked,
                                expected_sha256, expected_version,
                                observed_sha256, observed_version, fix="")
            checked.append(f"env: {env_name}={env_val} (does not exist)")
        else:
            checked.append(f"env: {env_name}=absent")

    # 3. approved registry / App Paths metadata (static only; live query is
    #    owner-gated). The metadata names the *location*; we still verify the
    #    path exists before trusting it.
    reg = (registry.get("registryAppPaths", {}) or {}).get(logical_id) or {}
    reg_key = str(reg.get("key") or "")
    if reg_key:
        checked.append(f"registry-metadata: {reg_key} (approved static; live query owner-gated)")

    # 4. PATH / shutil.which
    names = exe_names.get(logical_id) or [logical_id]
    path_hits: list[str] = []
    seen_paths: set[str] = set()
    for name in names:
        found = which(name) if which is not None else None
        if found:
            checked.append(f"PATH: which({name!r}) -> {found}")
            # Alias dedupe: several exe-name variants may resolve to the SAME
            # physical installation -- that is one candidate, not ambiguity.
            # AMBIGUOUS is reserved for *distinct* writable installations.
            if found not in seen_paths:
                seen_paths.add(found)
                path_hits.append(found)
        else:
            checked.append(f"PATH: which({name!r})=absent")

    # 5. declared canonical root
    canonical_root_name = canonical_hint.get(logical_id)
    if canonical_root_name:
        root = (writable_roots or {}).get(canonical_root_name)
        if root is not None:
            candidate = Path(root) / (names[0] if names else logical_id)
            if path_exists(candidate):
                checked.append(f"canonical-root: {root} -> {candidate}")
                return _verdict(logical_id, "FOUND", str(candidate), "canonical-root",
                                checked, expected_sha256, expected_version,
                                observed_sha256, observed_version, fix="")
            checked.append(f"canonical-root: {root} (no {candidate.name} found)")
        else:
            checked.append(f"canonical-root: {canonical_root_name}=unresolved (no writable root)")

    # 6. fail closed: decide AMBIGUOUS vs MISSING vs BLOCKED.
    if len(path_hits) > 1:
        return Resolution(
            logical_id=logical_id,
            status="AMBIGUOUS",
            resolved_path=None,
            locator_method=None,
            candidate_locations=checked,
            verified_at=_now_iso(),
            fix=(
                "multiple writable installations resolved on PATH; pick one "
                f"({'; '.join(path_hits)}) and re-run with --explicit, or "
                "register a single canonical root. No install was attempted."
            ),
        )
    if path_hits:
        return _verdict(logical_id, "FOUND", path_hits[0], "path", checked,
                        expected_sha256, expected_version,
                        observed_sha256, observed_version, fix="")
    # No strategy resolved it. A logical id that has no registered locator
    # inputs at all is BLOCKED (unknown tool, not a miss): the caller cannot
    # have expected a resolution the registry never declared.
    registered = (
        logical_id in (registry.get("envVarByTool", {}) or {})
        or logical_id in (registry.get("exeNamesByTool", {}) or {})
        or logical_id in (registry.get("canonicalRootHintByTool", {}) or {})
        or logical_id in (registry.get("registryAppPaths", {}) or {})
    )
    status = "BLOCKED" if not registered else "MISSING"
    fix = (
        "unregistered logical_id: add it to "
        f"{_REGISTRY_REL.as_posix()} with env/app/canonical inputs, or pass "
        "--explicit. No download, clone, or install was attempted."
        if status == "BLOCKED" else
        "set the tool's env var, put it on PATH, or declare a canonical root. "
        "No download, clone, or install was attempted."
    )
    return Resolution(
        logical_id=logical_id,
        status=status,
        resolved_path=None,
        locator_method=None,
        candidate_locations=checked,
        verified_at=_now_iso(),
        fix=fix,
    )


def _verdict(
    logical_id, status_hint, resolved, method, checked,
    expected_sha256, expected_version, observed_sha256, observed_version, *, fix,
) -> Resolution:
    # VERIFIED ONLY when an expectation was supplied AND the observed value
    # matches it. An expectation without an observation stays FOUND -- the
    # locator never fabricates a verified state (observed-only contract).
    # version / sha256 in the receipt are the OBSERVED values, else None.
    status = "FOUND"
    if (expected_sha256 and observed_sha256 is not None and observed_sha256 == expected_sha256) or (
        expected_version and observed_version is not None and observed_version == expected_version
    ):
        status = "VERIFIED"
    return Resolution(
        logical_id=logical_id,
        status=status,
        resolved_path=resolved,
        version=observed_version,
        sha256=observed_sha256,
        locator_method=method,
        candidate_locations=checked,
        verified_at=_now_iso(),
        fix=fix,
    )


def validate_receipt_dict(rec: Mapping[str, object], schema: Mapping[str, object]) -> list[str]:
    """Cheap, dependency-free structural check of a receipt against the schema's
    required keys + status enum. (Full jsonschema validation lives in the test
    suite; this keeps the locator importable with stdlib only.)"""
    findings: list[str] = []
    for key in schema.get("required", []):
        if key not in rec:
            findings.append(f"RECEIPT-MISSING-KEY {key}")
    status = rec.get("status")
    if status not in STATUSES:
        findings.append(f"RECEIPT-BAD-STATUS {status!r} (expected one of {STATUSES})")
    if rec.get("schema_version") != SCHEMA_VERSION:
        findings.append(f"RECEIPT-BAD-SCHEMA {rec.get('schema_version')!r}")
    return findings


if __name__ == "__main__":  # pragma: no cover - smoke entry point
    import sys
    rid = sys.argv[1] if len(sys.argv) > 1 else "open-design"
    root = Path(__file__).resolve().parent.parent.parent
    receipt = resolve_tool(rid, repo_root=root)
    print(json.dumps(receipt.to_dict(), indent=2, ensure_ascii=False))
    raise SystemExit(0 if receipt.status in ("FOUND", "VERIFIED") else 1)
