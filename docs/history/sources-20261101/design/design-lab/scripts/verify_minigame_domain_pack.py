#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify the MINIGAME domain-pack source-of-truth boundary."""

from __future__ import annotations

import json
from pathlib import Path
import sys

REQUIRED_MANIFEST_KEYS = {
    "schema_version",
    "pack_id",
    "version",
    "capabilities",
    "entrypoints",
    "evidence_policy",
    "safety",
    "excluded_capabilities",
}
REQUIRED_ARTIFACTS = {"brief", "profile", "visual-qa-report", "handoff", "runtime-smoke"}


def main() -> int:
    root = Path(__file__).resolve()
    while root != root.parent and not (root / "design-lab" / "domain-packs" / "minigame-design").is_dir():
        root = root.parent
    pack = root / "design-lab" / "domain-packs" / "minigame-design"
    manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    errors: list[str] = []

    errors.extend(f"manifest missing key: {key}" for key in REQUIRED_MANIFEST_KEYS - manifest.keys())
    if manifest.get("schema_version") != "workflow/domain-pack/v1":
        errors.append("manifest schema version mismatch")
    if manifest.get("pack_id") != "minigame-design":
        errors.append("manifest pack_id mismatch")
    policy = manifest.get("evidence_policy", {})
    if policy.get("minimum_level") != "E2":
        errors.append("minimum evidence must remain E2")
    errors.extend(f"required artifact missing: {item}" for item in REQUIRED_ARTIFACTS - set(policy.get("required_artifacts", [])))
    if manifest.get("safety", {}).get("approval_required") is not True:
        errors.append("approval_required must remain true")
    if "platform-release" not in manifest.get("excluded_capabilities", []):
        errors.append("platform-release must remain excluded")

    for name in ("README.md", "rules.md", "qa.md", "handoff.md", "SOURCE_OF_TRUTH.md"):
        if not (pack / name).is_file():
            errors.append(f"missing boundary document: {name}")
    if not (root / "fixtures" / "domains" / "game-visual").is_dir():
        errors.append("repository runtime fixture is missing")
    source_doc = (pack / "SOURCE_OF_TRUTH.md").read_text(encoding="utf-8")
    if "treated as a second live source" not in source_doc:
        errors.append("external historical source boundary is not explicit")

    if errors:
        for error in errors:
            print(f"MINIGAME_DOMAIN_PACK_ERROR={error}")
        return 1
    print("MINIGAME_DOMAIN_PACK_BOUNDARY_PASS contract=manifest fixture=game-visual evidence=E2")
    return 0


if __name__ == "__main__":
    sys.exit(main())
