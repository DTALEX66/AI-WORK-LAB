"""P0-01 CI Truth Repair: negative controls for the fail-fast group runner.

Proves the exact failure-masking contract the 2026-09-25 observer fake-green
violated:

    command A = exit 1
    command B = exit 0
    => final required group = FAIL   (B must NOT mask A)

and that B is actually skipped when A fails (a later command never runs after
a required failure). Also asserts exit-code propagation (group exit == first
failing command's exit) and the happy path.

Self-contained: temp manifests are written under .project-local/runs/ and the
runner is invoked by repo-relative path (WLG-050 style, no machine paths).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "ci" / "failfast_group.py"
SCRATCH = ROOT / ".project-local" / "runs"


def run_group(manifest: Path, group: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(RUNNER), "--manifest", str(manifest), "--group", group],
        capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )
    return proc.returncode, proc.stdout + proc.stderr


def write_manifest(commands: dict) -> Path:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="failfast-", dir=SCRATCH, delete=False, encoding="utf-8"
    )
    json.dump({"version": 1, "note": "test", "groups": commands}, handle, indent=2)
    handle.close()
    return Path(handle.name)


def fail_cmd(code: int) -> list[str]:
    return [sys.executable, "-c", f"import sys; sys.exit({code})"]


def main() -> int:
    failures: list[str] = []

    # --- Core negative control: A=exit1, B=exit0 => group must FAIL, B skipped.
    manifest = write_manifest(
        {
            "negative-masking": {
                "working_dir": ".",
                "commands": [fail_cmd(1), fail_cmd(0)],
            }
        }
    )
    rc, out = run_group(manifest, "negative-masking")
    if rc == 0:
        failures.append("A(exit1)+B(exit0): group unexpectedly PASSED (masking regression)")
    if "FAILFAST_GROUP_FAIL group=negative-masking failed_cmd=1" not in out:
        failures.append("A(exit1)+B(exit0): first-failure marker missing")
    if "skipped=1" not in out:
        failures.append("A(exit1)+B(exit0): B was not skipped")
    if "exit=1 ::" not in out:
        failures.append("A(exit1)+B(exit0): A's exit code not printed")
    manifest.unlink(missing_ok=True)

    # --- Exit-code propagation: A=exit7 => group exit 7 (not clamped to 1).
    manifest = write_manifest({"exit7": {"working_dir": ".", "commands": [fail_cmd(7)]}})
    rc, out = run_group(manifest, "exit7")
    if rc != 7:
        failures.append(f"exit7: group rc={rc}, expected 7")
    manifest.unlink(missing_ok=True)

    # --- Happy path: all exit 0 => group PASS (rc 0, PASS marker).
    manifest = write_manifest({"all-zero": {"working_dir": ".", "commands": [fail_cmd(0), fail_cmd(0)]}})
    rc, out = run_group(manifest, "all-zero")
    if rc != 0 or "FAILFAST_GROUP_PASS group=all-zero" not in out:
        failures.append(f"all-zero: rc={rc}, expected 0 with PASS marker")
    manifest.unlink(missing_ok=True)

    # --- Required-group manifest completeness: the real manifest must contain the
    #     four observer groups with exactly these commands (regression guard).
    # Pinned as lists rather than counts: a count stays correct when someone drops
    # one required check and swaps in a cheaper one, which is the failure this
    # guard exists to catch.
    real = ROOT / "scripts" / "ci" / "required_groups.json"
    data = json.loads(real.read_text(encoding="utf-8"))
    expected = {
        "observer-python-skeleton": [
            ["python", "scripts/verify_observer_skeleton.py"],
            ["python", "tests/test_observer_skeleton.py"],
            ["python", "tests/test_observer_runtime.py"],
            ["python", "tests/test_observer_evidence.py"],
            ["python", "tests/test_observer_store.py"],
            ["python", "tests/test_artifact_freshness.py"],
            ["python", "scripts/verify_usage_rollup.py"],
            ["python", "tests/test_usage_rollup.py"],
            ["python", "tests/test_observer_events_migration.py"],
        ],
        "observer-web-contracts": [
            ["node", "tests/run_all_tests.js"],
        ],
        # W02 (2026-10-14): this one group used to hold npm ci + typecheck + build + test, so the job's
        # name reported their SUM and a regression in the build could not be told apart from a slow install.
        # Four named groups cost nothing extra (same commands, same fail-fast semantics) and make the step
        # durations the diagnosis. Splitting is the change; dropping a command would be a different one.
        "observer-frontend-install": [
            ["npm", "ci"],
        ],
        "observer-frontend-typecheck": [
            ["npm", "run", "typecheck"],
        ],
        "observer-frontend-build": [
            ["npm", "run", "build"],
        ],
        "observer-frontend-test": [
            ["npm", "run", "test"],
        ],
        "observer-desktop-crate": [
            ["cargo", "test", "--locked"],
            ["cargo", "check", "--locked"],
        ],
    }
    for name, commands in expected.items():
        cmds = data.get("groups", {}).get(name, {}).get("commands", [])
        if cmds != commands:
            missing = [c for c in commands if c not in cmds]
            extra = [c for c in cmds if c not in commands]
            failures.append(
                f"required_groups: {name} commands drifted "
                f"(missing={json.dumps(missing)} unexpected={json.dumps(extra)})")

    # --- Unknown group => exit 2, not 0.
    manifest = write_manifest({"x": {"working_dir": ".", "commands": [fail_cmd(0)]}})
    rc, out = run_group(manifest, "does-not-exist")
    if rc == 0 or "unknown_group" not in out:
        failures.append(f"unknown-group: rc={rc}, expected 2 + unknown_group marker")
    manifest.unlink(missing_ok=True)

    if failures:
        print("FAILFAST_GROUP_TESTS_FAIL")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("FAILFAST_GROUP_TESTS_PASS (A1+B0=>FAIL, B-skipped, exit-propagation, all-zero, manifest-completeness, unknown-group)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
