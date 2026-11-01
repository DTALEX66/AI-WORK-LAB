"""W07 (2026-10-17): the CI-job <-> local-gate mapping, and the falsifications that keep it honest.

Why the falsifications matter more than the pass: the mapping is a *claim about two other files*. A checker
that only re-reads today's tree proves today's tree; these cases plant the three failures the mapping exists
to catch -- a gate naming a job that does not exist, a job nothing claims, and a CI-only check that is silent
about being CI-only -- and require each to be reported with its name.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci" / "verify_gate_ci_job_mapping.py"


def load_module():
    spec = importlib.util.spec_from_file_location("verify_gate_ci_job_mapping", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def profile_with(**gates):
    return {"gates": {name: {"ci_job": job} for name, job in gates.items()}, "ci": {}}


class MappingTests(unittest.TestCase):
    def test_the_live_mapping_passes_and_names_every_job(self) -> None:
        proc = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        out = proc.stdout + proc.stderr
        self.assertEqual(0, proc.returncode, out)
        self.assertIn("GATE_CI_JOB_MAPPING_PASS", out)
        self.assertIn("every job is claimed or declared", out)

    def test_a_gate_naming_a_nonexistent_job_is_reported(self) -> None:
        module = load_module()
        problems = module.audit(profile_with(workflow="workflow", observer="nope-not-a-job"),
                                {"workflow": "work-lab-gate.yml"}, set())
        self.assertTrue(any("nope-not-a-job" in problem for problem in problems),
                        f"a gate claiming a job that does not exist must be named: {problems}")

    def test_a_job_no_one_claims_is_reported(self) -> None:
        """The rule W07 asks for: a required CI job a writer cannot see from a local run."""
        module = load_module()
        problems = module.audit(profile_with(workflow="workflow"),
                                {"workflow": "work-lab-gate.yml", "silent-new-job": "work-lab-gate.yml"}, set())
        self.assertTrue(any("silent-new-job" in problem for problem in problems),
                        f"an unclaimed job must be reported, not tolerated: {problems}")

    def test_a_ci_only_route_must_say_so_and_a_stale_declaration_is_caught(self) -> None:
        module = load_module()
        profile = profile_with(workflow="workflow")
        # `capsule-verify` exists in the workflow but declares no local_route field at all -> the field is
        # missing, which is exactly the silence this checker rejects.
        profile["ci"] = {"additional_required_jobs": {"capsule-verify": {"note": "CI only, honest"}}}
        problems = module.audit(profile, {"workflow": "work-lab-gate.yml", "capsule-verify": "wlr-060-gates.yml"},
                                set())
        self.assertTrue(any("declares no local_route" in problem for problem in problems), problems)

        # Declaring it as null WITH a note is the accepted shape: the gap is visible on purpose.
        profile["ci"]["additional_required_jobs"]["capsule-verify"] = {
            "local_route": None, "note": "CI-only with negative controls; no local test module"}
        self.assertEqual([], [p for p in module.audit(
            profile, {"workflow": "work-lab-gate.yml", "capsule-verify": "wlr-060-gates.yml"}, set())
            if "capsule-verify" in p])

    def test_a_local_route_pointing_at_an_untracked_file_is_reported(self) -> None:
        module = load_module()
        profile = profile_with(workflow="workflow")
        profile["ci"] = {"additional_required_jobs": {
            "config-compiler": {"local_route": "python tests/ci/does_not_exist.py", "note": "x"}}}
        problems = module.audit(profile, {"workflow": "work-lab-gate.yml", "config-compiler": "x.yml"}, set())
        self.assertTrue(any("not tracked" in problem for problem in problems), problems)


class StageCoverageTests(unittest.TestCase):
    """CL-14 direction five: 50 canonical stages against the commands the workflows actually run.

    The population is read from `VERIFY_ORDER` itself, so a stage added to the gate cannot be left invisible;
    the falsifications plant the four ways an absence gets dressed up as coverage.
    """

    def test_the_live_tree_has_no_undeclared_stage(self) -> None:
        proc = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        out = proc.stdout + proc.stderr
        self.assertEqual(0, proc.returncode, out)
        self.assertIn("undeclared=0", out, "a stage that is neither invoked nor declared must show in its own count")

    def test_a_stage_neither_invoked_nor_declared_is_named(self) -> None:
        module = load_module()
        problems = module.stage_coverage_audit({"ci": {}}, ("alpha", "beta"), {"alpha": "work-lab-gate.yml"}, {})
        self.assertEqual(1, len(problems), problems)
        self.assertIn("beta", problems[0])

    def test_a_declared_absence_must_state_why_and_may_not_deny_an_invocation(self) -> None:
        module = load_module()
        stages = ("alpha", "beta", "gamma", "delta")
        invoked = {"alpha": "work-lab-gate.yml", "delta": "work-lab-gate.yml"}
        coverage = {"beta": {"status": "needs_local_environment"},              # no reason
                    "gamma": {"status": "invoked_in_ci", "reason": "x"},        # a status that is not a reason
                    "delta": {"status": "needs_local_environment", "reason": "x"}}  # denies a real invocation
        problems = module.stage_coverage_audit({"ci": {"stage_coverage": coverage}}, stages, invoked, {})
        self.assertTrue(any("beta" in p and "without a reason" in p for p in problems), problems)
        self.assertTrue(any("gamma" in p and "invoked_in_ci" in p for p in problems), problems)
        self.assertTrue(any("delta" in p and "must not hide an invocation" in p for p in problems), problems)

    def test_a_coverage_claim_must_name_a_step_that_really_runs(self) -> None:
        module = load_module()
        stages = ("alpha", "beta")
        invoked = {"alpha": "work-lab-gate.yml"}
        ghost = {"beta": {"status": "covered_by_ci_step", "covered_by": "ghost-stage", "reason": "x"}}
        problems = module.stage_coverage_audit({"ci": {"stage_coverage": ghost}}, stages, invoked, {})
        self.assertTrue(any("ghost-stage" in p for p in problems),
                        f"coverage by a step nothing invokes must be refused: {problems}")
        # Naming a stage a workflow does invoke, or a real job ID, is the accepted shape.
        good = {"beta": {"status": "covered_by_ci_step", "covered_by": "alpha", "reason": "x"}}
        self.assertEqual([], module.stage_coverage_audit({"ci": {"stage_coverage": good}}, stages, invoked, {}))
        by_job = {"beta": {"status": "covered_by_ci_step", "covered_by": "observer", "reason": "x"}}
        self.assertEqual([], module.stage_coverage_audit({"ci": {"stage_coverage": by_job}}, stages, invoked,
                                                         {"observer": "work-lab-gate.yml"}))

    def test_a_declaration_for_a_stage_that_no_longer_exists_is_stale(self) -> None:
        module = load_module()
        coverage = {"renamed-away-stage": {"status": "needs_local_environment", "reason": "x"}}
        problems = module.stage_coverage_audit({"ci": {"stage_coverage": coverage}}, ("alpha",), {}, {})
        self.assertTrue(any("renamed-away-stage" in p and "not a stage in VERIFY_ORDER" in p for p in problems),
                        problems)

    def test_a_comment_that_quotes_a_command_is_not_an_invocation(self) -> None:
        """The invocation set comes from parsed YAML step bodies with their shell comments removed.

        A `run: |` block in this workflow explains itself -- often by naming the very gates it no longer runs --
        so a text search over the file would read a historical note as a requirement and report a stage as
        covered while no command executes it.
        """
        sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))
        import project_temp
        module = load_module()
        workflow = Path(project_temp.fixture_dir(prefix="mapping-workflow-")) / "gate.yml"
        workflow.write_text(
            "jobs:\n"
            "  workflow:\n"
            "    steps:\n"
            "      - name: gates\n"
            "        run: |\n"
            "          # retired 2026-01-01: python services/orchestration/run_quality_gate.py pretend-stage\n"
            "          python services/orchestration/run_quality_gate.py real-stage\n",
            encoding="utf-8")
        invoked = module.invoked_stages(module.workflow_run_commands((workflow,)))
        self.assertEqual(["real-stage"], sorted(invoked), invoked)


if __name__ == "__main__":
    unittest.main(verbosity=2)
