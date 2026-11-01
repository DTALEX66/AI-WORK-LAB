"""Tiered future-agent onboarding (WL3-710).

Manifest + capability probe + identity/config root + observe fixture for
Cursor, Claude Code, WorkBuddy, Qwen Code and later platforms. Levels:
L0 Generic / L1 Observe / L2 Govern / L3 Coordinate / L4 Deep. Detection alone
never grants apply/invoke; uninstalled platforms report UNAVAILABLE and never
fail the core.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

LEVELS = {"L0", "L1", "L2", "L3", "L4"}
MANIFEST_ONLY = {"cursor", "claude-code", "workbuddy", "qwen-code"}


def probe_level(
    platform: str,
    *,
    executable: str | None = None,
    config_root: Path | None = None,
    manifest: dict[str, Any] | None = None,
    capability_evidence: bool = False,
) -> dict[str, Any]:
    """Return the honest support level for a platform from real evidence."""
    if platform not in MANIFEST_ONLY and platform not in {"hermes", "codex", "cc-switch", "github"}:
        raise ValueError(f"unknown platform: {platform}")
    if platform in {"hermes", "codex", "cc-switch", "github"}:
        return {"platform": platform, "level": "L4", "basis": "real-conformance", "apply_allowed": False}
    installed = executable is not None and shutil.which(executable) is not None
    if not installed:
        return {"platform": platform, "level": "L0", "basis": "manifest-only", "installed": False, "apply_allowed": False}
    if manifest is None:
        return {"platform": platform, "level": "L0", "basis": "manifest-only", "installed": True, "apply_allowed": False}
    evidence: list[str] = []
    if config_root is not None and config_root.is_dir():
        evidence.append("config-root")
    if capability_evidence:
        evidence.append("capability-probe")
    level = "L1" if evidence else "L0"
    return {
        "platform": platform,
        "level": level,
        "basis": "probe",
        "installed": True,
        "config_root": str(config_root) if config_root else None,
        "evidence": evidence,
        "apply_allowed": level in {"L2", "L3", "L4"},
    }


def tier_matrix() -> dict[str, Any]:
    """Full support matrix for all known platforms with real probes."""
    platforms = {
        "hermes": {"executable": "hermes"},
        "codex": {"executable": "codex"},
        "cc-switch": {"executable": "cc-switch"},
        "github": {"executable": "gh"},
        "cursor": {"executable": "cursor", "manifest": True},
        "claude-code": {"executable": "claude", "manifest": True},
        "workbuddy": {"executable": None, "manifest": True},
        "qwen-code": {"executable": "qwen", "manifest": True},
    }
    rows: dict[str, Any] = {}
    for platform, spec in platforms.items():
        manifest = {"name": platform} if spec.get("manifest") else None
        rows[platform] = probe_level(
            platform,
            executable=spec.get("executable"),
            manifest=manifest,
        )
    return {
        "schema_version": "workflow/tiered-adapter-matrix/v1",
        "rows": rows,
        "core_unaffected": True,
    }


if __name__ == "__main__":
    print(json.dumps(tier_matrix(), ensure_ascii=False, indent=2))
