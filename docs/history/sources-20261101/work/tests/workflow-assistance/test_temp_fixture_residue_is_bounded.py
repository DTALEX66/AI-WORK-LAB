"""Gate: the bounded temp root must not accumulate orphaned fixtures.

The creation half of this boundary was gated long ago (``test_temp_fixture_stays_inside_the_boundary``
refuses a ``mkdtemp`` with no ``dir=``), and the at-exit sweeper in ``project_temp`` does release what
its own process created — measured 2026-10-08 by running ``test_cleanup.py`` (17 tests, 17 fixtures,
the ``wlsim-*`` count unchanged before and after). What nothing guarded was the *orphan*: a gate job
that is killed, times out or crashes never reaches at-exit, and its fixture roots then have no owner.
The pile it left was 4811 directories / 531.7 MiB under ``.project-local/runs/tmp``, 676 of them
carrying a nested ``.git`` whose mode-0444 objects made even an explicit ``shutil.rmtree`` fail with
WinError 5, which ``ignore_errors=True`` had been swallowing. It was reclaimed by
``scripts/maintenance/release_temp_fixture_residue.py --apply`` (4796 dirs, 556,311,265 bytes freed,
0 failures, manifest under ``.project-local/artifacts/temp-residue-reclaim/``).

This gate is what keeps it from regrowing. It measures the effect rather than the code pattern, so a
new call site that leaks some other way is still caught, and it uses the reclaim tool's own census and
age floor so the two cannot drift. The floor (6 hours) is what makes the check safe on a shared
checkout: a fixture belonging to a run that is live right now is never counted, and the planted-fixture
tests below prove both halves of that.

Discovered dynamically by ``run_quality_gate.py governance``.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "maintenance" / "release_temp_fixture_residue.py"
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))
import project_temp  # noqa: E402


def _load_tool():
    spec = importlib.util.spec_from_file_location("release_temp_fixture_residue", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tool = _load_tool()


def _plant(name: str, *, age_hours: float, nested_git: bool = False) -> Path:
    path = tool.DEFAULT_ROOT / name
    path.mkdir(parents=True, exist_ok=True)
    (path / "payload.bin").write_bytes(b"\0" * 4096)
    if nested_git:
        objects = path / ".git" / "objects" / "ab"
        objects.mkdir(parents=True, exist_ok=True)
        blob = objects / "cdef"
        blob.write_bytes(b"fixture object")
        blob.chmod(0o444)  # what git writes, and what a plain rmtree cannot remove on Windows
    old = time.time() - age_hours * 3600.0
    os.utime(path, (old, old))
    return path


class ResidueIsBoundedTests(unittest.TestCase):
    def test_the_reclaim_target_is_inside_the_project(self) -> None:
        # A gate that measures the wrong directory reports a clean tree it never looked at.
        self.assertTrue(project_temp.inside_project(tool.DEFAULT_ROOT))
        self.assertEqual(tool.DEFAULT_ROOT, ROOT / ".project-local" / "runs" / "tmp")

    def test_no_orphaned_fixture_is_older_than_the_floor(self) -> None:
        if not tool.DEFAULT_ROOT.is_dir():
            return  # a checkout that has never run a fixture has nothing to reclaim
        rows = tool.candidates(tool.DEFAULT_ROOT, tool.DEFAULT_OLDER_THAN_HOURS, time.time())
        named = ", ".join(f"{row['name']}({row['age_hours']}h)" for row in rows[:12])
        self.assertEqual(
            rows, [],
            f"{len(rows)} orphaned fixture root(s) older than {tool.DEFAULT_OLDER_THAN_HOURS}h are "
            f"unclaimed: {named}{' ...' if len(rows) > 12 else ''} — release them with "
            f"`python {SCRIPT.relative_to(ROOT).as_posix()} --apply`",
        )

    def test_census_counts_an_orphan_and_ignores_a_live_fixture(self) -> None:
        live = _plant("residue-gate-live-", age_hours=0.01)
        orphan = _plant("residue-gate-orphan-", age_hours=8.0, nested_git=True)
        self.addCleanup(project_temp.force_release, live)
        self.addCleanup(project_temp.force_release, orphan)
        rows = tool.candidates(tool.DEFAULT_ROOT, tool.DEFAULT_OLDER_THAN_HOURS, time.time())
        names = {row["name"] for row in rows}
        self.assertIn(orphan.name, names, "an 8h-old orphan was not counted: the floor is inverted")
        self.assertNotIn(live.name, names, "a fixture seconds old was counted: a concurrent run "
                                           "would have its working directory reclaimed")
        row = next(r for r in rows if r["name"] == orphan.name)
        self.assertTrue(row["has_nested_git"], "a nested .git was not identified, so the read-only "
                                               "class this tool exists for would be invisible")
        self.assertEqual(row["files"], 2)

    def test_force_release_removes_a_git_fixture_a_plain_rmtree_cannot(self) -> None:
        orphan = _plant("residue-gate-release-", age_hours=8.0, nested_git=True)
        self.addCleanup(project_temp.force_release, orphan)
        self.assertTrue(project_temp.force_release(orphan))
        self.assertFalse(orphan.exists(), "force_release reported success while the fixture survived")

    def test_the_tool_refuses_a_root_outside_the_project(self) -> None:
        # Deliberately NOT `tempfile.gettempdir()`: inside a gate run that resolves to the project's
        # own temp root, which is a legal target — a probe built from it would prove nothing.
        outside = ROOT.parent / "work-lab-refusal-probe"
        self.assertFalse(outside.is_relative_to(ROOT))
        result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(outside), "--apply"],
                                capture_output=True, text=True, encoding="utf-8", errors="replace",
                                cwd=ROOT)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("TEMP_RESIDUE_REFUSED", result.stdout)
        self.assertFalse(outside.exists(), "the refusal still created the directory it refused")


class ManifestIdentityTests(unittest.TestCase):
    """The record of what was deleted must survive the next measurement of what is there.

    Measured 2026-10-25: the manifest name was a second-granularity timestamp with no mode, so a dry run
    landing in the same second as `--apply` resolved to the same path and rewrote the applied record — the
    census line and the release line printed the identical filename. A deletion log that can be replaced by
    a later read-only pass is not evidence of anything.
    """

    def setUp(self) -> None:
        self.dir = Path(project_temp.fixture_dir(prefix="residue-manifest-"))

    def test_a_dry_run_cannot_replace_an_applied_record(self) -> None:
        stamp = "20261026T110000Z-000000"
        applied = tool.write_manifest(self.dir, "apply", stamp, {"apply": True, "released": [{"path": "x"}]})
        before = applied.read_bytes()
        dry = tool.write_manifest(self.dir, "dry", stamp, {"apply": False, "released": []})
        self.assertNotEqual(applied, dry, "a dry run resolved onto the applied manifest's own path")
        self.assertEqual(before, applied.read_bytes(), "the applied record changed under a dry run")
        self.assertIn("apply", applied.name)
        self.assertIn("dry", dry.name)

    def test_two_passes_in_the_same_instant_get_two_files(self) -> None:
        stamp = "20261026T110000Z-000000"
        first = tool.write_manifest(self.dir, "dry", stamp, {"n": 1})
        second = tool.write_manifest(self.dir, "dry", stamp, {"n": 2})
        self.assertNotEqual(first, second)
        self.assertEqual({"n": 1}, __import__("json").loads(first.read_text(encoding="utf-8")))
        self.assertEqual({"n": 2}, __import__("json").loads(second.read_text(encoding="utf-8")))

    def test_the_allocation_refuses_to_overwrite_silently(self) -> None:
        # The counter is bounded: a collision storm must surface as a refusal, not as a clobber.
        for attempt in range(1000):
            tool.write_manifest(self.dir, "dry", "flood", {"attempt": attempt})
        with self.assertRaises(RuntimeError):
            tool.write_manifest(self.dir, "dry", "flood", {"attempt": 1000})


class BrowserProfileCensusTests(unittest.TestCase):
    """A killed geometry gate leaves its Chrome profile behind, and it never lived in the census root."""

    def setUp(self) -> None:
        self.dir = Path(project_temp.fixture_dir(prefix="residue-profiles-"))
        for name in ("udf-1792341448-10404", "chrome-profile-old", "profile-keep", "unrelated-keep"):
            path = self.dir / name
            (path / "Default").mkdir(parents=True)
            (path / "Default" / "Preferences").write_text("{}", encoding="utf-8")
            os.utime(path, (time.time() - 9 * 3600, time.time() - 9 * 3600))

    def test_only_the_declared_profile_prefixes_are_candidates(self) -> None:
        rows = tool.candidates(self.dir, tool.DEFAULT_OLDER_THAN_HOURS, time.time(),
                               tool.PROFILE_PREFIXES)
        self.assertEqual(["chrome-profile-old", "profile-keep", "udf-1792341448-10404"],
                         sorted(row["name"] for row in rows),
                         "the filter either missed a browser scratch dir or reached into unrelated ones")

    def test_the_default_census_reports_a_browser_profile_count(self) -> None:
        result = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True,
                                text=True, encoding="utf-8", errors="replace")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("browser_profiles=", result.stdout,
                      "the census still only counts the bounded temp root, so a leftover Chrome profile "
                      "stays invisible to the tool that exists to reclaim it")


if __name__ == "__main__":
    unittest.main()
