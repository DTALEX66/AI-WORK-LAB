"""Synthetic quota-exhaustion tests: no unapproved paid fallback.

Why this file exists
--------------------
The historical incident was a real account hit: `--ignore-user-config` made the
runtime fall back to a built-in `openrouter` route and the provider refused the
request with HTTP 402. The package asks for a **synthetic** quota test precisely
so this class is covered without spending real quota again.

The classifier's documented evidence hierarchy is **exit code > structured > text**
(`hermes_task_result.classify` docstring). These tests assert the consequences of
that hierarchy rather than an imaginary one, and one of them pins a deliberate
ordering choice so the residual risk is visible instead of hidden.

What is asserted, and what is deliberately NOT
----------------------------------------------
Asserted: a text-visible quota exhaustion is a terminal FAILURE that can never be
reported as success; it is not a retry event; and the managed launch path still
refuses the exact flag that produced the historical paid fallback.

NOT asserted: that the upstream runtime has no paid path at all. That is not
provable from here and must not be claimed. The machine-level fact that no fallback
chain is configured (`fallback_providers == []` on both profiles) is recorded as
live evidence in H2, not as a unit test.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT_MODULE = ROOT / "integrations/executors/hermes" / "hermes_task_result.py"
POLICY_MODULE = ROOT / "integrations/executors/hermes" / "managed_launch_policy.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The runtime's own wording for this class; captured without any account data.
QUOTA_TEXT = "Billing or credits exhausted. Top up or switch to a free model."
CALIBRATED = "0.21.2"


class SyntheticQuotaTerminalFailureTests(unittest.TestCase):
    """Quota exhaustion visible in the output is terminal, never success."""

    def setUp(self) -> None:
        self.m = load("hermes_task_result_quota", RESULT_MODULE)

    def test_quota_exhaustion_with_zero_exit_is_a_failure(self) -> None:
        result = self.m.classify(exit_code=0, stdout=QUOTA_TEXT, runtime_version=CALIBRATED)
        self.assertEqual(result["outcome"], self.m.FAILURE)
        self.assertFalse(self.m.is_success(result))
        # the specific class is reported in evidence; `reason` stays the generic
        # text-level reason, which is the module's existing contract
        self.assertIn("terminal_error:billing_or_credits_exhausted", result["evidence"])

    def test_quota_exhaustion_is_not_signed_success_by_acceptance_alone(self) -> None:
        result = self.m.classify(
            exit_code=0, stdout=QUOTA_TEXT, acceptance_passed=True, runtime_version=CALIBRATED
        )
        self.assertEqual(result["outcome"], self.m.FAILURE)

    def test_nonzero_exit_outranks_the_quota_classification(self) -> None:
        result = self.m.classify(exit_code=2, stdout=QUOTA_TEXT, runtime_version=CALIBRATED)
        self.assertEqual(result["outcome"], self.m.FAILURE)
        self.assertEqual(result["reason"], "process_exit_nonzero")

    def test_uncalibrated_runtime_cannot_turn_quota_into_success(self) -> None:
        result = self.m.classify(exit_code=0, stdout=QUOTA_TEXT)
        self.assertNotEqual(result["outcome"], self.m.SUCCESS)

    def test_quota_exhaustion_is_terminal_and_not_a_retry_event(self) -> None:
        terminal = dict(self.m.TERMINAL_FAILURE_PATTERNS)
        retry = dict(self.m.RETRY_EVENT_PATTERNS)
        self.assertIn("billing_or_credits_exhausted", terminal)
        self.assertNotIn("billing_or_credits_exhausted", retry)

    def test_structured_failure_evidence_is_also_terminal(self) -> None:
        result = self.m.classify(
            exit_code=0,
            stdout=QUOTA_TEXT,
            structured={"status": "error", "error": "quota"},
            acceptance_passed=True,
            runtime_version=CALIBRATED,
        )
        self.assertEqual(result["outcome"], self.m.FAILURE)
        self.assertEqual(result["reason"], "structured_failure")


class TerminalEvidenceOutranksStructuredSuccessTests(unittest.TestCase):
    """A literal terminal failure marker outranks a structured success claim.

    The documented hierarchy is exit code > structured > text, but before this was
    fixed a structured payload claiming success, together with a passed acceptance
    check, was signed SUCCESS even when the output carried "Billing or credits
    exhausted" — and the terminal marker did not even appear in `evidence`. That is
    the same mistake as trusting the exit code alone, one level up: an unambiguous
    abort marker was overridden by a weaker, self-reported claim.

    The fix consults the literal terminal patterns before signing a structured
    success. It can only withdraw an unwarranted SUCCESS, never create one, and the
    normal structured success path is covered below so the hierarchy still holds
    where no terminal marker is present.
    """

    def setUp(self) -> None:
        self.m = load("hermes_task_result_hierarchy", RESULT_MODULE)

    def test_terminal_text_overrides_a_structured_success_claim(self) -> None:
        result = self.m.classify(
            exit_code=0,
            stdout=QUOTA_TEXT,
            structured={"status": "completed", "success": True},
            acceptance_passed=True,
            runtime_version=CALIBRATED,
        )
        self.assertEqual(result["outcome"], self.m.FAILURE)
        self.assertFalse(self.m.is_success(result))
        self.assertIn("terminal_error:billing_or_credits_exhausted", result["evidence"])

    def test_terminal_text_also_blocks_structured_success_without_acceptance(self) -> None:
        result = self.m.classify(
            exit_code=0,
            stdout=QUOTA_TEXT,
            structured={"status": "completed", "success": True},
            runtime_version=CALIBRATED,
        )
        self.assertEqual(result["outcome"], self.m.FAILURE)

    def test_structured_success_still_wins_when_no_terminal_marker_is_present(self) -> None:
        result = self.m.classify(
            exit_code=0,
            stdout="all good",
            structured={"status": "completed", "success": True},
            acceptance_passed=True,
            runtime_version=CALIBRATED,
        )
        self.assertEqual(result["outcome"], self.m.SUCCESS)
        self.assertEqual(result["reason"], "structured_success_and_acceptance_passed")

    def test_structured_success_without_acceptance_is_still_only_unknown(self) -> None:
        result = self.m.classify(
            exit_code=0,
            stdout="all good",
            structured={"status": "completed", "success": True},
            runtime_version=CALIBRATED,
        )
        self.assertEqual(result["outcome"], self.m.UNKNOWN)


class HistoricalPaidFallbackVectorTests(unittest.TestCase):
    """The exact flag that produced the real 402 stays refused on our launch path."""

    def setUp(self) -> None:
        self.policy = load("managed_launch_policy_quota", POLICY_MODULE)

    def test_managed_launch_refuses_the_historical_paid_fallback_vector(self) -> None:
        for argv in (
            ["hermes", "chat", "-q", "probe", "--ignore-user-config"],
            ["hermes", "chat", "-q", "probe", "--ignore-user-config=true"],
        ):
            with self.subTest(argv=argv):
                with self.assertRaises(Exception):
                    self.policy.assert_managed_argv(argv, what="quota_synthetic")

    def test_a_managed_launch_without_the_flag_is_accepted(self) -> None:
        self.policy.assert_managed_argv(
            ["hermes", "chat", "-q", "probe", "--oneshot", "--max-turns", "3"],
            what="quota_synthetic",
        )


if __name__ == "__main__":
    unittest.main()
