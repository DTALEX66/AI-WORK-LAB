"""Finish removing .project-local/runs/tmp: the refusal is a read-only bit on nested
.git object files, not a permission boundary (a sibling file in the same tree deleted fine).

Clears the bit, retries, and reports what remains. Then re-verifies the keep-list and the
recovered space, and prints the manifest that was written before any deletion.
"""
import hashlib
import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys

ROOT = pathlib.Path.cwd()
PREFIX = "\\\\?\\" + str(ROOT).replace("/", "\\")
REL = ".project-local/runs/tmp"
TARGET = PREFIX + "\\" + REL.replace("/", "\\")
OUT = ROOT / ".project-local/artifacts/cleanup-20261007"


def onerror(func, path, exc_info):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def force_remove(tree: str):
    full = PREFIX + "\\" + tree.replace("/", "\\")
    if not os.path.isdir(full):
        return False
    shutil.rmtree(full, onerror=onerror)
    return not os.path.exists(full)


if os.path.isdir(TARGET):
    removed = force_remove(REL)
    print("runs/tmp removed:", removed)
    if not removed:
        left = sum(len(f) for _, _, f in os.walk(TARGET))
        print("files still present:", left)
else:
    print("runs/tmp already gone")

for rel in ("apps/observer/src-tauri/target", ".project-local/runs/cache",
            ".project-local/runs/pycache", REL):
    print(f"exists {rel}: {(ROOT / rel).exists()}")

KEEP = {
    ".project-local/runs/u19-msvc-20261006/target/release/app.exe":
        lambda p: hashlib.sha256(p.read_bytes()).hexdigest().startswith("6f73c14eb542f1a7"),
    ".project-local/runs/u19-msvc-20261006/target/release/app.exe.inputs.json":
        lambda p: p.is_file(),
    ".project-local/toolchains/wl-py311/Scripts/python.exe": lambda p: p.is_file(),
    ".project-local/artifacts/gdv-rescue-20261006/github-delivery-repair-uncommitted.patch":
        lambda p: p.is_file(),
    ".project-local/imported-from-workbuddy-20261006/MANIFEST.md": lambda p: p.is_file(),
}
print("\n=== survivors (keep-list) ===")
bad = []
for rel, check in KEEP.items():
    p = ROOT / rel
    ok = p.is_file() and check(p)
    print(f"{'OK  ' if ok else 'LOST'} {rel}")
    if not ok:
        bad.append(rel)

reports = sorted((OUT / "spill-reports").rglob("spill-report.json"))
print(f"\nspill reports retained: {len(reports)}")

manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
total = sum(i["bytes"] for i in manifest["items"])
print("manifest items (measured before deletion):")
for i in manifest["items"]:
    print(f"  {i['path']:<44} files={i['files']:>6,} bytes={i['bytes']:>14,} "
          f"du_kb={i.get('duKb'):>9,}")
print(f"manifest total bytes={total:,} ({total / 2**30:.2f} GiB)")

du = subprocess.run(["du", "-sk", ".project-local"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                    cwd=str(ROOT), check=False).stdout.split()
print(".project-local now (KiB):", du[0] if du else "UNKNOWN")
print("git content diff lines:", len([l for l in subprocess.run(
    ["git", "diff", "--name-only"], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT),
    check=False).stdout.splitlines() if l]))
sys.exit(2 if bad else 0)
