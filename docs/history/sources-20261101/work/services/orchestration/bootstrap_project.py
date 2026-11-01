#!/usr/bin/env python
"""Install minimal, project-local Workflow-assistance governance into a Git repo."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


FILES = {
    ".hermes/README.md": """# Project-local Hermes runtime\n\nThis ignored directory contains only regenerable task runtime data, caches, logs and verification artifacts. Run project-writing commands through `hermes-project-data.py --project . run -- <command>`.\n""",
    ".hermes/BOOTSTRAP_MANIFEST.yaml": """schema_version: 1\nsource: Workflow-assistance\nfeatures:\n  - project_data_boundary\n  - context_pack\n  - local_quality_gate\ncredentials: not_copied\n""",
}
AGENT_RULES_TEMPLATE = Path(__file__).resolve().parents[2] / "packages" / "client-neutral-core" / "templates" / "agent-rules" / "AGENTS.md"


def git_root(target: Path) -> Path:
    result = subprocess.run(["git", "-C", str(target), "rev-parse", "--show-toplevel"], text=True, encoding="utf-8", errors="replace", capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(f"target is not inside a Git repository: {target}")
    return Path(result.stdout.strip()).resolve()


def ignored(root: Path) -> bool:
    result = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", "--no-index", ".hermes/.probe"], check=False)
    return result.returncode == 0


def files_for(root: Path, *, include_agent_rules: bool) -> dict[str, str]:
    """Return only files this bootstrap owns and may create safely."""
    files = {relative: content for relative, content in FILES.items() if not (root / relative).exists()}
    if include_agent_rules and not (root / "AGENTS.md").exists():
        files["AGENTS.md"] = AGENT_RULES_TEMPLATE.read_text(encoding="utf-8")
    return files


def plan(root: Path, *, include_agent_rules: bool = False) -> list[Path]:
    if not ignored(root):
        raise RuntimeError("target must ignore .hermes/ before bootstrap; add '.hermes/' to .gitignore")
    return [root / relative for relative in files_for(root, include_agent_rules=include_agent_rules)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap project-local Hermes workflow state without credentials.")
    parser.add_argument("project", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--agent-rules",
        action="store_true",
        help="also create the portable AGENTS.md template when the target has no AGENTS.md",
    )
    args = parser.parse_args(argv)
    root = git_root(args.project)
    files = files_for(root, include_agent_rules=args.agent_rules)
    outputs = plan(root, include_agent_rules=args.agent_rules)
    if args.dry_run:
        print("BOOTSTRAP_DRY_RUN project=" + str(root))
        for output in outputs:
            print("would_write=" + output.relative_to(root).as_posix())
        return 0
    for relative, content in files.items():
        output = root / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            with output.open("x", encoding="utf-8") as handle:
                handle.write(content)
        except FileExistsError:
            print("BOOTSTRAP_SKIPPED_EXISTING=" + output.relative_to(root).as_posix())
        else:
            print("BOOTSTRAP_WRITTEN=" + output.relative_to(root).as_posix())
    print("BOOTSTRAP_PASS project=" + str(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
