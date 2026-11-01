"""A green exit from a governance module must be evidence that it ran something.

Discovery-only coverage has one blind spot: a `tests/ci/test_*.py` file with no `unittest.main()` entry
point executes zero tests and exits 0, so the suite counts it as a passing module. That was found by
accident today -- a throwaway file written to read the FAIL header came back green on its first
iteration. These assertions are synthetic on purpose: calling the real runner from here would make the
outer suite spawn the inner suite spawn this module, forever. The live tree was measured again on
2026-10-25 with the shape rule in place: 59 executed modules (`discovered=60`,
`excluded_post_merge=1`), none silent, none reporting `Ran 0 tests`, none carrying a class below the runner.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "ci"))
sys.path.insert(0, str(REPO / "packages" / "client-neutral-core" / "scripts"))

import run_root_governance_suite as suite  # noqa: E402


class MainGuardShape(unittest.TestCase):
    """A module whose tail sits below `unittest.main()` cannot be executed by a script-based suite."""

    GOOD = (
        "import unittest\n\n\nclass ATests(unittest.TestCase):\n    def test_one(self):\n        pass\n\n\n"
        'if __name__ == "__main__":\n    unittest.main()\n'
    )
    BLIND = (
        "import unittest\n\n\nclass ATests(unittest.TestCase):\n    def test_one(self):\n        pass\n\n\n"
        'if __name__ == "__main__":\n    unittest.main()\n\n\nclass LateTests(unittest.TestCase):\n'
        "    def test_two(self):\n        pass\n"
    )
    NO_GUARD = "import unittest\n\n\nclass ATests(unittest.TestCase):\n    def test_one(self):\n        pass\n"

    def _write(self, text: str) -> Path:
        # Bounded on purpose: `test_temp_fixture_stays_inside_the_boundary` names every bare
        # `tempfile.mkdtemp()` site, and `project_temp.fixture_dir()` registers the directory so the
        # at-exit hook releases it instead of leaving residue for the bounded-residue gate to convict.
        import project_temp

        path = Path(project_temp.fixture_dir(prefix="guard-shape-")) / "test_shape.py"
        path.write_text(text, encoding="utf-8")
        return path

    def test_a_class_appended_below_the_guard_is_named(self) -> None:
        reason = suite.shape_reason(self._write(self.BLIND))
        self.assertIsNotNone(reason)
        self.assertIn("CLASS_BELOW_MAIN_GUARD", str(reason))
        self.assertIn("LateTests", str(reason), "the refusal has to name the class that cannot run")

    def test_a_guard_at_the_end_of_the_file_is_accepted(self) -> None:
        self.assertIsNone(suite.shape_reason(self._write(self.GOOD)))

    def test_a_module_without_a_guard_is_left_to_the_vacuity_check(self) -> None:
        # Script-executed modules with no `unittest.main()` run zero tests and print nothing; that is the
        # silence rule's job. Two rules firing on one shape would hide which one a reader must fix.
        self.assertIsNone(suite.shape_reason(self._write(self.NO_GUARD)))

    def test_no_live_suite_module_has_the_blind_shape(self) -> None:
        offenders = []
        for module in sorted((REPO / "tests" / "ci").glob("test_*.py")):
            reason = suite.shape_reason(module)
            if reason is not None:
                offenders.append(f"{module.name}: {reason}")
        self.assertEqual([], offenders,
                         "every class in tests/ci must sit above the runner, or the suite executes a "
                         "subset while reporting the module green")


class VacuityReason(unittest.TestCase):
    def test_a_module_that_exits_zero_in_silence_is_not_coverage(self) -> None:
        reason = suite.vacuity_reason(0, "")
        self.assertIsNotNone(reason)
        self.assertIn("SILENT_MODULE", str(reason))

    def test_whitespace_and_a_blank_line_are_still_silence(self) -> None:
        for output in ("   ", "\n\n", " \n \n"):
            self.assertIn("SILENT_MODULE", str(suite.vacuity_reason(0, output)), output)

    def test_ran_zero_tests_is_refused_even_though_it_prints(self) -> None:
        output = "----------------------------------------------------------------------\nRan 0 tests in 0.000s\n\nOK\n"
        self.assertIn("ZERO_TESTS", str(suite.vacuity_reason(0, output)))

    def test_a_module_that_reports_tests_is_accepted(self) -> None:
        self.assertIsNone(suite.vacuity_reason(0, "Ran 9 tests in 0.395s\n\nOK\n"))

    def test_a_hand_rolled_module_with_its_own_receipt_is_accepted(self) -> None:
        """Not every governance module is a unittest script; one prints its own verdict line."""
        self.assertIsNone(suite.vacuity_reason(0, "FAILFAST_GROUP_PASS commands=3 exit=0\n"))

    def test_a_red_exit_is_never_relabelled_as_vacuity(self) -> None:
        """A failing module must keep its real code; the vacuity check only guards green exits."""
        self.assertIsNone(suite.vacuity_reason(1, ""))


class TheRunnerItself(unittest.TestCase):
    def test_the_pass_and_fail_headers_name_the_two_counts_separately(self) -> None:
        """`failed=14` used to mean 14 printed lines while two modules were red.

        Measured on a controlled red: `modules_ran=32 modules_failed=1 detail_lines=7`.
        """
        source = (REPO / "scripts" / "ci" / "run_root_governance_suite.py").read_text(encoding="utf-8")
        self.assertIn("modules_failed={failed_modules}", source)
        self.assertIn("detail_lines={len(failures)}", source)
        self.assertNotIn("failed={len(failures)}", source)


if __name__ == "__main__":
    unittest.main()
