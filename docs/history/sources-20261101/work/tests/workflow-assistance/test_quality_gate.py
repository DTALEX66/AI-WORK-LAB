from __future__ import annotations

import contextlib
import importlib.util
import io
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "services/orchestration" / "run_quality_gate.py"
SPEC = importlib.util.spec_from_file_location("run_quality_gate", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class QualityGateTests(unittest.TestCase):
    def test_governance_child_receives_project_runtime_even_with_external_temp(self) -> None:
        from types import SimpleNamespace
        with patch.dict(MODULE.os.environ, {"TMP": "X:/external-temp", "TEMP": "X:/external-temp"}):
            with patch.object(MODULE.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="Ran 1 test in 0.0s\nOK\n", stderr="")) as child:
                exit_code, _output, outcomes = MODULE._run_governance_batch(["test_placeholder"])
        environment = child.call_args.kwargs["env"]
        for name in ("TMP", "TEMP", "TMPDIR"):
            self.assertTrue(Path(environment[name]).resolve().is_relative_to(ROOT / ".project-local/runs"))
        # NF31: the batch answers per member, and an id with no file behind it keeps the unittest route
        # rather than being reclassified into a script that could exit 0 having done nothing.
        self.assertEqual(exit_code, 0)
        self.assertEqual(outcomes["test_placeholder"].kind, "unittest")

    def test_dependency_preflight_fails_once_with_install_instruction(self) -> None:
        with patch.object(MODULE.importlib.util, "find_spec", return_value=None):
            self.assertEqual(MODULE.dependency_preflight(), 2)

    def test_a_missing_bash_is_a_named_not_run_rather_than_a_pass(self) -> None:
        """AGENTS.md: a missing or skipped required job fails the aggregate."""
        with patch.object(MODULE, "usable_bash", return_value=None):
            self.assertEqual(MODULE.gate_shell(), 3)

    def test_a_missing_pwsh_is_a_named_not_run_rather_than_a_pass(self) -> None:
        with patch.object(MODULE.shutil, "which", return_value=None):
            self.assertEqual(MODULE.gate_powershell(), 3)

    def test_the_retirement_exclusion_excludes_a_file_that_actually_exists(self) -> None:
        # The four declared retired names point at files the 2026-10-19 archive normalization deleted, so
        # the original assertion -- a subtraction against paths that cannot exist -- could never fail. Pin
        # the mechanism instead: a discovered, mandatory test file leaves the mandatory set the moment it is
        # declared retired, and only that one file leaves.
        present = next(p.name for p in (ROOT / "tests" / "workflow-assistance").glob("test_*.py"))
        baseline = MODULE.governance_test_files()
        self.assertIn(f"tests/workflow-assistance/{present}", baseline)
        with patch.object(MODULE, "RETIRED_ORDINARY_TESTS", frozenset({present})):
            after = MODULE.governance_test_files()
        self.assertNotIn(f"tests/workflow-assistance/{present}", after)
        self.assertEqual(len(baseline) - len(after), 1,
                         "declaring one retirement must exclude exactly one file, not a whole glob")

    def test_runtime_adapter_gate_is_explicit_but_not_in_default_verify(self) -> None:
        self.assertIn("portable-install-runtime", MODULE.GATES)
        self.assertNotIn("portable-install-runtime", MODULE.VERIFY_ORDER)

    def test_governance_excludes_only_retired_tests(self) -> None:
        selected = set(MODULE.governance_test_files())
        retired = {f"tests/{name}" for name in MODULE.RETIRED_ORDINARY_TESTS}
        all_tests = {
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "tests" / "workflow-assistance").glob("test_*.py")
        }
        all_negative = {
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "tests" / "workflow-assistance").glob("nf*.py")
        }

        # P0-05: mandatory discovery is ordinary + negative-control tests, minus
        # the retired set. No hard-coded count; the negative controls are part
        # of the mandatory set now.
        self.assertTrue(retired.isdisjoint(selected))
        self.assertEqual(selected, (all_tests | all_negative) - retired)
        self.assertIn("tests/workflow-assistance/test_codex_global_asset_sync.py", selected)
        self.assertIn("tests/workflow-assistance/nf01_rule_semantics_artifact_flow.py", selected)

    def test_governance_discovers_negative_controls(self) -> None:
        modules = MODULE.mandatory_discovery_modules()
        # A representative negative-control module is importable in the gate.
        self.assertIn("nf01_rule_semantics_artifact_flow", modules)
        self.assertIn("nf14_universal_signoff", modules)
        # No hard-coded count masquerading as truth: the set is discovered.
        self.assertGreater(len([m for m in modules if m.startswith("nf")]), 0)

    def test_governance_not_run_is_not_pass(self) -> None:
        # P0-05 fail-closed: a clean process exit that executed ZERO tests must
        # not be reported as PASS. NF31: the batch now answers with per-member
        # accounting, and no accounting row at all is the hollowest shape of all.
        with patch.object(MODULE, "_run_governance_batch", return_value=(0, "no banner here\n", {})):
            with patch.object(MODULE, "mandatory_discovery_modules", return_value=["test_placeholder"]):
                self.assertEqual(MODULE.gate_governance(), 1)

    def test_governance_empty_set_is_not_pass(self) -> None:
        # P0-05 fail-closed: an empty mandatory set is a red flag, not a pass.
        with patch.object(MODULE, "mandatory_discovery_modules", return_value=[]):
            self.assertEqual(MODULE.gate_governance(), 1)

    def test_governance_failed_batch_is_not_pass(self) -> None:
        # P0-05 fail-closed: a non-zero batch exit is propagated, never PASS.
        with patch.object(
            MODULE,
            "_run_governance_batch",
            return_value=(
                1,
                "Ran 3 tests in 0.1s\nFAILED (failures=1)\n",
                {"test_placeholder": MODULE.MemberOutcome("unittest", 3, 3, 0, 3, 1)},
            ),
        ):
            self.assertEqual(MODULE.gate_governance(), 1)

    def test_a_mixed_batch_with_a_silent_member_is_not_pass(self) -> None:
        """The shape of the hole: a healthy shared banner, a member that ran nothing, and exit code 0.

        Every mock here used to be a unittest-only batch, and a batch with no unittest member answered
        `script-only-batch(all-exit-0)` from the returncode alone -- so a silent member could only be
        caught by an assertion the suite never made. This is a MIXED batch: one member that ran, one that
        printed nothing, and the verdict must name the silent one.
        """
        silent = "tests/workflow-assistance/probe_silent.py"
        outcomes = {
            "test_placeholder": MODULE.MemberOutcome("unittest", 3, 3, 0, 3, 0),
            silent: MODULE.MemberOutcome("script", 0, 0, 0, 0, 0),
        }
        with patch.object(MODULE, "mandatory_discovery_modules", return_value=list(outcomes)):
            with patch.object(MODULE, "_run_governance_batch",
                              return_value=(0, "Ran 3 tests in 0.1s\nOK\n", outcomes)):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    verdict = MODULE.gate_governance()
        self.assertEqual(verdict, 1)
        self.assertIn(f"ZERO_EXECUTED {silent}", buffer.getvalue())

    def test_a_mixed_batch_pass_line_counts_the_pytest_route(self) -> None:
        """`executed=` must be the sum over routes, not the unittest banner.

        Measured before the fix: 10 members contributed 0 of the reported 2921 while 78 cases sat inside
        them unexecuted. A PASS line that only knows the banner cannot show that loss, so this pins the
        arithmetic across both routes.
        """
        outcomes = {
            "test_placeholder": MODULE.MemberOutcome("unittest", 3, 3, 1, 2, 0),
            "tests/workflow-assistance/probe_pytest.py": MODULE.MemberOutcome("pytest", 17, 17, 0, 17, 0),
        }
        # The skip must be NAMEABLE in the batch output, because the gate refuses a `skipped=N` it cannot
        # attribute to a case: the same rule that made the hole invisible also makes a fabricated count fail.
        banner = ("test_skipped_case (test_placeholder.SomeCase.test_skipped_case) ... skipped 'no vendor cache'\n"
                  "Ran 3 tests in 0.1s\nOK (skipped=1)\n")
        with patch.object(MODULE, "mandatory_discovery_modules", return_value=list(outcomes)):
            with patch.object(MODULE, "_run_governance_batch",
                              return_value=(0, banner, outcomes)):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    verdict = MODULE.gate_governance()
        self.assertEqual(verdict, 0, buffer.getvalue())
        printed = buffer.getvalue()
        self.assertIn("QUALITY_GATE_GOVERNANCE_PASS modules=2 executed=19 ran=20 skipped=1", printed)
        self.assertIn("GOVERNANCE_ROUTES unittest=1 pytest=1 script=0 pytest_executed=17", printed)

    def test_the_shared_banner_cannot_hide_an_unattributed_case(self) -> None:
        """Attribution is checked against the banner, so a case nobody claims fails instead of vanishing."""
        outcomes = {"test_placeholder": MODULE.MemberOutcome("unittest", 1, 1, 0, 1, 0)}
        with patch.object(MODULE, "mandatory_discovery_modules", return_value=list(outcomes)):
            with patch.object(MODULE, "_run_governance_batch",
                              return_value=(0, "Ran 4 tests in 0.1s\nOK\n", outcomes)):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    verdict = MODULE.gate_governance()
        self.assertEqual(verdict, 1)
        self.assertIn("ATTRIBUTION_GAP banner_ran=4 attributed=1", buffer.getvalue())

    def test_negative_mutation_breaks_mandatory_gate(self) -> None:
        # P0-05 negative mutation (real, not simulated): write a throwaway
        # negative-control module whose condition is intentionally broken, run
        # it through the gate's real batch runner, and assert the gate fails.
        # This is the "break one mandatory NF condition -> aggregate must fail"
        # guarantee, with no mutation of any tracked test file.
        #
        # NF31 adds the mutation this suite never made: a VACUOUS control. A failing module already exited
        # non-zero, so the old runner caught it; a module that executes nothing exited 0 and the old runner
        # called that a pass. Both directions are pinned now, and the vacuous probe lives in the project
        # runtime root instead of the tracked test directory, so a crash cannot leave a permanently red
        # mandatory member behind.
        broken = "nf00_mutation_probe"
        tmp_mod = ROOT / "tests" / "workflow-assistance" / f"{broken}.py"
        tmp_mod.write_text(
            "import unittest\n\n\nclass MutationProbe(unittest.TestCase):\n"
            "    def test_broken_condition_fails(self):\n"
            "        self.fail('mandatory negative control intentionally broken')\n\n"
            "if __name__ == '__main__':\n    unittest.main()\n",
            encoding="utf-8",
        )
        vacuous_dir = ROOT / ".project-local" / "runs" / "tmp" / "quality-gate-vacuous-probe"
        vacuous_dir.mkdir(parents=True, exist_ok=True)
        vacuous = (vacuous_dir / "probe_vacuous.py")
        # No test at all, and it prints nothing: exactly the shape that used to read as coverage.
        vacuous.write_text("VALUE = 1\n", encoding="utf-8")
        vacuous_member = vacuous.as_posix()
        try:
            # A single broken mandatory negative control, run through the gate's
            # real batch runner, must produce a non-zero exit -> gate FAIL.
            exit_code, _output, outcomes = MODULE._run_governance_batch([broken])
            self.assertEqual(exit_code, 1)
            # A failing control is distinguishable from a silent one: it really ran its case.
            self.assertEqual(outcomes[broken].executed, 1, outcomes[broken])
            # And the gate wrapper itself reports failure on that same batch.
            with patch.object(
                MODULE, "_run_governance_batch",
                return_value=(1, "Ran 1 test in 0.0s\nFAILED (failures=1)\n",
                              {broken: MODULE.MemberOutcome("unittest", 1, 1, 0, 1, 1)}),
            ):
                self.assertEqual(MODULE.gate_governance(), 1)

            # The vacuous mutation, through the real runner: exit 0, nothing executed, and the accounting
            # names it. This is the assertion whose absence kept 10 silent members green.
            silent_exit, _silent_output, silent_outcomes = MODULE._run_governance_batch([vacuous_member])
            self.assertEqual(silent_exit, 0, "the hole depends on a silent module exiting 0")
            self.assertEqual(silent_outcomes[vacuous_member].executed, 0)
            self.assertEqual(
                MODULE.governance_hollow_members([vacuous_member], silent_outcomes),
                [f"ZERO_EXECUTED {vacuous_member}"],
            )
            with patch.object(MODULE, "mandatory_discovery_modules", return_value=[vacuous_member]):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    self.assertEqual(MODULE.gate_governance(), 1)
            self.assertIn(f"ZERO_EXECUTED {vacuous_member}", buffer.getvalue())

            # And a mixed real batch: the healthy member still has to be counted as executed.
            mixed_exit, _mixed_output, mixed = MODULE._run_governance_batch([broken, vacuous_member])
            self.assertEqual(mixed_exit, 1, "a failing member fails the batch it shares with a silent one")
            self.assertEqual(mixed[broken].executed, 1)
            self.assertEqual(mixed[vacuous_member].executed, 0)
        finally:
            tmp_mod.unlink(missing_ok=True)
            vacuous.unlink(missing_ok=True)

    def test_governance_modules_are_importable_from_tests_pythonpath(self) -> None:
        modules = [Path(path).stem for path in MODULE.governance_test_files()]
        self.assertIn("test_codex_global_asset_sync", modules)
        self.assertNotIn("test_design_token_compliance", modules)
        self.assertTrue(all("/" not in module and "\\" not in module for module in modules))


if __name__ == "__main__":
    unittest.main()
