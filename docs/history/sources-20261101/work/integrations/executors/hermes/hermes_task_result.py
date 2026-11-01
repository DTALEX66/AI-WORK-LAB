"""Hermes task-result classification for WORK-LAB-managed runs (review finding A-2).

Why this exists
---------------
Hermes 0.21.2 returns **exit code 0** for a task that failed and for a task that
aborted on a non-retryable provider error. The transcript says so; the process
status does not. Any automation that keys on the exit code would record a failed
task as a success.

Decision rules (from the ruling)
--------------------------------
* non-zero process exit                                        -> FAILURE
* exit 0 but an explicit task/provider error is present         -> FAILURE
* exit 0 with no completion evidence                            -> UNKNOWN
* only task-specific acceptance passing                         -> SUCCESS

Preference order: a native structured result wins. This version does not expose
one for ``hermes chat --oneshot``, so a **version-pinned** text detector is used
as a documented, explicitly temporary compensation. The pin is part of the
contract: if ``HERMES_CALIBRATED_VERSION`` no longer matches the runtime, the
text detector is not trustworthy and results degrade to UNKNOWN.

Two further rules that prevent false verdicts:

* A marker in the output is **not** proof of success - the model can emit a
  success token and then fail a tool call. Success requires task-specific
  acceptance to have passed *and* the absence of failure/incomplete markers.
* Auxiliary failures (e.g. title generation) are recorded, never decisive. A
  failed subtitle does not make the task a failure.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

HERMES_CALIBRATED_VERSION = "0.21.2"

SUCCESS = "SUCCESS"
FAILURE = "FAILURE"
UNKNOWN = "UNKNOWN"

# Terminal, main-path task/provider errors: the run cannot have produced a valid
# answer after one of these.
TERMINAL_FAILURE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("api_retries_exhausted", r"API failed after \d+ retries"),
    ("final_error", r"^\s*Final error:"),
    ("non_retryable_client_error", r"Non-retryable client error \(HTTP \d+\)"),
    ("non_retryable_error", r"Non-retryable error \(HTTP \d+\)"),
    ("billing_or_credits_exhausted", r"Billing or credits exhausted"),
)

# A single failed attempt that the runtime then retried. On its own this does NOT
# establish that the task failed - retrying can recover - and it does not
# establish that it succeeded either. Text alone cannot tell the two apart, so
# without acceptance evidence the outcome is indeterminate.
RETRY_EVENT_PATTERNS: tuple[tuple[str, str], ...] = (
    ("api_call_failed_attempt", r"API call failed \(attempt \d+/\d+\)"),
)

# Kept for source compatibility with the previous revision.
FAILURE_PATTERNS = TERMINAL_FAILURE_PATTERNS + RETRY_EVENT_PATTERNS

# Recorded for the report but deliberately NOT decisive.
AUXILIARY_FAILURE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("auxiliary_title_generation_failed", r"Auxiliary title generation failed"),
)

# The runtime itself says the answer may be incomplete.
INCOMPLETE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("iteration_budget_reached", r"Iteration budget reached"),
    ("response_may_be_incomplete", r"response may be incomplete"),
)


def _matches(text: str, patterns: Iterable[tuple[str, str]]) -> list[str]:
    hits = []
    for name, pattern in patterns:
        if re.search(pattern, text, re.MULTILINE):
            hits.append(name)
    return hits


def classify(
    *,
    exit_code: int,
    stdout: str = "",
    stderr: str = "",
    acceptance_passed: bool | None = None,
    runtime_version: str | None = None,
    structured: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify one managed run.

    ``acceptance_passed`` is the task-specific acceptance result. ``None`` means
    it was not evaluated, which can never yield SUCCESS.

    Ordering matters and is deliberate:

    1. **Process status first.** A non-zero exit is a failure whatever a
       structured payload claims; a structured "completed" must not override it.
    2. **Structured result, only for exit 0.** An internally contradictory
       payload (``success`` together with an error status or a non-empty
       ``error``) is not signed as success.
    3. **Text fallback, only with a stated calibrated version.** Omitting
       ``runtime_version`` no longer assumes the calibrated one.
    4. Retry events are separated from terminal errors: a retried attempt that
       then succeeded is not a failure, and text alone cannot prove recovery, so
       an unproven retry outcome is UNKNOWN rather than either verdict.
    """

    evidence: list[str] = []
    text = f"{stdout}\n{stderr}"

    # 1. process status is authoritative
    if exit_code != 0:
        return {
            "outcome": FAILURE,
            "reason": "process_exit_nonzero",
            "source": "exit_code",
            "evidence": [f"exit_code={exit_code}"],
        }

    # 2. a native structured result, when the runtime provides one
    if structured is not None:
        status = str(structured.get("status") or structured.get("outcome") or "").upper()
        error = structured.get("error")
        claims_success = structured.get("success") is True or status in {"SUCCESS", "COMPLETED", "OK"}
        claims_failure = status in {"ERROR", "FAILED", "FAILURE", "ABORTED"} or bool(error)
        if claims_success and claims_failure:
            return {
                "outcome": UNKNOWN,
                "reason": "structured_result_conflict",
                "source": "structured",
                "evidence": [
                    f"structured status={status} success={structured.get('success')} error={error}",
                    "a contradictory structured result is not signed as success",
                ],
            }
        if claims_success:
            # A literal terminal failure marker in the output outranks a structured
            # success claim. The payload is the native result, but "Billing or credits
            # exhausted", "Final error:" or an exhausted retry chain is evidence that
            # the run aborted; signing that as success would be the same mistake as
            # trusting the exit code alone, one level up. These patterns are literal
            # runtime strings rather than calibrated prose detectors, so they are not
            # gated behind runtime_version, and the check can only ever withdraw an
            # unwarranted SUCCESS - it never manufactures one.
            terminal_in_text = _matches(text, TERMINAL_FAILURE_PATTERNS)
            if terminal_in_text:
                return {
                    "outcome": FAILURE,
                    "reason": "native_task_error",
                    "source": "text",
                    "evidence": [
                        f"structured status={status} claimed success but the output carries a terminal error",
                        *(f"terminal_error:{name}" for name in terminal_in_text),
                    ],
                }
            if acceptance_passed is True:
                return {
                    "outcome": SUCCESS,
                    "reason": "structured_success_and_acceptance_passed",
                    "source": "structured",
                    "evidence": ["structured status=" + status],
                }
            return {
                "outcome": UNKNOWN,
                "reason": "structured_success_without_acceptance",
                "source": "structured",
                "evidence": ["acceptance not evaluated"],
            }
        return {
            "outcome": FAILURE,
            "reason": "structured_failure",
            "source": "structured",
            "evidence": [f"structured status={status} error={error}"],
        }

    # 3. the text path requires an explicitly stated, calibrated version
    if runtime_version is None:
        return {
            "outcome": UNKNOWN,
            "reason": "runtime_version_required",
            "source": "text",
            "evidence": [
                f"no runtime_version supplied; the text detector is only valid for "
                f"{HERMES_CALIBRATED_VERSION} and is not assumed",
            ],
        }
    if runtime_version != HERMES_CALIBRATED_VERSION:
        return {
            "outcome": UNKNOWN,
            "reason": "text_detector_not_calibrated",
            "source": "text",
            "evidence": [
                f"text detector not calibrated for runtime {runtime_version} "
                f"(calibrated for {HERMES_CALIBRATED_VERSION}); degrading to UNKNOWN"
            ],
        }

    terminal = _matches(text, TERMINAL_FAILURE_PATTERNS)
    retries = _matches(text, RETRY_EVENT_PATTERNS)
    incomplete = _matches(text, INCOMPLETE_PATTERNS)
    auxiliary = _matches(text, AUXILIARY_FAILURE_PATTERNS)
    evidence.extend(f"terminal_error:{name}" for name in terminal)
    evidence.extend(f"retry_event:{name} (not terminal on its own)" for name in retries)
    evidence.extend(f"incomplete:{name}" for name in incomplete)
    evidence.extend(f"auxiliary_error:{name} (not decisive)" for name in auxiliary)

    if terminal:
        return {"outcome": FAILURE, "reason": "native_task_error", "source": "text", "evidence": evidence}

    if retries:
        # A retry happened. Acceptance is the only evidence that it recovered.
        if acceptance_passed is True and not incomplete:
            return {
                "outcome": SUCCESS,
                "reason": "recovered_after_retry",
                "source": "acceptance",
                "evidence": evidence,
            }
        return {
            "outcome": UNKNOWN,
            "reason": "retry_outcome_indeterminate",
            "source": "text",
            "evidence": evidence,
        }

    if incomplete and acceptance_passed is not True:
        return {"outcome": UNKNOWN, "reason": "incomplete_output", "source": "text", "evidence": evidence}

    if acceptance_passed is True:
        return {
            "outcome": SUCCESS,
            "reason": "acceptance_passed_without_failure_markers",
            "source": "acceptance",
            "evidence": evidence,
        }

    return {"outcome": UNKNOWN, "reason": "no_completion_evidence", "source": "text", "evidence": evidence}


def is_success(result: Mapping[str, Any]) -> bool:
    """Only an explicit SUCCESS is a success; UNKNOWN never is."""

    return result.get("outcome") == SUCCESS
