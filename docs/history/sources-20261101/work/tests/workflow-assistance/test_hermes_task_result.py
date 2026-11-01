"""Regression tests for the A-2 result classifier and the A-3 launch policy.

The three regression classes the ruling asked for are covered explicitly:
normal completion, explicit failure with exit 0, and incomplete output. No real
paid request is made: the fixtures are the de-identified transcripts captured in
this package plus synthetic variants.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
RESULT_MODULE = ROOT / "integrations/executors/hermes" / "hermes_task_result.py"
POLICY_MODULE = ROOT / "integrations/executors/hermes" / "managed_launch_policy.py"
SWITCH_MODEL = ROOT / "integrations/executors/hermes" / "switch_model.py"
DOCTOR = ROOT / "integrations/executors/hermes" / "hermes_workflow_doctor.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# De-identified excerpts of the transcripts this package actually captured.
NORMAL_COMPLETION = """
Query: Do not use any tools. Reply with exactly this token and nothing else: WL-LAYER-SMOKE-20260914
WL-LAYER-SMOKE-20260914

Session:        20260914_201308_b3b782
Duration:       13s
Messages:       2 (1 user, 0 tool calls)
"""

EXPLICIT_FAILURE_EXIT_ZERO = """
Query: Do not use any tools. Reply with OK.
Auxiliary title generation failed: HTTP 503: No available channel for model X
API call failed (attempt 1/3): InternalServerError [HTTP 503]
API call failed (attempt 2/3): InternalServerError [HTTP 503]
API call failed (attempt 3/3): InternalServerError [HTTP 503]
API failed after 3 retries - HTTP 503
   Final error: HTTP 503
Iteration budget reached (1/1) - response may be incomplete

Session:        20260914_203802_853d1b
Duration:       17s
Messages:       1 (1 user, 0 tool calls)
"""

INCOMPLETE_OUTPUT = """
Query: count to 500
1
2
3
Iteration budget reached (1/1) - response may be incomplete

Session:        20260914_20xxxx_aaaaaa
"""

BILLING_ABORT_EXIT_ZERO = """
Provider: openrouter  Model: z-ai/glm-5.2
API call failed (attempt 1/3): APIStatusError [HTTP 402]
Non-retryable client error (HTTP 402). Aborting.
Billing or credits exhausted: HTTP 402
"""


class TaskResultClassifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = load("hermes_task_result", RESULT_MODULE)

    def test_normal_completion_with_acceptance_is_success(self) -> None:
        verdict = self.result.classify(
            exit_code=0, stdout=NORMAL_COMPLETION, acceptance_passed=True, runtime_version="0.21.2"
        )
        self.assertEqual(verdict["outcome"], "SUCCESS")
        self.assertTrue(self.result.is_success(verdict))

    def test_normal_completion_without_acceptance_is_unknown(self) -> None:
        """Exit 0 alone is never success."""
        verdict = self.result.classify(exit_code=0, stdout=NORMAL_COMPLETION, runtime_version="0.21.2")
        self.assertEqual(verdict["outcome"], "UNKNOWN")
        self.assertFalse(self.result.is_success(verdict))

    def test_explicit_task_error_with_exit_zero_is_failure(self) -> None:
        verdict = self.result.classify(
            exit_code=0, stdout=EXPLICIT_FAILURE_EXIT_ZERO, acceptance_passed=True, runtime_version="0.21.2"
        )
        self.assertEqual(verdict["outcome"], "FAILURE")
        self.assertEqual(verdict["reason"], "native_task_error")
        self.assertFalse(self.result.is_success(verdict))

    def test_billing_abort_with_exit_zero_is_failure(self) -> None:
        verdict = self.result.classify(
            exit_code=0, stdout=BILLING_ABORT_EXIT_ZERO, acceptance_passed=True, runtime_version="0.21.2"
        )
        self.assertEqual(verdict["outcome"], "FAILURE")

    def test_nonzero_exit_is_failure_regardless_of_text(self) -> None:
        verdict = self.result.classify(exit_code=1, stdout="looks fine", acceptance_passed=True)
        self.assertEqual(verdict["outcome"], "FAILURE")
        self.assertEqual(verdict["reason"], "process_exit_nonzero")

    def test_incomplete_output_is_not_success(self) -> None:
        verdict = self.result.classify(exit_code=0, stdout=INCOMPLETE_OUTPUT, runtime_version="0.21.2")
        self.assertEqual(verdict["outcome"], "UNKNOWN")
        self.assertEqual(verdict["reason"], "incomplete_output")

    def test_auxiliary_failure_alone_is_not_decisive(self) -> None:
        text = "Auxiliary title generation failed: HTTP 503\nanswer text\n"
        verdict = self.result.classify(
            exit_code=0, stdout=text, acceptance_passed=True, runtime_version="0.21.2"
        )
        self.assertEqual(verdict["outcome"], "SUCCESS")
        self.assertTrue(any("auxiliary_error" in item for item in verdict["evidence"]))

    def test_uncalibrated_runtime_degrades_to_unknown(self) -> None:
        """The text detector is a version-pinned compensation, not an assumption."""
        verdict = self.result.classify(
            exit_code=0, stdout=NORMAL_COMPLETION, acceptance_passed=True, runtime_version="9.9.9"
        )
        self.assertEqual(verdict["outcome"], "UNKNOWN")
        self.assertEqual(verdict["reason"], "text_detector_not_calibrated")

    def test_structured_success_needs_acceptance(self) -> None:
        ok = self.result.classify(
            exit_code=0, structured={"status": "completed"}, acceptance_passed=True
        )
        self.assertEqual(ok["outcome"], "SUCCESS")
        weak = self.result.classify(exit_code=0, structured={"status": "completed"})
        self.assertEqual(weak["outcome"], "UNKNOWN")
        bad = self.result.classify(exit_code=0, structured={"status": "error", "error": "boom"})
        self.assertEqual(bad["outcome"], "FAILURE")

    def test_success_marker_alone_cannot_rescue_a_failure(self) -> None:
        """The model can emit a success token and then fail; the marker is not authoritative."""
        text = "WL-LAYER-SMOKE-20260914\nAPI failed after 3 retries - HTTP 503\n"
        verdict = self.result.classify(
            exit_code=0, stdout=text, acceptance_passed=True, runtime_version="0.21.2"
        )
        self.assertEqual(verdict["outcome"], "FAILURE")

    # ------------------------------------------------------------------ #
    # Counter-examples supplied by the independent review (H1)
    # ------------------------------------------------------------------ #
    def test_h1_nonzero_exit_outranks_a_completed_structured_status(self) -> None:
        verdict = self.result.classify(
            exit_code=1,
            structured={"status": "completed"},
            acceptance_passed=True,
        )
        self.assertEqual(verdict["outcome"], "FAILURE")
        self.assertEqual(verdict["reason"], "process_exit_nonzero")

    def test_h1_contradictory_structured_result_is_not_success(self) -> None:
        verdict = self.result.classify(
            exit_code=0,
            structured={"success": True, "status": "error", "error": "provider exploded"},
            acceptance_passed=True,
        )
        self.assertNotEqual(verdict["outcome"], "SUCCESS")
        self.assertEqual(verdict["reason"], "structured_result_conflict")

    def test_h1_missing_runtime_version_is_not_assumed_calibrated(self) -> None:
        verdict = self.result.classify(exit_code=0, stdout=NORMAL_COMPLETION, acceptance_passed=True)
        self.assertEqual(verdict["outcome"], "UNKNOWN")
        self.assertEqual(verdict["reason"], "runtime_version_required")

    def test_h1_retry_that_recovered_is_not_a_terminal_failure(self) -> None:
        text = (
            "API call failed (attempt 1/3): InternalServerError [HTTP 503]\n"
            "Retrying in 2.8s (attempt 1/3)...\n"
            "answer text\n"
        )
        recovered = self.result.classify(
            exit_code=0, stdout=text, acceptance_passed=True, runtime_version="0.21.2"
        )
        self.assertEqual(recovered["outcome"], "SUCCESS")
        self.assertEqual(recovered["reason"], "recovered_after_retry")
        # the same retry without acceptance evidence cannot be resolved from text
        indeterminate = self.result.classify(exit_code=0, stdout=text, runtime_version="0.21.2")
        self.assertEqual(indeterminate["outcome"], "UNKNOWN")
        self.assertEqual(indeterminate["reason"], "retry_outcome_indeterminate")
        # and a retry followed by a terminal error is still a failure
        terminal = self.result.classify(
            exit_code=0,
            stdout=text + "API failed after 3 retries - HTTP 503\n",
            acceptance_passed=True,
            runtime_version="0.21.2",
        )
        self.assertEqual(terminal["outcome"], "FAILURE")


class ManagedLaunchPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = load("managed_launch_policy", POLICY_MODULE)

    def test_ignore_user_config_is_refused_for_managed_launches(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "MANAGED_LAUNCH_REFUSED"):
            self.policy.assert_managed_argv(
                ["hermes", "chat", "-q", "x", "--oneshot", "--ignore-user-config"]
            )

    def test_equals_spelling_is_also_refused(self) -> None:
        self.assertEqual(self.policy.forbidden_flags(["--ignore-user-config=true"]), ["--ignore-user-config"])

    def test_approved_flags_pass(self) -> None:
        self.policy.assert_managed_argv(["hermes", "chat", "-q", "x", "--oneshot", "--max-turns", "1"])
        self.assertEqual(self.policy.forbidden_flags(["hermes", "doctor"]), [])

    def test_policy_states_its_scope(self) -> None:
        described = self.policy.describe_policy()
        self.assertIn("manual commands are outside this policy", described["scope"])
        self.assertIn("--ignore-user-config", described["forbidden"])


class ManagedEntryWiringTests(unittest.TestCase):
    """H2: the A-2/A-3 modules must be reachable from a real managed entry.

    A fake process executor is used, so no real Hermes process and no provider
    account is touched.
    """

    def setUp(self) -> None:
        self.switch = load("switch_model", SWITCH_MODEL)
        self.doctor = load("hermes_workflow_doctor", DOCTOR)

    def test_switch_model_entry_rejects_the_forbidden_flag_before_start(self) -> None:
        calls: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            calls.append(list(cmd))
            return SimpleNamespace(returncode=0, stdout="")

        with mock.patch.object(self.switch, "subprocess", SimpleNamespace(run=fake_run, PIPE=-1, STDOUT=-2)):
            with self.assertRaisesRegex(RuntimeError, "MANAGED_LAUNCH_REFUSED"):
                self.switch.run(["hermes", "chat", "-q", "x", "--oneshot", "--ignore-user-config"])
        self.assertEqual(calls, [], "the process must not be created at all")

    def test_doctor_entry_rejects_the_forbidden_flag_before_start(self) -> None:
        calls: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            calls.append(list(cmd))
            return SimpleNamespace(returncode=0, stdout="")

        with mock.patch.object(self.doctor.subprocess, "run", fake_run):
            with self.assertRaisesRegex(RuntimeError, "MANAGED_LAUNCH_REFUSED"):
                self.doctor.run(["hermes", "chat", "-q", "x", "--ignore-user-config"])
        self.assertEqual(calls, [], "the process must not be created at all")

    def test_approved_argv_reaches_the_executor(self) -> None:
        calls: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            calls.append(list(cmd))
            return SimpleNamespace(returncode=0, stdout="ok")

        with mock.patch.object(self.switch, "subprocess", SimpleNamespace(run=fake_run, PIPE=-1, STDOUT=-2)):
            self.switch.run(["hermes", "doctor"])
        self.assertEqual(calls, [["hermes", "doctor"]])

    def test_live_marker_outcome_is_not_promoted_from_failure_or_unknown(self) -> None:
        """Failure and UNKNOWN must not be reported as LIVE_OK.

        The transcripts are the de-identified ones captured by this package: the
        runtime returns exit 0 for an aborted provider call.
        """
        marker = "OK_MARKER_XYZ"
        cases = [
            ("explicit failure with exit 0", (0, "API failed after 3 retries - HTTP 503\n"), False),
            ("no completion evidence", (0, "some unrelated output\n"), False),
            ("non-zero exit", (1, f"{marker}\n"), False),
            ("clean completion", (0, f"{marker}\n"), True),
        ]
        for label, (code, output), should_pass in cases:
            def fake_run(cmd, **kwargs):
                if "--version" in cmd:
                    return SimpleNamespace(returncode=0, stdout="Hermes Agent v0.21.2 (2026.9.11)\n")
                return SimpleNamespace(returncode=code, stdout=output)

            self.switch._RUNTIME_VERSION.clear()
            with mock.patch.object(self.switch, "subprocess", SimpleNamespace(run=fake_run, PIPE=-1, STDOUT=-2)):
                if should_pass:
                    with mock.patch("builtins.print") as printed:
                        self.switch.live_marker("provider", "model", marker)
                    self.assertTrue(
                        any("LIVE_OK" in str(call) for call in printed.call_args_list), label
                    )
                else:
                    with self.assertRaises(SystemExit) as ctx:
                        self.switch.live_marker("provider", "model", marker)
                    self.assertIn("not successful", str(ctx.exception), label)

    def test_version_lookup_is_read_from_the_runtime(self) -> None:
        def fake_run(cmd, **kwargs):
            return SimpleNamespace(returncode=0, stdout="Hermes Agent v0.21.2 (2026.9.11) 路 upstream abc\n")

        self.switch._RUNTIME_VERSION.clear()
        with mock.patch.object(self.switch, "subprocess", SimpleNamespace(run=fake_run, PIPE=-1, STDOUT=-2)):
            self.assertEqual(self.switch.hermes_runtime_version(), "0.21.2")


if __name__ == "__main__":
    unittest.main()

