"""Mutation probe: drop the tailwind pathspec, the config test must go red.

Reverts the file byte-for-byte afterwards and verifies that it did.
"""
import pathlib
import subprocess
import sys

TARGET = pathlib.Path("apps/observer/scripts/u19_webview_e2e.py")
original = TARGET.read_bytes()
mutated = original.replace(b'    "frontend/tailwind.config.js",\n', b"")
if mutated == original:
    print("MUTATION_NOT_APPLIED")
    sys.exit(2)
TARGET.write_bytes(mutated)
try:
    done = subprocess.run(
        [sys.executable, "apps/observer/tests/test_artifact_freshness.py"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
finally:
    TARGET.write_bytes(original)

print("restored_byte_equal:", TARGET.read_bytes() == original)
print("mutated_run_exit:", done.returncode)
tail = [l for l in (done.stdout + done.stderr).splitlines() if l.strip()][-6:]
print("\n".join(tail))
verdict = "MUTATION_CAUGHT" if done.returncode != 0 else "MUTATION_SILENT"
print(f"{verdict} gate_falsified={done.returncode != 0} "
      f"restored={TARGET.read_bytes() == original}")
sys.exit(0 if (done.returncode != 0 and TARGET.read_bytes() == original) else 1)
