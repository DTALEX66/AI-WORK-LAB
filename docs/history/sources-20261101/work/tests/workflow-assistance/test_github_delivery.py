"""Negative controls for the optional GitHub delivery helpers."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages/client-neutral-core/scripts"))
from github_common import git, local_path, redact
from github_upload_accelerator import upload
from github_review_accelerator import _run_local_gate, review


class UploadTests(unittest.TestCase):
    def setUp(self):
        run_root = ROOT / ".project-local" / "runs" / "github-delivery-tests"
        run_root.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=run_root)
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.path)], check=True)
        subprocess.run(["git", "-C", str(self.path), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(self.path), "config", "user.email", "test@example.invalid"], check=True)
        (self.path / "tracked.txt").write_text("base", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.path), "add", "tracked.txt"], check=True)
        subprocess.run(["git", "-C", str(self.path), "commit", "-qm", "base"], check=True)
        subprocess.run(["git", "-C", str(self.path), "branch", "-M", "main"], check=True)
        self.lp = mock.patch("github_upload_accelerator.local_path", return_value=self.path)
        self.lp.start()
        self.addCleanup(self.lp.stop)

    def test_main_refuses_before_stage(self):
        (self.path / "tracked.txt").write_text("new", encoding="utf-8")
        r = upload("WORK-LAB", "fix: change", files=["tracked.txt"])
        self.assertEqual(r["status"], "BLOCKED_BRANCH")
        self.assertEqual(git(self.path, "diff", "--cached", "--name-only"), "")

    def test_failed_git_is_error_not_clean(self):
        def fail_status(path, *args):
            if args[0] == "status":
                raise RuntimeError("git status failed (exit 128): denied")
            return git(path, *args)
        with mock.patch("github_upload_accelerator.git", side_effect=fail_status):
            r = upload("WORK-LAB")
        self.assertEqual(r["status"], "ERROR")
        self.assertIn("git status failed", r["error"])

    def test_existing_stage_is_not_collected(self):
        subprocess.run(["git", "-C", str(self.path), "switch", "-qc", "codex/test"], check=True)
        (self.path / "tracked.txt").write_text("new", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.path), "add", "tracked.txt"], check=True)
        r = upload("WORK-LAB", "fix: change", files=["tracked.txt"])
        self.assertEqual(r["status"], "BLOCKED_STAGED")

    def test_unrelated_change_not_committed(self):
        subprocess.run(["git", "-C", str(self.path), "switch", "-qc", "codex/test"], check=True)
        (self.path / "tracked.txt").write_text("new", encoding="utf-8")
        (self.path / "other.txt").write_text("user", encoding="utf-8")
        r = upload("WORK-LAB", "fix: change", files=["tracked.txt"])
        self.assertEqual(r["status"], "DONE_LOCAL")
        self.assertEqual(git(self.path, "show", "--pretty=format:", "--name-only", "HEAD"), "tracked.txt")
        self.assertTrue((self.path / "other.txt").exists())

    def test_no_upstream_and_create_pr_requires_push(self):
        subprocess.run(["git", "-C", str(self.path), "switch", "-qc", "codex/test"], check=True)
        self.assertEqual(upload("WORK-LAB")["status"], "NO_UPSTREAM")
        self.assertEqual(upload("WORK-LAB", "fix: change", files=["tracked.txt"], create_pr=True)["status"], "BLOCKED_PR")

    def test_clean_with_unpushed_commit(self):
        bare_tmp = tempfile.TemporaryDirectory(dir=self.path.parent)
        self.addCleanup(bare_tmp.cleanup)
        bare = Path(bare_tmp.name)
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
        subprocess.run(["git", "-C", str(self.path), "remote", "add", "origin", str(bare)], check=True)
        subprocess.run(["git", "-C", str(self.path), "push", "-q", "-u", "origin", "main"], check=True)
        (self.path / "tracked.txt").write_text("later", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.path), "commit", "-qam", "later"], check=True)
        r = upload("WORK-LAB")
        self.assertEqual(r["status"], "UNPUSHED_COMMITS")
        self.assertEqual(r["ahead"], 1)

    def test_create_pr_returns_actual_url_with_mock_network(self):
        subprocess.run(["git", "-C", str(self.path), "switch", "-qc", "codex/test"], check=True)
        subprocess.run(["git", "-C", str(self.path), "update-ref", "refs/remotes/origin/main", "HEAD"], check=True)
        (self.path / "tracked.txt").write_text("new", encoding="utf-8")
        def fake_git(path, *args):
            return "" if args[0] == "push" else git(path, *args)
        with mock.patch("github_upload_accelerator.git", side_effect=fake_git), \
             mock.patch("github_upload_accelerator.request", return_value={"html_url": "https://github.com/DTALEX66/WORK-LAB/pull/99"}):
            r = upload("WORK-LAB", "fix: change", files=["tracked.txt"], push=True, create_pr=True)
        self.assertEqual(r["status"], "DONE_PUSHED")
        self.assertEqual(r["pr_url"], "https://github.com/DTALEX66/WORK-LAB/pull/99")

    def test_registry_identity_mismatch(self):
        with mock.patch("github_common.git", side_effect=[str(self.path), "git@github.com:someone/other.git", "git@github.com:DTALEX66/WORK-LAB.git"]):
            with self.assertRaisesRegex(ValueError, "origin does not match"):
                local_path({"local": "WORK-LAB", "root": str(self.path)})
        with mock.patch("github_common.git", side_effect=[str(self.path), "git@github.com:DTALEX66/WORK-LAB.git", "git@github.com:someone/other.git"]):
            with self.assertRaisesRegex(ValueError, "origin does not match"):
                local_path({"local": "WORK-LAB", "root": str(self.path)})

    def test_redaction(self):
        self.assertNotIn("abc123", redact("https://user:abc123@github.com/x"))
        self.assertNotIn("abc123", redact("Authorization: abc123"))
        self.assertNotIn("ghp_example123", redact("git error ghp_example123"))

    def test_git_timeout_is_structured(self):
        with mock.patch("github_common.subprocess.run", side_effect=subprocess.TimeoutExpired(["git"], 60)):
            with self.assertRaisesRegex(RuntimeError, "git status timed out"):
                git(self.path, "status", "--porcelain")


class ReviewTests(unittest.TestCase):
    def _pr(self):
        return {"head": {"sha": "abcdef"}, "base": {"ref": "main"},
                "mergeable": True, "mergeable_state": "clean"}

    @mock.patch("github_review_accelerator._run_local_gate", return_value={"applicable": False})
    @mock.patch("github_review_accelerator.request")
    def test_missing_pending_failed_checks(self, req, _gate):
        for state in (None, "in_progress", "failure"):
            req.side_effect = [self._pr(), [{"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "ci"}]}}],
                               {}, {"check_runs": [] if state is None else [{"name": "ci", "status": state if state == "in_progress" else "completed", "conclusion": state}]}]
            self.assertEqual(review("DTALEX66/WORK-LAB", 1)["recommendation"], "BLOCK")

    @mock.patch("github_review_accelerator._run_local_gate", return_value={"applicable": False})
    @mock.patch("github_review_accelerator.request")
    def test_unknown_required_policy(self, req, _gate):
        req.side_effect = [self._pr(), [], {}]
        self.assertEqual(review("DTALEX66/WORK-LAB", 1)["recommendation"], "UNKNOWN")

    @mock.patch("github_review_accelerator._run_local_gate", return_value={"applicable": False})
    @mock.patch("github_review_accelerator.request")
    def test_pagination(self, req, _gate):
        first = [{"name": f"extra-{i}", "status": "completed", "conclusion": "success"} for i in range(100)]
        second = [{"name": "ci", "status": "completed", "conclusion": "success", "head_sha": "abcdef"}]
        req.side_effect = [self._pr(), [{"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "ci"}]}}],
                           {}, {"check_runs": first}, {"check_runs": second}]
        self.assertEqual(review("DTALEX66/WORK-LAB", 1)["recommendation"], "APPROVE")

    @mock.patch("github_review_accelerator._run_local_gate", return_value={"applicable": False})
    @mock.patch("github_review_accelerator.request")
    def test_required_rule_on_later_page(self, req, _gate):
        required_rule = {"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "ci"}]}}
        req.side_effect = [self._pr(), [{"type": "non_fast_forward"}] * 100,
                           [required_rule], {}, {"check_runs": []}]
        self.assertEqual(review("DTALEX66/WORK-LAB", 1)["recommendation"], "BLOCK")

    @mock.patch("github_review_accelerator._run_local_gate", return_value={"applicable": False})
    @mock.patch("github_review_accelerator.request")
    def test_duplicate_success_cannot_hide_pending(self, req, _gate):
        required_rule = {"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "ci"}]}}
        req.side_effect = [self._pr(), [required_rule], {}, {"check_runs": [
            {"name": "ci", "status": "in_progress", "conclusion": None},
            {"name": "ci", "status": "completed", "conclusion": "success"},
        ]}]
        self.assertEqual(review("DTALEX66/WORK-LAB", 1)["recommendation"], "BLOCK")

    @mock.patch("github_review_accelerator.subprocess.run")
    def test_local_gate_path_cwd_and_exit(self, run):
        run.return_value = mock.Mock(returncode=1, stdout="QUALITY_GATE_PASS", stderr="")
        result = _run_local_gate("DTALEX66/WORK-LAB")
        self.assertFalse(result["passed"])
        args, kwargs = run.call_args
        self.assertEqual(kwargs["cwd"], ROOT)
        self.assertEqual(Path(args[0][1]), ROOT / "services/orchestration/run_quality_gate.py")


if __name__ == "__main__":
    unittest.main()
