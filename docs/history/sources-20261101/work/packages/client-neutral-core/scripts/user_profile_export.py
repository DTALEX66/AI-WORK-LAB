#!/usr/bin/env python3
"""Build the portable, field-allowlisted WORK-LAB user overlay.

The exporter never inventories user homes, Skills, environment variables,
provider/model routing, sessions, memory, caches, logs, MCP state, Desktop
internals, or absolute paths. It is plan-only unless ``--write`` is explicit.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _nested(data: dict[str, Any], dotted: str, default: Any) -> Any:
    current: Any = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def build_profile(
    *,
    hermes_preferences: dict[str, Any] | None = None,
    codex_preferences: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return only MANAGE-allowlisted portable preferences."""

    hermes_preferences = hermes_preferences or {}
    codex_preferences = codex_preferences or {}
    return {
        "authority": "config/config-ownership.json",
        "codex": {
            "guidance": {
                "managed_authority": "codex-assets/AGENTS.md",
                "unmanaged": "PRESERVE",
            },
            "plugins": "OBSERVE_PRESERVE",
            "preferences": {
                "approval_policy": codex_preferences.get("approval_policy", "on-request"),
                "project_doc_max_bytes": codex_preferences.get("project_doc_max_bytes", 65536),
                "sandbox_mode": codex_preferences.get("sandbox_mode", "workspace-write"),
            },
            "rules": {
                "managed_authority": "codex-assets/rules/workflow-assistance.rules",
                "unmanaged": "PRESERVE",
            },
            "skills": {
                "managed_authority": "config/skill-provenance.yaml",
                "unmanaged": "PRESERVE",
            },
        },
        "discovery": {
            "absolute_paths_persisted": False,
            "runtime_roots": "CAPABILITY_DISCOVERY",
        },
        "excluded": [
            "models/providers/base_urls",
            "credentials/env/auth",
            "sessions/memory/cache/logs",
            "MCP/Desktop/platform-internal-state",
            "absolute-paths",
        ],
        "hermes": {
            "plugins": "OBSERVE_PRESERVE",
            "preferences": {
                "display.busy_input_mode": _nested(
                    hermes_preferences, "display.busy_input_mode", "queue"
                ),
                "display.language": _nested(
                    hermes_preferences, "display.language", "zh"
                ),
            },
            "skills": {
                "managed_authority": "config/skill-provenance.yaml",
                "unmanaged": "PRESERVE",
            },
        },
        "profile_mode": "USER_OVERLAY_ONLY",
        "schema_version": "worklab/user-environment-profile/v2",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[3] / "config/user-environment-profile.json",
    )
    parser.add_argument("--write", action="store_true", help="write the reviewed portable overlay")
    args = parser.parse_args(argv)

    profile = build_profile()
    payload = json.dumps(profile, ensure_ascii=False, indent=2) + "\n"
    if not args.write:
        print(payload, end="")
        print(f"USER_ENVIRONMENT_PROFILE_PLAN_ONLY path={args.output}")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload, encoding="utf-8")
    print(f"USER_ENVIRONMENT_PROFILE_WRITTEN path={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
