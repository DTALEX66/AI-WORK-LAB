#!/usr/bin/env python
"""Render Hermes persona plus the reviewed universal mother snapshot.

The external mother is recorded in config/universal-agent/source.json. The
native extension owns only Hermes persona/supplements. Legacy typed policy
still validates machine contracts; its obsolete prose is not rendered. Live
SOUL publication stays with sync_hermes_workflow_assets.py and its guards.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "services" / "policy"))

import policy_projection as pp  # noqa: E402  (project-local module)


class HermesPolicyRenderer(pp.SoftwarePolicyRenderer):
    """Project the neutral Global Agent Policy into the Hermes managed SOUL."""

    adapter = "hermes"

    def classify(self, policy: dict, extension: dict) -> dict[str, str]:
        """Hermes capability states come from the extension's honest seed."""
        return dict(extension.get("capability_states", {}))

    def render(self, policy: dict, extension: dict) -> dict[str, str]:
        """Preserve native persona and render the reviewed universal mother."""
        from universal_agent_core import render_core_block

        header = (extension.get("soul_header") or "").strip()
        bullets = extension.get("soul_sections", {}).get("hermes_supplement", [])
        body = (
            header + "\n\n" + render_core_block(self.root)
            + "\n\n## Hermes 专用补充\n\n"
            + "\n".join(f"- {line}" for line in bullets) + "\n"
        )
        return {"config/SOUL.md": body}

    def golden_text(self, policy: dict, extension: dict) -> str:
        return self.render(policy, extension)["config/SOUL.md"]


def build_renderer(root: Path) -> HermesPolicyRenderer:
    return HermesPolicyRenderer(root)


def write_soul(root: Path) -> dict:
    """Regenerate the managed config/SOUL.md + persist the Hermes loss report."""
    renderer = build_renderer(root)
    result = renderer.project()  # fail-closed: validates the policy first
    body = result["assets"]["config/SOUL.md"]
    soul_path = root / "config" / "SOUL.md"
    soul_path.write_text(body, encoding="utf-8")
    report_path = pp.write_loss_report(root, result["loss_report"])
    return {"soul": str(soul_path), "loss_report": str(report_path), "digest": pp.policy_digest(root)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=_REPO_ROOT)
    parser.add_argument("--write", action="store_true", help="regenerate config/SOUL.md + persist the loss report")
    args = parser.parse_args()

    renderer = build_renderer(args.root)
    result = renderer.project()

    if args.write:
        written = write_soul(args.root)
        print("HERMES_POLICY_WRITE soul=" + written["soul"])
        print("HERMES_POLICY_WRITE loss_report=" + written["loss_report"])
    else:
        print(result["assets"]["config/SOUL.md"])
        print("--- loss report ---")
        print(json.dumps(result["loss_report"], ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
