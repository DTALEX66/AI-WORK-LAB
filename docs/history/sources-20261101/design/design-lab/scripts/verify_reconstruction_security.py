#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Aggregate adversarial reconstruction checks that must reject before render or host launch."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "design-lab"))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "capabilities"))
MANIFEST = PROJECT_ROOT / "design-lab" / "tests" / "fixtures" / "reconstruction" / "adversarial" / "manifest.json"


@dataclass(frozen=True)
class AttackResult:
    name: str
    phase: str


def run_attack(name: str) -> AttackResult:
    from reconstruction.adobe_readback import AuthorizationExpired, verify_launch_authorization
    from reconstruction.fusion import ReferenceOverlayError, SceneAnalysis, fuse_scene
    from reconstruction.matting import LayerProposal
    from reconstruction.svg_safety import UnsafeSVGError, sanitize_svg

    try:
        if name == "script-element.svg":
            sanitize_svg(b'<svg width="1" height="1" viewBox="0 0 1 1"><script /></svg>')
        elif name == "external-href.svg":
            sanitize_svg(b'<svg width="1" height="1" viewBox="0 0 1 1"><image href="https://example.test/x.png" x="0" y="0" width="1" height="1" /></svg>')
        elif name == "full-canvas-overlay.json":
            layer = LayerProposal(
                "reference", "reference-overlay", 0, (0, 0, 10, 10), (0, 0, 10, 10),
                PROJECT_ROOT / ".project-local" / "task-runtime" / "security" / "reference.png", False, 1.0,
            )
            fuse_scene(SceneAnalysis(10, 10, "flat"), (layer,), ())
        elif name == "stale-authorization.json":
            verify_launch_authorization(
                {"jobId": "adobe-test", "expiresAt": "2000-01-01T00:00:00Z", "approved": True},
                "adobe-test",
            )
        else:
            raise ValueError(f"unknown registered attack: {name}")
    except (UnsafeSVGError, ReferenceOverlayError, AuthorizationExpired):
        return AttackResult(name, "PRE_RENDER_REJECTED")
    return AttackResult(name, "FAILED_TO_REJECT")


def main() -> int:
    attacks = json.loads(MANIFEST.read_text(encoding="utf-8"))["attacks"]
    results = [run_attack(name) for name in attacks]
    failed = [item for item in results if item.phase != "PRE_RENDER_REJECTED"]
    print(f"RECONSTRUCTION_SECURITY={'PASS' if not failed else 'FAIL'} fixtures={len(results)}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
