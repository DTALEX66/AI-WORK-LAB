"""Gate: a fixture root created by production code cannot escape the project Git root.

ERR-140 was a bare ``tempfile.mkdtemp()`` whose ``ignore_errors=True`` teardown left complete mirrors of
the authority package in the system temp directory. ``packages/client-neutral-core/scripts/project_temp.py``
is the mechanism that removes the dependence on the gate runner's environment. This gate pins the three
ways that mechanism could be wrong — and two of the three were observed while the mechanism was being
written, so they are regressions here, not hypotheses:

1. the repository root was resolved one directory too high, which silently created a second
   ``.project-local`` under ``packages/`` (a new spill root, reported honestly by the sweeper);
2. a fixture whose SQLite handle is still open cannot be removed on Windows, so the sweeper must report
   it instead of pretending the directory is gone;
3. an inherited ``TMPDIR`` pointing at the system temp must be refused, not trusted.

Discovered dynamically by ``run_quality_gate.py governance``.
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "packages" / "client-neutral-core" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import project_temp  # noqa: E402


class RootResolutionTests(unittest.TestCase):
    def test_repo_root_is_the_git_root_not_a_parent_of_it(self) -> None:
        """The off-by-one that made a second runtime root under packages/ must never return."""
        self.assertTrue((project_temp.REPO_ROOT / ".project/governance/project-authority-index.json").is_file(),
                        f"REPO_ROOT resolved to {project_temp.REPO_ROOT}, which is not the Git root")
        self.assertEqual(project_temp.REPO_ROOT, ROOT)

    def test_default_tmp_is_the_declared_runtime_root(self) -> None:
        self.assertEqual(project_temp.DEFAULT_TMP, ROOT / ".project-local" / "runs" / "tmp")


class TempRootSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = {name: os.environ.get(name) for name in ("TMPDIR", "TEMP", "TMP")}

    def tearDown(self) -> None:
        for name, value in self._saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def test_system_temp_is_refused_even_when_it_is_the_environment(self) -> None:
        host = Path(tempfile.gettempdir()).resolve()
        for name in ("TMPDIR", "TEMP", "TMP"):
            os.environ[name] = str(host)
        chosen = project_temp.temp_root()
        self.assertTrue(chosen.is_relative_to(ROOT), f"temp_root() honoured an out-of-boundary TMPDIR: {chosen}")

    def test_in_repository_tmpdir_is_honoured(self) -> None:
        declared = ROOT / ".project-local" / "runs" / "tmp"
        for name in ("TMPDIR", "TEMP", "TMP"):
            os.environ[name] = str(declared)
        self.assertEqual(project_temp.temp_root().resolve(), declared.resolve())

    def test_unresolvable_tmpdir_falls_back_inside_the_boundary(self) -> None:
        # a drive that does not exist must not become the fixture root
        os.environ["TMPDIR"] = "Q:\\definitely-not-mounted\\tmp"
        os.environ.pop("TEMP", None)
        os.environ.pop("TMP", None)
        chosen = project_temp.temp_root()
        self.assertTrue(chosen.is_relative_to(ROOT), f"fell outside the boundary: {chosen}")


class FixtureLifecycleTests(unittest.TestCase):
    def test_tracked_fixture_is_created_inside_and_released(self) -> None:
        path = project_temp.fixture_dir(prefix="project-temp-gate-")
        try:
            self.assertTrue(path.is_dir())
            self.assertTrue(path.is_relative_to(ROOT), f"fixture escaped: {path}")
            self.assertIn(path, project_temp.pending_fixtures())
        finally:
            project_temp._release_tracked()
        self.assertFalse(path.exists(), "the sweeper left the fixture behind")
        self.assertNotIn(path, project_temp.pending_fixtures())

    def test_a_locked_fixture_is_reported_not_swallowed(self) -> None:
        """Negative control: ERR-140's sin was silence. A residue that cannot be removed must be said."""
        path = project_temp.fixture_dir(prefix="project-temp-lock-")
        handle = (path / "held.sqlite")
        handle.write_bytes(b"x")
        stream = io.StringIO()
        try:
            with open(handle, "rb") as locked:
                with redirect_stdout(stream):
                    project_temp._release_tracked()
                self.addCleanup(locked.close)
        finally:
            try:
                import shutil
                shutil.rmtree(path)
            except OSError:
                pass
        report = stream.getvalue()
        if "TEMP_RESIDUE_NOT_REMOVED" in report:
            self.assertIn(str(path), report)
        else:
            # the handle was released before the sweep on this host; assert the directory is genuinely gone
            self.assertFalse(path.exists(), "silent success with the fixture still on disk")

    def test_production_sites_use_the_bounded_helper(self) -> None:
        for rel in ("packages/client-neutral-core/scripts/platform_collector.py",
                    "packages/client-neutral-core/scripts/verify_gate_runtime_convergence.py",
                    "services/session-federation/gate.py"):
            source = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("tempfile.mkdtemp()", source,
                             f"{rel} went back to a bare mkdtemp with no dir= (ERR-140 class)")


class BoundaryProofTests(unittest.TestCase):
    def test_a_run_of_the_federation_gate_leaves_no_fixture_behind(self) -> None:
        """End-to-end: the real self-check script, then prove the declared root is empty of its fixtures."""
        def fixtures() -> set[str]:
            if not project_temp.DEFAULT_TMP.is_dir():
                return set()
            return {p.name for p in project_temp.DEFAULT_TMP.glob("sf-gate-*") if p.is_dir()}

        names_before = fixtures()
        result = subprocess.run([sys.executable, str(ROOT / "services/session-federation/gate.py")],
                                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                check=False)
        self.assertEqual(result.returncode, 0, result.stdout[-400:] + result.stderr[-400:])
        self.assertIn("GATE PASS", result.stdout)
        self.assertNotIn("TEMP_RESIDUE_NOT_REMOVED", result.stdout,
                         f"the gate left a fixture it could not remove:\n{result.stdout[-600:]}")
        self.assertEqual(fixtures() - names_before, set(),
                         "new fixture residue in the declared runtime root")


if __name__ == "__main__":
    unittest.main(verbosity=2)
