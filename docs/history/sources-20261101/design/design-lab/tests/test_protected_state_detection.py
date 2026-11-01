# SPDX-License-Identifier: MIT
"""The read-only detector must see bytes, not a status string -- three plants proved it did not.

`verify_projection_freshness.py` guards the claim that a `--check` writes nothing, because a checker
that rewrites its own record can never disagree with it. The first version compared
`git status --porcelain` strings and reported `set(after) - set(before)`. Driven against the three
cases the guard exists for, it caught one:

* a file that was already dirty and gets rewritten with different bytes keeps the *same* status
  line -- missed;
* a check that restores a dirty file back to its committed content makes the set *smaller*, which a
  forward difference cannot express -- missed;
* a clean file getting written appears in the after-set -- caught.

It also treated an empty stdout as "nothing changed", so a failing git call (locked index, unreadable
long path) silently certified the run. The detector now fingerprints path + status + content digest,
reports the transition as `was=… now=…` (CLEAN / status code / ABSENT), and fails closed when git
itself cannot run -- either by exiting non-zero or by refusing to start.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "design-lab" / "scripts"))

import verify_projection_freshness as gate  # noqa: E402

GIT = ["git"]


def run(argv, cwd):
    return subprocess.run(GIT + argv, cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


class RepoFixture(unittest.TestCase):
    """A throwaway repository, because a plant must move real bytes and may not touch this tree."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        if run(["--version"], cwd=self.repo).returncode != 0:
            self.skipTest("git is not available on this machine")
        for args in (["init", "-q"], ["config", "user.email", "t@example.invalid"],
                     ["config", "user.name", "fixture"], ["config", "core.autocrlf", "false"],
                     ["config", "core.safecrlf", "false"]):
            self.assertEqual(run(args, cwd=self.repo).returncode, 0, args)
        (self.repo / "reports").mkdir()
        self.record = self.repo / "reports" / "RECORD.json"
        self.record.write_text('{"verdict": "PASS"}\n', encoding="utf-8", newline="\n")
        self.assertEqual(run(["add", "-A"], cwd=self.repo).returncode, 0)
        self.assertEqual(run(["commit", "-q", "-m", "fixture"], cwd=self.repo).returncode, 0)
        self._repo = gate.REPO
        gate.REPO = self.repo

    def tearDown(self) -> None:
        gate.REPO = self._repo
        self._tmp.cleanup()

    def dirty(self, text: str) -> None:
        self.record.write_text(text, encoding="utf-8", newline="\n")

    def drive(self, child) -> tuple[list[str], str]:
        """Run the guard with `child` standing in for the subprocess check, so no real child runs."""
        def fake_run_entry(generator, argv):
            child()
            return 0, "VERIFY_X=OK"

        real = gate.run_entry
        gate.run_entry = fake_run_entry
        try:
            _code, _tail, moved, scan_error = gate.run_entry_read_only("x.py", ["--check"])
        finally:
            gate.run_entry = real
        return moved, scan_error


class DetectorTests(RepoFixture):
    def test_a_clean_file_that_gets_written_is_reported(self) -> None:
        moved, error = self.drive(lambda: self.dirty('{"verdict": "REWRITTEN"}\n'))
        self.assertEqual(error, "")
        self.assertEqual(len(moved), 1, moved)
        self.assertIn("reports/RECORD.json [was=CLEAN now= M sha256:", moved[0])

    def test_an_already_dirty_file_rewritten_with_other_bytes_is_reported(self) -> None:
        self.dirty('{"verdict": "STALE"}\n')
        before_status = run(["status", "--porcelain"], cwd=self.repo).stdout
        moved, error = self.drive(lambda: self.dirty('{"verdict": "FRESH"}\n'))
        after_status = run(["status", "--porcelain"], cwd=self.repo).stdout
        self.assertEqual(before_status, after_status,
                         "the plant must be invisible to a status-string comparison to mean anything")
        self.assertEqual(self.record.read_text(encoding="utf-8"), '{"verdict": "FRESH"}\n')
        self.assertEqual(len(moved), 1, moved)
        self.assertIn(" [was= M sha256:", moved[0])
        self.assertIn(" now= M sha256:", moved[0])
        first, second = moved[0].split("was=")[1].rstrip("]").split(" now=")
        self.assertNotEqual(first, second, f"the digest did not change? {moved}")

    def test_a_dirty_file_restored_to_clean_by_a_check_is_reported(self) -> None:
        self.dirty('{"verdict": "STALE"}\n')
        committed = run(["show", "HEAD:reports/RECORD.json"], cwd=self.repo).stdout
        before_status = run(["status", "--porcelain"], cwd=self.repo).stdout

        def restore():
            self.record.write_text(committed, encoding="utf-8", newline="\n")

        moved, error = self.drive(restore)
        after_status = run(["status", "--porcelain"], cwd=self.repo).stdout
        self.assertNotEqual(before_status.strip(), "", "the fixture must start dirty")
        self.assertEqual(after_status.strip(), "", "git sees the file as clean again")
        self.assertEqual(len(moved), 1, moved)
        self.assertIn("now=CLEAN]", moved[0],
                      f"restoring a dirty file is a write, and it was not reported: {moved}")

    def test_a_write_outside_the_record_is_seen_even_when_the_record_is_untouched(self) -> None:
        stray = self.repo / "reports" / "OTHER.json"
        moved, _error = self.drive(lambda: stray.write_text("{}\n", encoding="utf-8", newline="\n"))
        self.assertEqual(len(moved), 1, moved)
        self.assertIn("reports/OTHER.json", moved[0])
        self.assertIn("??", moved[0], "an untracked new file must show its status code")

    def test_a_deleted_tracked_file_is_reported_not_silently_ignored(self) -> None:
        moved, _error = self.drive(lambda: self.record.unlink())
        self.assertEqual(len(moved), 1, moved)
        self.assertIn("ABSENT", moved[0])
        self.record.write_text('{"verdict": "PASS"}\n', encoding="utf-8", newline="\n")

    def test_a_failing_git_call_fails_closed_instead_of_certifying_nothing_changed(self) -> None:
        real = gate.REPO
        outside = Path(tempfile.mkdtemp())          # NOT under the fixture repo, which is a repo
        # ...but "not under this repository" is not enough. `project_test_environment` points
        # TEMP/TMPDIR at `.project-local/task-runtime/<namespace>/tmp`, i.e. *inside* the
        # checkout, so `mkdtemp()` here lands in the repository on CI and in
        # `scripts/run_python_tests.py` -- and git then walks up, succeeds, and this test reads
        # the real tree's status instead of a git failure. Measured 2026-10-13: on a host with a
        # system temp root the test passed, and the same code failed on CI. The ceiling below and
        # the premise assertion are what make the fixture mean what its name says.
        previous_ceiling = os.environ.get("GIT_CEILING_DIRECTORIES")
        os.environ["GIT_CEILING_DIRECTORIES"] = str(outside)
        try:
            # (1) a directory that is not a repository: git runs and refuses
            plain = outside / "plain"
            plain.mkdir()
            premise = run(["rev-parse", "--show-toplevel"], cwd=plain)
            self.assertNotEqual(premise.returncode, 0,
                                f"the fixture is inside a repository after all: "
                                f"{premise.stdout.strip()}")
            gate.REPO = plain
            snapshot, error = gate.protected_state()
            self.assertEqual(snapshot, {}, error)
            self.assertIn("git status exited", error)
            # (2) a path that is not a directory at all: git cannot even be started
            gate.REPO = outside / "not-a-repository"
            snapshot, error = gate.protected_state()
            self.assertEqual(snapshot, {})
            self.assertIn("git could not run", error)
            for broken in (plain, Path(self._tmp.name) / "not-a-repository"):
                gate.REPO = broken
                _code, _tail, moved, scan_error = gate.run_entry_read_only("x.py", ["--check"])
                self.assertEqual(moved, [], "a broken detector must not claim to have watched")
                self.assertTrue(scan_error, (broken, scan_error))
                failures = gate.guard_read_only("x.py", ["--check"], "x",
                                                "FRESHNESS-DRIFT", "proof")[4]
                self.assertTrue(any("FRESHNESS-PROTECTED-SCAN-FAILED" in f for f in failures),
                                 (broken, failures))
        finally:
            gate.REPO = real
            if previous_ceiling is None:
                os.environ.pop("GIT_CEILING_DIRECTORIES", None)
            else:
                os.environ["GIT_CEILING_DIRECTORIES"] = previous_ceiling
            import shutil
            shutil.rmtree(outside, ignore_errors=True)



class LegacyComparisonTests(RepoFixture):
    """The old string rule, kept as a measurement: it must miss exactly the two plants above."""

    @staticmethod
    def old_dirty_paths(repo: Path) -> set[str]:
        result = subprocess.run(GIT + ["status", "--porcelain"], cwd=str(repo), capture_output=True,
                                text=True, encoding="utf-8", errors="replace")
        return {line.split(None, 1)[-1] for line in result.stdout.splitlines() if line.strip()}

    def test_the_status_string_difference_cannot_see_a_rewrite_or_a_restore(self) -> None:
        self.dirty('{"verdict": "STALE"}\n')
        before = self.old_dirty_paths(self.repo)
        self.record.write_text('{"verdict": "FRESH"}\n', encoding="utf-8", newline="\n")
        after = self.old_dirty_paths(self.repo)
        self.assertEqual(after - before, set(),
                         "the rewrite is now visible to the old rule, so this control no longer proves")

        committed = run(["show", "HEAD:reports/RECORD.json"], cwd=self.repo).stdout
        before = self.old_dirty_paths(self.repo)
        self.record.write_text(committed, encoding="utf-8", newline="\n")
        after = self.old_dirty_paths(self.repo)
        self.assertEqual(after - before, set(),
                         "the restore is now visible to the old rule, so this control no longer proves")


class NoAutoRebindTests(unittest.TestCase):
    def test_the_gate_does_not_close_a_subject_debt_by_rewriting_a_report(self) -> None:
        """`subject_sha` staying empty is the point; a freshness run must not fill it in."""
        record = ROOT / "reports" / "current" / "SPILL-CENSUS.json"
        register = ROOT / "design-lab" / "config" / "report-subject-debt.json"
        if not record.is_file() or not register.is_file():
            self.skipTest("the census record or the debt register is not in this checkout")
        subject_before = str(_json_load(record).get("subject_sha", ""))
        digest_before = hashlib.sha256(record.read_bytes()).hexdigest()
        register_before = hashlib.sha256(register.read_bytes()).hexdigest()
        failures, _exclusions, _checked, _missing = gate.check()
        self.assertEqual([f for f in failures if "SPILL-CENSUS" in f], [], failures)
        self.assertEqual(hashlib.sha256(record.read_bytes()).hexdigest(), digest_before,
                         "the freshness run rewrote a projection it was supposed to verify")
        self.assertEqual(str(_json_load(record).get("subject_sha", "")), subject_before,
                         "a declared subject debt was silently filled in by a check run")
        self.assertEqual(hashlib.sha256(register.read_bytes()).hexdigest(), register_before,
                         "the debt register was edited by a check run; it only shrinks by a "
                         "deliberate, recorded regeneration")


def _json_load(path: Path) -> dict:
    import json
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
