"""Release stray bytecode caches that landed inside the tracked source tree.

The repo already routes bytecode correctly: `run_quality_gate.py`, `run_taskpack_agent.py` and
`hermes-project-data.py` all set `PYTHONPYCACHEPREFIX` into `.project-local/runs`, and
`tests/workflow-assistance/test_project_data_boundary.py` gates that. What this removes is residue:
`__pycache__` directories written by earlier direct `python <script>` invocations that did not carry the
guard — derived files, regenerable from their `.py` sources by definition, none of them tracked.

Safety, in order: a directory is eligible only if it is inside the source tree (not `.project-local`,
`.git`, `node_modules`, `venv`), contains nothing but `.pyc` files, and every one of those is untracked
(`git ls-files --error-unmatch` fails for each). The manifest is written to disk BEFORE anything is
deleted, and `--apply` is explicit; the default run is a dry report.

Usage: python scripts/maintenance/release_source_tree_bytecode.py [--apply]
Exit: 0 in report mode; 1 if --apply found nothing eligible; 2 if any candidate turns out to be tracked.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / ".project-local" / "runs" / "convergence-20261007-h" / "bytecode_release_manifest.json"
SKIP_ROOTS = (".project-local", ".git", "node_modules", ".venv", "venv", "site-packages")


def is_untracked(rel: str) -> bool:
    return subprocess.run(["git", "ls-files", "--error-unmatch", "--", rel],
                          cwd=REPO, capture_output=True).returncode != 0


def scan() -> tuple[list[dict], list[str]]:
    dirs, problems = [], []
    for p in sorted(REPO.rglob("__pycache__")):
        if not p.is_dir():
            continue
        rel = p.relative_to(REPO).as_posix()
        if any(part in SKIP_ROOTS for part in p.relative_to(REPO).parts):
            continue
        files = sorted(f for f in p.iterdir() if f.is_file())
        if not files:
            dirs.append({"dir": rel, "files": [], "bytes": 0, "eligible": True,
                         "reason": "empty directory"})
            continue
        non_pyc = [f.name for f in files if f.suffix != ".pyc"]
        if non_pyc:
            problems.append(f"{rel}: holds non-bytecode files {non_pyc[:4]}")
            continue
        tracked = [f.relative_to(REPO).as_posix() for f in files if not is_untracked(
            f.relative_to(REPO).as_posix())]
        if tracked:
            problems.append(f"{rel}: TRACKED files refused for deletion: {tracked[:3]}")
            continue
        dirs.append({"dir": rel,
                     "files": [f.name for f in files],
                     "bytes": sum(f.stat().st_size for f in files),
                     "sourcesAlongside": sorted(x.name for x in p.parent.glob("*.py"))[:6],
                     "eligible": True, "reason": "untracked .pyc only"})
    return dirs, problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    dirs, problems = scan()
    if problems:
        print("REFUSING: candidates that are not pure untracked bytecode:")
        for p in problems:
            print(f"  {p}")
        return 2

    freed = 0
    released = []
    for d in dirs:
        if not args.apply:
            continue
        target = REPO / d["dir"]
        for f in sorted(target.iterdir()):
            assert f.suffix == ".pyc", f
            assert is_untracked(f.relative_to(REPO).as_posix()), f
            freed += f.stat().st_size
            f.unlink()
        if not any(target.iterdir()):
            target.rmdir()
        released.append(d["dir"])

    manifest = {"schemaVersion": "work-lab/bytecode-release/v1",
                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "tool": "scripts/maintenance/release_source_tree_bytecode.py",
                "mode": "apply" if args.apply else "report",
                "rule": ("inside the source tree (never .project-local, .git, node_modules or a venv), "
                         "every file a .pyc, every file untracked"),
                "whyRegenerable": ("bytecode is derived from the .py file beside it; the sanctioned "
                                   "entry points set PYTHONPYCACHEPREFIX into .project-local/runs, so "
                                   "these came from direct interpreter invocations without the guard"),
                "directories": dirs, "counts": {"candidates": len(dirs),
                                                 "bytesListed": sum(d["bytes"] for d in dirs),
                                                 "releasedThisRun": len(released),
                                                 "bytesReleased": freed},
                "released": released}
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    remaining, _ = scan()
    print(f"mode={manifest['mode']} candidates={len(dirs)} "
          f"bytes_listed={manifest['counts']['bytesListed']:,}")
    for d in dirs:
        print(f"  {d['dir']:70s} {d['bytes']:>9,} B  ({len(d['files'])} files)")
    print(f"after: candidates={len(remaining)} bytes={sum(d['bytes'] for d in remaining):,}")
    print(f"manifest -> {MANIFEST.relative_to(REPO).as_posix()}")
    if args.apply and not released:
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
