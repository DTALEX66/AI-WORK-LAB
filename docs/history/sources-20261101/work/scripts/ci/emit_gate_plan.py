#!/usr/bin/env python3
"""Emit the canonical WORK-LAB gate plan for local or GitHub Actions use."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_SCRIPTS = ROOT / "packages" / "client-neutral-core" / "scripts"
sys.path.insert(0, str(WORKFLOW_SCRIPTS))
from impact_planner import build_plan, load_profile  # noqa: E402


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def read_changed_paths(path: Path | None, root: Path) -> list[str]:
    if path is not None:
        return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [line for line in git(root, "diff", "--name-only", "HEAD^", "HEAD").splitlines() if line]


def write_output(path: Path | None, key: str, value: str) -> None:
    if path is None:
        return
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"{key}<<WORK_LAB_GATE_PLAN\n{value}\nWORK_LAB_GATE_PLAN\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--profile", type=Path, default=ROOT / ".project/governance" / "work-lab.project-profile.yaml")
    parser.add_argument("--changed-path-file", type=Path)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit")
    parser.add_argument("--tree")
    parser.add_argument("--platform", action="append", dest="platform_scope")
    parser.add_argument("--generated-at")
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    changed_paths = read_changed_paths(args.changed_path_file, root)
    commit = args.commit or git(root, "rev-parse", "HEAD")
    tree = args.tree or git(root, "rev-parse", "HEAD^{tree}")
    generated_at = args.generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    profile = load_profile(args.profile.resolve())
    plan = build_plan(
        profile,
        repository=args.repository,
        commit=commit,
        tree=tree,
        changed_paths=changed_paths,
        platform_scope=args.platform_scope,
        plan_id="work-lab-gate",
        generated_at=generated_at,
    )
    compact = {
        "required_gates": plan["required_gates"],
        "plan_digest": plan["plan_digest"]["value"],
        "risk": plan["risk"],
    }
    print("GATE_PLAN_PASS " + json.dumps(compact, ensure_ascii=False, sort_keys=True))
    plan_json = json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    write_output(args.github_output, "required_gates", json.dumps(plan["required_gates"], separators=(",", ":")))
    write_output(args.github_output, "plan_digest", plan["plan_digest"]["value"])
    write_output(args.github_output, "risk", plan["risk"])
    write_output(args.github_output, "plan_json", plan_json)
    for gate in sorted(profile["gates"]):
        write_output(args.github_output, f"run_{gate.replace('-', '_')}", str(gate in plan["required_gates"]).lower())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
