"""Confirm no tracked file still routes runtime output into the Hermes home.

Long-path safe walk (\\?\), with a loud failure if the walk inspected too little — an empty
scan and a clean scan must not share a verdict.
"""
import os
import pathlib
import sys

ROOT = pathlib.Path.cwd()
PREFIX = "\\\\?\\" + str(ROOT).replace("/", "\\")
NEEDLES = (".hermes/task-artifacts/setup-plan", ".hermes/skill-call-index",
           "scripts/workflow/sync_hermes_workflow_assets.py",
           'ROOT / ".hermes/task-artifacts/current-state-ci.json"',
           ".hermes\\task-artifacts\\setup-plan", "scripts\\workflow\\sync_hermes")
EXTS = {".py", ".sh", ".ps1", ".md", ".json", ".yaml", ".yml"}

hits = []
count = 0
errors = []
for dirpath, dirnames, filenames in os.walk(PREFIX, onerror=lambda e: errors.append(str(e)[:100])):
    rel_dir = dirpath[len(PREFIX):].lstrip("\\")
    top = rel_dir.split("\\")[0]
    if top in {".git", ".project-local"}:
        dirnames[:] = []
        continue
    for name in filenames:
        if os.path.splitext(name)[1].lower() not in EXTS:
            continue
        full = dirpath + "\\" + name
        rel = os.path.join(rel_dir, name) if rel_dir else name
        count += 1
        try:
            body = pathlib.Path(full).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            errors.append(f"read {rel}: {exc.__class__.__name__}")
            continue
        for needle in NEEDLES:
            if needle in body:
                hits.append(f"{rel}  <-  {needle[:58]}")

print(f"tracked_tree_files_inspected={count:,} errors={len(errors)}")
for e in errors[:5]:
    print("   ERROR", e)
for h in hits[:15]:
    print("   REMAINS", h)
if not hits:
    print("stale_routing_paths_remaining=NONE")
if count < 800 or errors:
    print("SCAN_UNRELIABLE")
    sys.exit(3)
