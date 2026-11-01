#!/usr/bin/env python
"""Render Codex guidance from the user's reviewed universal mother snapshot.

config/universal-agent/AGENT_CORE.md is a derived deployment artifact, never a
second mother. The external source is recorded in source.json. The legacy
YAML retains typed machine-control contracts and coverage classification only;
its old prose no longer regenerates the global guidance. --write updates the
repository projection; live configuration still requires the existing syncer.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "services" / "policy"))

import policy_projection as pp  # noqa: E402  (project-local module, see _REPO_ROOT insert)


def _section(title: str, bullets: list[str]) -> str:
    lines = [f"### {title}"]
    lines += [f"- {b}" for b in bullets]
    return "\n".join(lines)


class CodexPolicyRenderer(pp.SoftwarePolicyRenderer):
    """Project the neutral Global Agent Policy into the Codex native surface."""

    adapter = "codex"

    def classify(self, policy: dict, extension: dict) -> dict[str, str]:
        """Codex capability states come from the extension's honest seed."""
        return dict(extension.get("capability_states", {}))

    def render(self, policy: dict, extension: dict) -> dict[str, str]:
        """Render universal prose from the checksum-verified mother snapshot.

        Typed policy and extension config values remain compatibility contracts;
        this render does not deploy permission, sandbox, or model settings.
        """
        from universal_agent_core import render_core_block

        body = render_core_block(self.root) + "\n\n" + (
            "## Codex 专用补充\n\n"
            "- 项目事实与有效合同只在对应项目生效，不把某个项目的数据目录或阶段强制推广到其他项目。\n"
            "- 工作流模块按任务需要读取 C:/Users/ALEX/AgentRules/WORKFLOW_MODULES.md；不全部常驻加载。\n"
        )
        return {
            "global-guidance.md": body,
            "config.toml.managed_fields": json.dumps(
                extension.get("managed_config_values", {}), sort_keys=True
            ),
        }

    def golden_text(self, policy: dict, extension: dict) -> str:
        return self.render(policy, extension)["global-guidance.md"]


def build_renderer(root: Path) -> CodexPolicyRenderer:
    return CodexPolicyRenderer(root)


def write_golden(root: Path) -> dict:
    """Regenerate the golden global-guidance.md + persist the loss report."""
    renderer = build_renderer(root)
    result = renderer.project()
    extension = pp.load_extension(root, "codex")
    golden = result["assets"]["global-guidance.md"]
    golden_path = root / "integrations" / "executors" / "codex" / "global-guidance.md"
    golden_path.write_text(golden, encoding="utf-8")
    report_path = pp.write_loss_report(root, result["loss_report"])
    return {"golden": str(golden_path), "loss_report": str(report_path), "digest": pp.policy_digest(root)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=_REPO_ROOT)
    parser.add_argument("--write", action="store_true", help="regenerate the golden + persist the loss report")
    args = parser.parse_args()
    root = args.root

    renderer = build_renderer(root)
    result = renderer.project()  # fail-closed: validates the policy first

    if args.write:
        written = write_golden(root)
        print("CODEX_POLICY_WRITE golden=" + written["golden"])
        print("CODEX_POLICY_WRITE loss_report=" + written["loss_report"])
    else:
        print(result["assets"]["global-guidance.md"])
        print("--- loss report ---")
        print(json.dumps(result["loss_report"], ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
