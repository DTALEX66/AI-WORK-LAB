"""AG-19 self-verified status of every pinned historical source, long paths included.

A first attempt used Path.rglob and died on a deep directory inside the imported atlas
(absolute path > 260 chars), which is exactly the failure mode that turns "my scan could
not reach it" into "it is not here". This walk prefixes \\?\ so Windows resolves beyond
MAX_PATH, and it reports the directories it could not read instead of skipping silently.
"""
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import zipfile

ROOT = pathlib.Path.cwd()
PREFIXED = "\\\\?\\" + str(ROOT).replace("/", "\\")
MANIFEST = ROOT / ".project-local/artifacts/task-artifacts/r4/history-source-manifest.json"
pins = json.loads(MANIFEST.read_text(encoding="utf-8"))["sources"]
wanted = {s["sizeBytes"]: s for s in pins}

files = []
unreadable = []
for dirpath, dirnames, filenames in os.walk(PREFIXED, onerror=lambda e: unreadable.append(str(e))):
    if "\\.git\\" in dirpath or dirpath.rstrip("\\").endswith(".git"):
        dirnames[:] = []
        continue
    for name in filenames:
        full = dirpath + "\\" + name
        try:
            st = os.stat(full, follow_symlinks=False)
        except OSError:
            unreadable.append(f"stat {full}")
            continue
        if not os.path.isdir(full):
            files.append((full, st.st_size))

rel = [((p[len(PREFIXED):].lstrip("\\")), s) for p, s in files]
abs_of = {p[len(PREFIXED):].lstrip("\\"): p for p, s in files}
print(f"files_scanned={len(rel):,}  unreadable_entries={len(unreadable)}")
for u in unreadable[:5]:
    print("   UNREADABLE", u[:150])

by_size = {}
for path, size in rel:
    if size in wanted:
        by_size.setdefault(size, []).append(path)

print("\n=== per-pin result ===")
RESULT = []
for size in sorted(wanted, reverse=True):
    s = wanted[size]
    matches = []
    for cand in sorted(by_size.get(size, [])):
        p = abs_of[cand]
        try:
            digest = hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
        except OSError as exc:
            matches.append((cand, f"UNREADABLE {exc.__class__.__name__}", False))
            continue
        matches.append((cand, digest, digest == s["sha256"]))
    identical = [m for m in matches if m[2]]
    status = "HASH_IDENTICAL" if identical else ("SAME_SIZE_NO_HASH_MATCH" if matches else "ABSENT")
    print(f"{s['sourceId']:<24} {size:>10,} B  sha={s['sha256'][:16]}…  "
          f"same_size={len(matches)}  => {status}")
    for path, digest, ok in matches[:5]:
        print(f"      {'MATCH' if ok else 'differ'}  {path[-110:]}  {digest[:16]}")
    RESULT.append({"sourceId": s["sourceId"], "name": s["name"], "bytes": size,
                   "sha256": s["sha256"], "declaredLines": s.get("lineCount"),
                   "status": status,
                   "matches": [{"path": p, "sha256": d, "identical": ok} for p, d, ok in matches]})

timeline = wanted[15558839]
done = subprocess.run(["git", "cat-file", "--batch-all-objects", "--batch-check"],
                      capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT),
                      check=False)
obj_sizes = {}
largest = 0
for line in done.stdout.splitlines():
    fields = line.split()
    if len(fields) >= 3:
        n = int(fields[2])
        obj_sizes[n] = obj_sizes.get(n, 0) + 1
        largest = max(largest, n)
print(f"\ngit objects={sum(obj_sizes.values()):,} largest_object={largest:,} B "
      f"objects_of_timeline_size={obj_sizes.get(timeline['sizeBytes'], 0)}")

zip_hits = []
zip_count = 0
for path, _ in rel:
    if not path.lower().endswith(".zip"):
        continue
    real = abs_of[path]
    zip_count += 1
    try:
        with zipfile.ZipFile(real) as z:
            for info in z.infolist():
                if info.file_size == timeline["sizeBytes"]:
                    zip_hits.append(f"{path}::{info.filename}")
    except (zipfile.BadZipFile, OSError):
        continue
print(f"zips_inspected={zip_count} members_of_timeline_size={zip_hits or 'NONE'}")

out = ROOT / ".project-local/runs/convergence-20261007-c/ag19-evidence.json"
out.write_text(json.dumps({
    "scannedFiles": len(rel), "unreadableEntries": len(unreadable),
    "unreadableSample": unreadable[:10], "pins": RESULT,
    "gitObjects": sum(obj_sizes.values()), "gitLargestObjectBytes": largest,
    "gitObjectsOfTimelineSize": obj_sizes.get(timeline["sizeBytes"], 0),
    "zipsInspected": zip_count, "zipMembersOfTimelineSize": zip_hits,
}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("EVIDENCE_WRITTEN", out)
