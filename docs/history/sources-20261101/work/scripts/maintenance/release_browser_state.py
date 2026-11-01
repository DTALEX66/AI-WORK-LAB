"""Release provably regenerable browser user-data from the retained evidence trees.

The four probe trees and the UI suite were kept in the last greening rounds because tracked
documents cite files inside them. Most of their bytes are not evidence: WebView2 and Chrome
write user-data directories (profiles, caches, Crashpad, SmartScreen) that the next launch
rebuilds. This script releases only those, under three guards:

1. the directory must look like a browser user-data root (or a pycache),
2. no path cited verbatim by a tracked file may live inside the directory,
3. after deletion, every tracked-referenced path of the parent tree is re-checked.

`--apply` is required; without it nothing is removed and the manifest is printed as a plan.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLAN = Path(__file__).resolve().parent / "release_plan.json"

BROWSER_NAME = re.compile(r"^(EBWebView[-_A-Za-z0-9]*|chrome-profile[-_A-Za-z0-9]*|"
                          r"Crashpad|SmartScreen|GPUCache|Code Cache|GrShaderCache|"
                          r"ShaderCache|WebCache|blob_storage)$", re.I)
MARKERS = ("Local State", "Default", "Code Cache", "Crashpad", "DevToolsActivePort",
           "lockfile", "session_store.json")


def walk_bytes(path: Path) -> tuple[int, int]:
    files = 0
    total = 0
    for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
        base = Path(dirpath)
        dirnames[:] = [d for d in dirnames if not (base / d).is_symlink()]
        for name in filenames:
            entry = base / name
            try:
                if entry.is_file() and not entry.is_symlink():
                    files += 1
                    total += entry.stat().st_size
            except OSError:
                continue
    return files, total


def tracked_corpus() -> str:
    listing = subprocess.run(["git", "ls-files", "*.md", "*.json", "*.yml", "*.py"],
                             cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8").stdout.splitlines()
    chunks = []
    for rel in listing:
        if any(part in rel for part in ("node_modules", "package-lock", ".project-local")):
            continue
        path = ROOT / rel
        try:
            if path.is_file() and path.stat().st_size < 4_000_000:
                chunks.append(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return "\n".join(chunks)


def looks_like_browser_state(path: Path) -> bool:
    if not path.is_dir():
        return False
    if path.name.lower().startswith(("ebwebview", "chrome-profile")):
        return True
    names = {child.name for child in path.iterdir()} if path.exists() else set()
    return len(names.intersection(MARKERS)) >= 2


def onerror(action, path, error):  # noqa: ANN001, ANN401 - shutil's legacy error hook
    target = Path(path)
    try:
        os.chmod(target, 0o700)
        action(path)
    except OSError:
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="actually delete; without this the plan is printed only")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    corpus = tracked_corpus()
    bases = [ROOT / ".project-local" / "runs", ROOT / ".project-local" / "artifacts"]

    plan, skipped = [], []
    cited_paths = sorted({m for m in re.findall(
        r"\.project-local/(?:runs|artifacts)/[^\s`\"'<>()\]\}\\|]+", corpus)})
    for base in bases:
        if not base.is_dir():
            continue
        for top in sorted(p for p in base.iterdir() if p.is_dir()):
            matches = [p for p in top.rglob("*")
                       if p.is_dir() and BROWSER_NAME.match(p.name)]
            outermost = [p for p in matches
                         if not any(other != p and other in p.parents for other in matches)]
            for candidate in sorted(outermost):
                rel = candidate.relative_to(ROOT).as_posix()
                files, total = walk_bytes(candidate)
                inside = [c for c in cited_paths if c.startswith(rel + "/")]
                if not looks_like_browser_state(candidate):
                    skipped.append({"path": rel, "reason": "does not look like browser state"})
                    continue
                plan.append({"path": rel, "files": files, "bytes": total,
                             "cited_references_inside": inside})

    plan.sort(key=lambda item: -item["bytes"])
    cited_blocking = [item for item in plan if item["cited_references_inside"]]
    releasable = [item for item in plan if not item["cited_references_inside"]]
    total_bytes = sum(item["bytes"] for item in releasable)
    total_files = sum(item["files"] for item in releasable)

    print(f"candidates={len(plan)} blocking_on_citation={len(cited_blocking)} "
          f"releasable={len(releasable)} bytes={total_bytes:,} files={total_files:,}")
    for item in plan[:14]:
        flag = "BLOCKED" if item["cited_references_inside"] else "release"
        print(f"  {item['bytes']:>13,} B  {item['files']:>6} f  {flag:<8} {item['path']}")
    for item in cited_blocking[:8]:
        print(f"  blocked refs under {item['path']}: {item['cited_references_inside'][:3]}")

    receipt = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "apply": args.apply, "plan": plan, "skipped": skipped[:20],
               "releasable": releasable, "planned_bytes": total_bytes,
               "planned_files": total_files, "deleted": [], "post_checks": []}

    if not args.apply:
        receipt["released_bytes"] = 0
        PLAN.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"PLAN ONLY written to {PLAN} (nothing deleted)")
        return 0

    for item in releasable:
        target = Path("\\\\?\\" + str(ROOT / item["path"]))
        before_files, before_bytes = walk_bytes(ROOT / item["path"])
        shutil.rmtree(target, onerror=onerror)
        receipt["deleted"].append({"path": item["path"], "files": before_files,
                                   "bytes": before_bytes, "gone": not (ROOT / item["path"]).exists()})
        print(f"  deleted {item['path']} ({before_files} files, {before_bytes:,} B)")

    for rel in sorted(set(re.findall(r"\.project-local/(?:runs|artifacts)/[^\s`\"'<>()\]\}\\|]+",
                                     corpus))):
        receipt["post_checks"].append({"cited_path": rel, "exists": (ROOT / rel).exists()})
    lost = [entry for entry in receipt["post_checks"] if not entry["exists"]]
    receipt["released_bytes"] = sum(entry["bytes"] for entry in receipt["deleted"])
    receipt["cited_paths_now_missing"] = lost
    PLAN.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"RELEASED bytes={receipt['released_bytes']:,} dirs={len(receipt['deleted'])} "
          f"cited_paths_missing_after={len(lost)}")
    for entry in lost[:10]:
        print("  LOST:", entry["cited_path"])
    return 1 if lost else 0


if __name__ == "__main__":
    sys.exit(main())
