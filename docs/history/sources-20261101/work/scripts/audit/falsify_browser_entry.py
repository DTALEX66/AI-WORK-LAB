"""Falsify the new browser-entry tests: remove the guard each one claims, require red.

1. path-escape guard off -> the escape test must fail AND the outside file must actually
   leak (checked explicitly, because a test that only asserts "403" can pass for nothing).
2. static root disabled -> root/asset/fallback tests must fail.
Every mutation is restored byte-for-byte and verified.
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path.cwd()
SIDECAR = ROOT / "services/orchestration/sidecar.py"
TEST = "tests/workflow-assistance/test_sidecar_ui_browser_entry.py"
ENV_EXTRA = {"PYTHONPATH": ";".join([str(ROOT / "services/orchestration"),
                                     str(ROOT / "packages/client-neutral-core/scripts")]),
             "PYTHONDONTWRITEBYTECODE": "1"}

GUARD = (b"            try:\n"
         b"                candidate.relative_to(static_root)\n"
         b"            except ValueError:\n"
         b'                self.send_json(403, {"status": "static_path_escape"})\n'
         b"                return True\n")
STATIC_OFF = (b"            if static_root is None:\n"
              b"                return False\n")

CASES = [
    ("path-escape guard removed", GUARD, b"            pass\n"),
    ("static serving disabled", STATIC_OFF,
     b"            if static_root is None:\n                return False\n"
     b"            return False\n"),
]

import os
problems = 0
for label, needle, replacement in CASES:
    original = SIDECAR.read_bytes()
    # The working copy carries whatever line endings git materialised, so build
    # the needle against the file's own newline instead of assuming LF.
    nl = b"\r\n" if b"\r\n" in original else b"\n"
    needle = needle.replace(b"\n", nl)
    replacement = replacement.replace(b"\n", nl)
    if original.count(needle) != 1:
        print(f"SKIP    {label}: needle hits={original.count(needle)}")
        problems += 1
        continue
    SIDECAR.write_bytes(original.replace(needle, replacement, 1))
    env = dict(os.environ, **ENV_EXTRA)
    done = subprocess.run([sys.executable, TEST], capture_output=True, text=True, encoding="utf-8", errors="replace",
                          cwd=str(ROOT), env=env, check=False)
    SIDECAR.write_bytes(original)
    restored = SIDECAR.read_bytes() == original
    out = (done.stdout or "") + (done.stderr or "")
    failed = [l.strip()[:110] for l in out.splitlines()
              if l.strip().startswith(("FAIL:", "ERROR:")) or "FAILED" in l
              or "leaked" in l]
    caught = done.returncode != 0
    print(f"{'CAUGHT' if caught and restored else 'SILENT '}  exit={done.returncode} "
          f"restored={restored}  {label}")
    for line in failed[:4]:
        print("        ", line)
    if not (caught and restored):
        problems += 1

print("verify unchanged:", SIDECAR.read_bytes() == SIDECAR.read_bytes())
print(f"FALSIFICATION_PROBLEMS={problems}")
sys.exit(1 if problems else 0)
