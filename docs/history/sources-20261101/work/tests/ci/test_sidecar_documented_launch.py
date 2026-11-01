"""The sidecar's documented entry has to be runnable *as documented*, not only under pytest.

Recorded defect (2026-10-18): `python services/orchestration/sidecar.py --project-root . ...`
-- the command in `apps/observer/README.md` and the one `apps/observer/start-observer.cmd`
launches -- died with `ModuleNotFoundError: No module named 'canonical_store'` in a clean
shell. Every CI run stayed green because `tests/conftest.py` injects the module roots before
any test imports the sidecar, so the only path that was ever exercised was the test path.

This asserts the launcher path with a cleaned environment. `PYTHONPATH` is dropped on purpose:
leaving it in would let a developer's shell -- or this repo's own bootstrap -- repair the exact
condition the test exists to detect.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SIDECAR = ROOT / "services" / "orchestration" / "sidecar.py"
RUNS = ROOT / ".project-local" / "runs" / "sidecar-launch-tests"
RELEASE_ATTEMPTS = 12
RELEASE_PAUSE_S = 0.25


def release(tree: Path, attempts: int = RELEASE_ATTEMPTS) -> None:
    """Delete the sandbox, allowing for the moment Windows still holds the child's store open.

    Measured here: the child is reaped at t=0 and its `runtime/canonical.sqlite` stays locked until
    ~250 ms later, so an immediate delete raises WinError 32 and the launch that answered
    `/api/v1/snapshot` with 200 is reported as an ERROR. Linux unlinks an open file, which is why CI
    never saw it. The budget is bounded and a tree still locked at the end is raised rather than
    ignored - silent residue would be invisible here and counted days later by
    `tests/workflow-assistance/test_temp_fixture_residue_is_bounded.py`.
    """
    last: OSError | None = None
    for _ in range(attempts):
        try:
            shutil.rmtree(tree)
            return
        except OSError as exc:
            last = exc
            time.sleep(RELEASE_PAUSE_S)
    raise RuntimeError(f"sandbox {tree} still unreleased after "
                       f"{attempts * RELEASE_PAUSE_S:.1f}s: {last}")


class DocumentedLaunchTests(unittest.TestCase):
    def test_the_documented_command_answers_ready_without_pythonpath(self) -> None:
        # In-boundary on purpose: the repo forbids its own runtime and test residue from spilling into
        # the user temp root, and the old version of this test wrote its sqlite store to %TEMP%.
        RUNS.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix="launch-", dir=str(RUNS)))
        try:
            self.assert_documented_launch(tmp)
        finally:
            release(tmp)

    def assert_documented_launch(self, tmp: Path) -> None:
        environment = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        process = subprocess.Popen(
            [
                sys.executable, str(SIDECAR),
                "--project-root", str(ROOT),
                "--runtime-root", str(tmp / "runtime"),
                "--host", "127.0.0.1",
                "--port", "0",
                "--no-worker",
            ],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            cwd=str(ROOT), env=environment,
        )
        try:
            assert process.stdout is not None
            output = ""
            for _ in range(40):  # the sidecar prints one ready line and then serves
                line = process.stdout.readline()
                if not line:
                    break
                output += line
                if "WORKFLOW_SIDECAR_READY" in line:
                    break
                if "Traceback" in line or "Error" in line:
                    break
            self.assertIn("WORKFLOW_SIDECAR_READY", output, output)
            match = re.search(r"url=http://[^:]+:(\d+)", output)
            self.assertIsNotNone(match, output)
            port = int(match.group(1))
            self.assertGreater(port, 0)
            self.assertIn("worker=disabled", output)
            # "ready" must mean serving, not just a banner: the snapshot route has to answer.
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/v1/snapshot", timeout=10) as response:
                self.assertEqual(200, response.status)
                payload = response.read().decode("utf-8")
            self.assertIn("revision", payload)
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            if process.stdout is not None:
                process.stdout.close()

    def test_the_bootstrap_names_the_roots_it_adds(self) -> None:
        """A silent sys.path insert would be a new magic; the file has to say which roots."""
        source = SIDECAR.read_text(encoding="utf-8")
        self.assertIn("packages/client-neutral-core/scripts", source)
        self.assertIn("sys.path", source)
        # the reason has to be in the file, because the next reader will ask why
        self.assertIn("conftest", source)


class ReleaseRetryIsBoundedAndLoud(unittest.TestCase):
    """Both halves of the retry have to be falsifiable, or the fix is a sleep dressed as a guard."""

    def test_a_transient_lock_is_retried_until_the_tree_goes_away(self) -> None:
        calls: list[str] = []

        def flaky(path, *args, **kwargs):
            calls.append(str(path))
            if len(calls) < 3:
                raise PermissionError(13, "another process is using the file", str(path))

        with mock.patch("shutil.rmtree", side_effect=flaky):
            release(Path("locked-tree"))
        self.assertEqual(3, len(calls),
                         "one failed attempt would have raised the very error this exists to outlast")

    def test_a_tree_that_never_releases_is_reported_instead_of_left_behind(self) -> None:
        def always_locked(path, *args, **kwargs):
            raise PermissionError(13, "another process is using the file", str(path))

        with mock.patch("shutil.rmtree", side_effect=always_locked):
            with self.assertRaises(RuntimeError) as caught:
                release(Path("never-released"), attempts=2)
        self.assertIn("never-released", str(caught.exception),
                      "an ignored failure would hide residue until the residue floor counts it days later")


if __name__ == "__main__":
    unittest.main()
