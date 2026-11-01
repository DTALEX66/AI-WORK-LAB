from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "packages/client-neutral-core/scripts" / "ci_watcher.py"
spec = importlib.util.spec_from_file_location("ci_watcher", SCRIPT)
assert spec and spec.loader
watcher = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = watcher
spec.loader.exec_module(watcher)


class CIWatcherTests(unittest.TestCase):
    def test_missing_exact_sha_is_queued_no_job(self):
        state, details = watcher.classify_runs([], ("work-lab-gate",), "sha")
        self.assertEqual(state, "QUEUED_NO_JOB")
        self.assertEqual(details["workflow"], "work-lab-gate")

    def test_active_run_is_running(self):
        state, _ = watcher.classify_runs([{"workflowName": "work-lab-gate", "headSha": "sha", "status": "in_progress", "runAttempt": 1}], ("work-lab-gate",), "sha")
        self.assertEqual(state, "RUNNING")

    def test_success_requires_all_workflows(self):
        runs = [
            {"workflowName": "work-lab-gate", "headSha": "sha", "status": "completed", "conclusion": "success", "runAttempt": 1},
            {"workflowName": "secondary", "headSha": "sha", "status": "completed", "conclusion": "success", "runAttempt": 1},
        ]
        state, _ = watcher.classify_runs(runs, ("work-lab-gate", "secondary"), "sha")
        self.assertEqual(state, "SUCCEEDED")

    def test_cancelled_is_infrastructure_failure(self):
        runs = [{"workflowName": "work-lab-gate", "headSha": "sha", "status": "completed", "conclusion": "cancelled", "runAttempt": 1}]
        state, _ = watcher.classify_runs(runs, ("work-lab-gate",), "sha")
        self.assertEqual(state, "FAILED_INFRASTRUCTURE")

    def test_rate_limit_honours_retry_after(self):
        state, retry_after = watcher.classify_error("HTTP 429 rate limit; Retry-After: 77")
        self.assertEqual(state, "CI_RATE_LIMITED")
        self.assertEqual(retry_after, 77)
        self.assertEqual(watcher.WatcherPolicy().delay(4, retry_after), 77)

    def test_platform_error_is_deferred_with_next_observation(self):
        observed = datetime(2026, 8, 7, tzinfo=timezone.utc)
        payload = watcher.make_observation("repo", "sha", "PLATFORM_OUTAGE", message="outage", observation_index=2, observed_at=observed)
        self.assertEqual(payload["state"], "PLATFORM_OUTAGE")
        self.assertEqual(payload["next_observation_at"], "2026-08-07T00:00:24Z")

    def test_no_workflow_identity_is_blocked(self):
        state, details = watcher.classify_runs([], (), "sha")
        self.assertEqual(state, "BLOCKED")
        self.assertIn("no required", details["message"])

    def test_cli_fixture_emits_schema_shaped_observation(self):
        with tempfile.TemporaryDirectory() as temp:
            runs = Path(temp) / "runs.json"
            runs.write_text(json.dumps([{"workflowName": "work-lab-gate", "headSha": "sha", "status": "completed", "conclusion": "success", "runAttempt": 1}]), encoding="utf-8")
            output = Path(temp) / "github-output.txt"
            observation_path = Path(temp) / "runtime" / "ci-observation.json"
            code = watcher.main(["--repository", "repo", "--commit", "sha", "--workflow", "work-lab-gate", "--runs-json", str(runs), "--github-output", str(output), "--observation-path", str(observation_path)])
            self.assertEqual(code, 0)
            payload = json.loads(output.read_text(encoding="utf-8").split("observation_json<<WORK_LAB_CI_OBSERVATION\n", 1)[1].split("\nWORK_LAB_CI_OBSERVATION", 1)[0])
            self.assertEqual(payload["state"], "SUCCEEDED")
            self.assertEqual(payload["schema_version"], "workflow/ci-observation/v1")
            self.assertEqual(json.loads(observation_path.read_text(encoding="utf-8"))["state"], "SUCCEEDED")


if __name__ == "__main__":
    unittest.main()
