"""Does anything still quote the pre-amendment registry digest?

The atlas tree holds long paths beyond MAX_PATH, and a scan that silently inspects zero
files reads exactly like a clean result, so this walks with the \\?\ form, counts what it
actually opened, and fails loudly if the walk produced errors or inspected nothing.
"""
import hashlib
import os
import pathlib
import sys

ROOT = pathlib.Path.cwd()
PREFIX = "\\\\?\\" + str(ROOT).replace("/", "\\")
BACKUP = ROOT / ".project-local/artifacts/ag19-registry-backup-20261007/SOURCE_REGISTRY.copy1.json"
LIVE = ROOT / ".project-local/atlas-2026-09-29/WORK-LAB_MASTER_ATLAS_2026-09-29/WORK-LAB_MASTER_SOURCE_REGISTRY.json"

old = hashlib.sha256(BACKUP.read_bytes()).hexdigest()
new = hashlib.sha256(LIVE.read_bytes()).hexdigest()
print(f"prefix={PREFIX!r}")
print(f"old={old[:16]}…  new={new[:16]}…")

text_ext = (".txt", ".json", ".md", ".py", ".yaml", ".yml", ".csv")
count = 0
hits = []
errors = []
for dirpath, dirnames, filenames in os.walk(PREFIX, onerror=lambda e: errors.append(str(e)[:120])):
    if dirpath.endswith("\\.git") or "\\.git\\" in dirpath:
        dirnames[:] = []
        continue
    for name in filenames:
        full = dirpath + "\\" + name
        rel = full[len(PREFIX):].lstrip("\\")
        if not rel.lower().endswith(text_ext):
            continue
        count += 1
        try:
            with open(full, encoding="utf-8", errors="replace") as fh:
                body = fh.read()
        except OSError as exc:
            errors.append(f"read {rel[:70]}: {exc.__class__.__name__}")
            continue
        if old in body:
            hits.append(("OLD", rel))
        if new in body:
            hits.append(("NEW", rel))

print(f"text_files_inspected={count:,} walk_or_read_errors={len(errors)}")
for e in errors[:5]:
    print("   ERROR", e)
for tag, rel in hits[:20]:
    print(f"   {tag} reference: {rel}")
if not hits:
    print("references=NONE")

if count < 1000 or errors:
    print("SCAN_UNRELIABLE — the walk did not cover the tree; do not report NONE as proof")
    sys.exit(3)
sys.exit(0)
