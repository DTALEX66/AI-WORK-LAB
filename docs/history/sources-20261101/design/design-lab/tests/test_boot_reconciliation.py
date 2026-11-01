# SPDX-License-Identifier: MIT
"""Restart reconciliation must tell a crashed worker from a live one.

DL-R5-004 acceptance A2 says a restart reconciles without creating duplicate
objects, and A3 says nothing unlocks until the stop is proven. Both used to be
unreachable: `job_store.recover_interrupted` is a blind scan of every RUNNING
attempt and had no production caller, so wiring it as-is would relabel work that
another process is still doing.

These tests drive the liveness-gated entry point through a real child process
holding a real OS lock, and they run the recovery-safety verifier so the script
that documents these guarantees cannot silently stop being checked.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import closing
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from design_lab.runtime import job_store as jobs  # noqa: E402
from design_lab.runtime.paths import resolve_paths  # noqa: E402

VERIFIER = ROOT / "scripts" / "verify_recovery_safety.py"

# Written to the temp dir and executed as a separate process: an OS lock held here
# is held by a *different* process, which is the only way to make "the holder died"
# mean something.
# environ={} because the authoritative suite runner exports PROJECT_LOCAL_ROOT at the
# repository root; inheriting it makes resolve_paths reject the temp project as an
# out-of-root policy violation. test_native_recovery_lock.py uses the same convention,
# which is why its cross-process case passes on CI and this one initially did not.
def _force_cleanup(tmp: tempfile.TemporaryDirectory) -> None:
    """Remove a temp project for real, after any injected refusal has been withdrawn.

    A test that injects a permanent `cleanup` refusal must not leak the directory it was
    told to keep, and must not do it by deleting the attribute inline in a `finally` the
    assertion can jump over.
    """
    try:
        del tmp.cleanup            # withdraw an instance-level injection, if any
    except AttributeError:
        pass
    deadline = time.monotonic() + 20
    while Path(tmp.name).exists() and time.monotonic() < deadline:
        try:
            tmp.cleanup()
        except PermissionError:
            time.sleep(0.2)
    if Path(tmp.name).exists():
        raise AssertionError("the temp project leaked")


def _cleanup_when_released(tmp: tempfile.TemporaryDirectory,
                           deadline_seconds: float = 10.0) -> None:
    """Remove a temp project once the OS has actually let go of the child's lock file.

    `Popen.wait()` returns when the child is reaped, but Windows releases that process's
    handles during teardown, which can land a moment later; unlinking
    `native-recovery-locks/<hash>.lock` inside that window raised WinError 32 and turned a
    passing assertion into a suite ERROR under full-run timing (it never reproduced
    standalone, which is how it survived). This retries the removal and still raises if the
    handle is genuinely never released -- a bounded wait, not a swallowed error.
    """
    deadline = time.monotonic() + deadline_seconds
    while True:
        try:
            tmp.cleanup()
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise


HOLDER_SCRIPT = '''
import sys, time
sys.path.insert(0, sys.argv[1])
from design_lab.runtime.paths import resolve_paths
from design_lab.runtime.native_recovery_lock import recovery_lock
paths = resolve_paths(project_root=sys.argv[2], environ={})
with recovery_lock(paths, sys.argv[3]):
    print("HELD", flush=True)
    time.sleep(float(sys.argv[4]))
'''


class ProbeIsRequired(unittest.TestCase):
    """A blind scan is the bug, not the fallback."""

    def setUp(self):
        runtime = ROOT / ".project-local/task-runtime/boot-reconciliation-tests"
        runtime.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=runtime)
        self.addCleanup(_cleanup_when_released, tmp)
        self.root = Path(tmp.name)
        (self.root / "AGENTS.md").write_text("# synthetic reconciliation project", encoding="utf-8")
        self.db = self.root / "state.db"
        self.conn = jobs.connect(self.db)
        self.addCleanup(self.conn.close)

    def begin_running(self, key):
        attempt = self.begin(key)
        jobs.transition(self.conn, attempt["attempt_id"], "RUNNING")
        return attempt

    def begin(self, key):
        return jobs.begin_attempt(self.conn, "job-" + key, operation_id="op-" + key,
                                  idempotency_scope="scope", idempotency_key=key,
                                  request_hash="sha256:" + "a" * 64)

    def test_a_missing_probe_is_refused_not_assumed_safe(self):
        with self.assertRaises(TypeError):
            jobs.recover_orphaned_attempts(self.conn, holder_is_gone=None)

    def test_nothing_is_relabelled_while_the_holder_lives(self):
        attempt = self.begin_running("live")
        aid = attempt["attempt_id"]
        child = subprocess.Popen(
            [sys.executable, "-X", "utf8", "-B", "-c", HOLDER_SCRIPT,
             str(ROOT / "src"), str(self.root), aid, "20"],
            cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, env={**os.environ})
        try:
            first = child.stdout.readline().strip()
            self.assertEqual("HELD", first,
                             "the child never reported holding the lock; its first output "
                             f"line was: {first[:300]!r}")
            flipped = jobs.recover_orphaned_attempts(
                self.conn, holder_is_gone=lambda a: self._free(a))
            self.assertEqual(flipped, [],
                             "an attempt with a live holder must not be touched")
            self.assertEqual(jobs.latest_attempt(self.conn, "job-live")["state"], "RUNNING")
        finally:
            child.stdout.close()
            child.terminate()
            child.wait(timeout=20)

    def test_a_dead_holder_is_relabelled_exactly_once(self):
        attempt = self.begin_running("orphan")
        aid = attempt["attempt_id"]
        flipped = jobs.recover_orphaned_attempts(self.conn, holder_is_gone=lambda a: True)
        self.assertEqual(flipped, [aid])
        self.assertEqual(jobs.latest_attempt(self.conn, "job-orphan")["state"], "OUTCOME_UNKNOWN")
        # Reconciliation created no successor attempt: relabelling is not a re-run.
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM attempt_state").fetchone()[0], 1)
        self.assertFalse(self.conn.in_transaction)
        # And it stays un-retryable until a proof is supplied, which is the
        # duplicate-object guarantee A2 actually depends on.
        with self.assertRaises(jobs.AttemptError):
            jobs.retry_attempt(self.conn, "job-orphan", previous_attempt_id=aid)
        jobs.reconcile_attempt(self.conn, aid, "effect_not_started")
        self.assertEqual(jobs.retry_attempt(self.conn, "job-orphan",
                                            previous_attempt_id=aid)["attempt_no"], 2)

    def test_only_the_orphans_are_relabelled(self):
        orphan = self.begin_running("gone")
        live = self.begin_running("busy")
        flipped = jobs.recover_orphaned_attempts(
            self.conn, holder_is_gone=lambda a: a == orphan["attempt_id"])
        self.assertEqual(flipped, [orphan["attempt_id"]])
        self.assertEqual(jobs.latest_attempt(self.conn, "job-gone")["state"], "OUTCOME_UNKNOWN")
        self.assertEqual(jobs.latest_attempt(self.conn, "job-busy")["state"], "RUNNING")

    def _free(self, attempt_id):
        from design_lab.runtime.native_recovery_lock import RecoveryBusy, recovery_lock
        try:
            with recovery_lock(resolve_paths(project_root=self.root, environ={}), attempt_id):
                return True
        except RecoveryBusy:
            return False


    def _temp_project(self) -> tempfile.TemporaryDirectory:
        runtime = ROOT / ".project-local/task-runtime/boot-reconciliation-tests"
        runtime.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=runtime)
        self.addCleanup(_force_cleanup, tmp)
        return tmp

    def test_a_permanent_refusal_is_still_propagated_after_the_bounded_wait(self):
        """The retry buys a moment, not a pardon -- asserted without platform machinery.

        Without this case the helper could be quietly widened to `ignore_errors=True` and
        the suite would go green while leaking a temp project on every run: the same
        failure it exists to survive, just hidden instead of fixed. The refusal is injected
        because which OS mechanism refuses a removal is platform machinery (Windows holds
        the file, POSIX unlinks it while a process still holds it), whereas the promise
        under test -- a refusal that does not go away must reach the caller after a bounded
        number of tries -- is not.
        """
        tmp = self._temp_project()
        attempts = []

        def always_refuse():
            attempts.append(1)
            raise PermissionError(13, "Permission denied")

        tmp.cleanup = always_refuse
        with self.assertRaises(PermissionError):
            _cleanup_when_released(tmp, deadline_seconds=1.0)
        self.assertGreater(len(attempts), 1,
                           "the bounded wait must actually retry before it gives up")

    @unittest.skipIf(os.name != "nt",
                     "ENVIRONMENT_FAIL: only Windows refuses removal of a file another "
                     "process still holds; on POSIX an open handle is no obstacle, so there "
                     "is no real-handle refusal to observe there")
    def test_the_wait_survives_a_handle_that_is_never_released(self):
        """End-to-end on the platform that actually has the transient the helper exists for."""
        tmp = self._temp_project()
        locked = Path(tmp.name) / "held.lock"
        locked.write_bytes(b"x")
        child = subprocess.Popen(
            [sys.executable, "-B", "-c",
             "import sys,time\n"
             "f=open(sys.argv[1],'rb')\n"
             "print('HELD', flush=True)\n"
             "time.sleep(float(sys.argv[2]))",
             str(locked), "8"],
            cwd=str(ROOT), stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), "HELD")
            with self.assertRaises(PermissionError):
                _cleanup_when_released(tmp, deadline_seconds=1.0)
        finally:
            child.stdout.close()
            child.terminate()
            child.wait(timeout=20)


class ProductionEntryIsWired(unittest.TestCase):
    """The service method is the caller the CLI uses; it must behave on its own."""

    def setUp(self):
        runtime = ROOT / ".project-local/task-runtime/boot-reconciliation-tests"
        runtime.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=runtime)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "AGENTS.md").write_text("# synthetic reconciliation project", encoding="utf-8")
        self._env = patch.dict(os.environ, {"PROJECT_LOCAL_ROOT": str(self.root / ".project-local")})
        self._env.start()
        self.addCleanup(self._env.stop)
        from design_lab.service import ProjectService
        self.service = ProjectService(str(self.root))

    def test_a_fresh_project_with_no_database_is_not_an_error(self):
        self.assertFalse(self.service.database.exists())
        self.assertEqual(self.service.reconcile_interrupted_attempts(), [])

    def test_the_service_reconciles_an_orphan_left_by_a_crash(self):
        with closing(jobs.connect(self.service.database,
                                  project_root=self.service.paths.project_root)) as conn:
            attempt = jobs.begin_attempt(conn, "job1", operation_id="op1",
                                         idempotency_scope="project1", idempotency_key="save1",
                                         request_hash="sha256:" + "a" * 64)
            jobs.transition(conn, attempt["attempt_id"], "RUNNING")
            conn.commit()
        self.assertEqual(self.service.reconcile_interrupted_attempts(),
                         [attempt["attempt_id"]])
        with closing(jobs.connect(self.service.database,
                                  project_root=self.service.paths.project_root)) as conn:
            self.assertEqual(jobs.latest_attempt(conn, "job1")["state"], "OUTCOME_UNKNOWN")


class RecoverySafetyVerifierIsExecuted(unittest.TestCase):
    """verify_recovery_safety.py used to be referenced nowhere but a manifest list.

    Being discovered here is what puts it in CI; asserting on its *helpers* is what
    stops it from passing on the existence of a function name again. Nothing is
    executed with --check because generate-mode writes a tracked report.
    """

    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location("verify_recovery_safety", VERIFIER)
        cls.verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.verifier)

    def test_the_live_audit_has_no_findings_and_claims_the_new_checks(self):
        recovery = self.verifier.audit_unknown_outcome()
        self.assertEqual(recovery["findings"], [],
                         f"recovery safety findings: {recovery['findings']}")
        self.assertTrue(recovery["recovery_is_called_in_production"],
                        "the verifier must assert a production call site, not hasattr")
        self.assertIn("src/design_lab/service.py", recovery["recovery_production_callers"])
        self.assertEqual(recovery["blind_scan_production_callers"], [],
                         "nobody may call the blind RUNNING scan from production")
        self.assertTrue(recovery["execution_holds_attempt_lock"],
                        "the liveness prerequisite has to be checked, or a later "
                        "change can delete it and the suite would not notice")
        self.assertTrue(recovery["tests"])

    def test_the_call_site_scan_detects_absence_as_well_as_presence(self):
        """A gate that can only say yes has no measurement value."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "pkg"
            package.mkdir()
            (package / "caller.py").write_text(
                "from m import f\ndef g():\n    f(1)\n", encoding="utf-8")
            (package / "quiet.py").write_text("def h():\n    return 1\n", encoding="utf-8")
            (package / "definer.py").write_text("def f(a):\n    return a\n", encoding="utf-8")
            hits = self.verifier.production_call_sites("f", root=package)
            # Basenames, not paths: the suite runner redirects the temp root inside the
            # repository, so a repo-relative expectation would differ between CI and a
            # bare shell. Which files were found is the claim; where the temp dir sits
            # is not.
            self.assertEqual(sorted(Path(h).name for h in hits),
                             ["caller.py", "definer.py"], hits)
            self.assertEqual(self.verifier.production_call_sites("never_called", root=package), [])

    def test_a_test_that_only_mentions_the_word_unknown_does_not_count(self):
        """The old coverage rule was `'unknown' in file.lower()`; this is the fix."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "weak.py").write_text(
                "# this file talks about unknown outcomes but calls nothing\n"
                "X = 'unknown'\n", encoding="utf-8")
            (root / "strong.py").write_text("def t():\n    return recover_orphaned_attempts(c)\n",
                                            encoding="utf-8")
            with patch.object(self.verifier, "REPO", root):
                self.assertFalse(self.verifier.test_exercises_recovery("weak.py"))
                self.assertTrue(self.verifier.test_exercises_recovery("strong.py"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
