"""Falsify the toolchain-declaration gate: mutate a declared claim, prove the gate fails, restore.

A gate that has only ever been observed green is not trusted yet. Each mutation below is a lie a
future editor could write into .project/governance/toolchain-declarations.json; the gate must reject it.

Not a CI step: it rewrites the declaration file in place and restores it by SHA-256 in a finally block,
so it is run by hand after changing the gate or the declaration.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DECL = ROOT / ".project/governance/toolchain-declarations.json"
TEST = "tests/workflow-assistance/test_toolchain_declarations.py"
ORIGINAL = DECL.read_bytes()


def run() -> tuple[int, str]:
    proc = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", TEST, "-q"],
                          cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    return proc.returncode, proc.stdout


def mutate(fn):
    doc = json.loads(ORIGINAL.decode("utf-8"))
    fn(doc)
    DECL.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


MUTATIONS = {
    "wrong python pin": lambda d: d["managers"][0]["ciPin"].__setitem__("version", "3.12"),
    "fabricated node pin": lambda d: d["managers"][1]["ciPin"].__setitem__("version", "22.11.0"),
    "install command not in CI": lambda d: d["managers"][1].__setitem__("install", "npm install"),
    "lockfile removed from tree": lambda d: d["managers"].pop(4),
    "root value restated": lambda d: d["managers"][0].__setitem__("runtimeRoot", ".project-local/runs"),
    "gap silently closed": lambda d: d["divergences"].pop(1),
}

failures = []
for name, fn in MUTATIONS.items():
    try:
        mutate(fn)
        code, out = run()
        tail = [line for line in out.splitlines() if " failed" in line or "passed" in line]
        print(f"{name}: exit={code} {tail[-1] if tail else 'no summary'}")
        if code == 0:
            failures.append(name)
    finally:
        DECL.write_bytes(ORIGINAL)

if hashlib.sha256(DECL.read_bytes()).hexdigest() != hashlib.sha256(ORIGINAL).hexdigest():
    print("RESTORE FAILED - bytes differ")
    sys.exit(4)
print("restored, sha256", hashlib.sha256(DECL.read_bytes()).hexdigest()[:12])
code, out = run()
print("baseline after restore:", out.strip().splitlines()[-1])
if failures:
    print("GATE CANNOT SEE: " + ", ".join(failures))
    sys.exit(1)
print("all mutations detected")
