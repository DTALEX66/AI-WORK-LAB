"""Gate: every verifier CI runs must have a local route, and this file is that route for eight of them.

The class of defect: `scripts/ci/verify_blueprint_coverage.py` ran only in the integration job, so the
branch was red at two pushed heads while the canonical local gate printed PASS on the same tree. A rule
a writer cannot run is a rule that honest edits break. This module is discovered by the root governance
batch, so the checks below now run in every local `verify` as well as in CI.

Two assertions, deliberately separated:
  REACHABLE  -- scripts/ci/verify_ci_check_reachability.py must say no CI-only rule survived;
  VERIFIED   -- each named verifier is actually executed here and must exit 0 on its own verdict line.

The generated TypeScript projection is checked by regenerating and comparing, then restoring the
committed bytes: the committed file is the evidence, so a test that left a mutation behind would be
reporting on its own side effect.
"""
from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "ci"))

import verify_ci_check_reachability as reach  # noqa: E402

# CI invokes each of these with no arguments; they are pure verdicts over tracked files, so they run
# identically here. A new workflow step that names a verifier no local route reaches must be added
# here or be declared in the reachability checker with a measured reason -- the reachability assertion
# below is what makes that choice unavoidable.
VERIFIERS = (
    "scripts/ci/verify_cross_module_source_index.py",
    "scripts/ci/verify_future_candidate_registry.py",
    "scripts/ci/verify_observer_readonly.py",
    "scripts/ci/verify_regression_report.py",
    "scripts/ci/verify_skill_mcp_consistency.py",
    "scripts/ci/verify_source_governance.py",
    "scripts/ci/verify_source_health.py",
    "scripts/ci/verify_wl_inheritance_matrix.py",
)
VERDICT = re.compile(r"^[A-Z][A-Z0-9_]*_(PASS|FAIL)\b", re.M)


class CiInvokedVerifiers(unittest.TestCase):
    def run_verifier(self, script: str) -> tuple[int, str]:
        proc = subprocess.run([sys.executable, script], cwd=REPO, capture_output=True)
        return proc.returncode, (proc.stdout + proc.stderr).decode("utf-8", "replace")

    def test_the_list_covers_scripts_ci_verifiers_ci_runs_alone(self) -> None:
        """An empty list would make this module a green nothing."""
        self.assertGreaterEqual(len(VERIFIERS), 8, VERIFIERS)
        for script in VERIFIERS:
            self.assertTrue((REPO / script).is_file(), f"{script} is gone; this route is a fiction")

    def test_each_ci_only_verifier_passes_here_too(self) -> None:
        for script in VERIFIERS:
            code, out = self.run_verifier(script)
            verdicts = VERDICT.findall(out)
            self.assertTrue(verdicts, f"{script} printed no verdict line:\n{out[-400:]}")
            self.assertEqual(0, code, f"{script} exited {code}:\n{out[-600:]}")
            self.assertIn("PASS", out, f"{script} exited 0 without a PASS verdict:\n{out[-400:]}")

    def test_the_current_state_freshness_mode_runs_here_too(self) -> None:
        """A route that names a script but not the mode CI runs is not a route.

        Measured the hard way: `tests/ci/test_current_state.py` imports generate_current_state and passes,
        while the CI step also runs `--check-current`, which was red locally and in CI at 6e6d4fbf because
        the projection still recorded the digests from before today's skill edits. No local run executed
        that mode, so the canonical gate said PASS.
        """
        proc = subprocess.run([sys.executable, "scripts/ci/generate_current_state.py", "--check-current"],
                              cwd=REPO, capture_output=True)
        out = (proc.stdout + proc.stderr).decode("utf-8", "replace")
        self.assertEqual(0, proc.returncode, out)
        self.assertIn("CURRENT_STATE_FRESHNESS_PASS", out)

    def test_no_check_exists_only_in_ci(self) -> None:
        code, out = 0, ""
        proc = subprocess.run([sys.executable, "scripts/ci/verify_ci_check_reachability.py"],
                              cwd=REPO, capture_output=True)
        code, out = proc.returncode, (proc.stdout + proc.stderr).decode("utf-8", "replace")
        self.assertEqual(0, code, out)
        self.assertIn("CI_CHECK_REACHABILITY_PASS", out)

    def test_the_reachability_checker_refuses_when_a_rule_escapes_both_routes(self) -> None:
        """Planted falsification: an operand no local file names must be reported, not ignored."""
        original = reach.tracked_python
        try:
            reach.tracked_python = lambda root: []
            self.assertEqual(1, reach.main([]))
        finally:
            reach.tracked_python = original

    def test_the_generated_types_projection_matches_the_generator_and_is_restored(self) -> None:
        """CI regenerates; a writer needs the same freshness signal without a leftover mutation."""
        generated = REPO / "packages/client-neutral-core/generated/contracts.ts"
        committed = generated.read_bytes()
        try:
            proc = subprocess.run([sys.executable, "scripts/ci/generate_contract_types.py"],
                                  cwd=REPO, capture_output=True)
            self.assertEqual(0, proc.returncode, proc.stderr.decode("utf-8", "replace")[-600:])
            regenerated = generated.read_bytes()
        finally:
            generated.write_bytes(committed)
        self.assertEqual(committed, regenerated,
                         "the committed contracts.ts is not what the generator produces; CI would "
                         "verify a projection nobody can regenerate")
        self.assertEqual(committed, generated.read_bytes(), "the restore did not take")


if __name__ == "__main__":
    unittest.main()
