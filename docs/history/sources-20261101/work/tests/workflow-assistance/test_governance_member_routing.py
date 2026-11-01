"""Route guard: a member that carries both shapes must go to the runner that sees all of it.

`services/orchestration/run_quality_gate.py` classifies each mandatory member from its syntax tree and
addresses unittest members by module stem, pytest members and check scripts by repository path. NF31
(2026-10-26) replaced a substring classifier that sent genuine pytest modules to `python -m unittest`,
where they imported cleanly, printed nothing and exited 0 -- a batch that reports PASS while executing
nothing. The rule that fixed it is one line long (module-level `def test_*` wins over a TestCase class),
and until now nothing tested it: reordering those two returns would re-open the whole leak with every
gate still green.

Two things make this a check rather than an echo. The shape table drives the shipped classifier over
sources written here, and the population sweep decides "this file must not go to unittest" from its own
syntax walk -- not from the classifier's answer -- so the two can disagree. Verified by planting the
fault: swapping the classifier's two returns fails `shape='mixed'` and the population sweep both.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "services" / "orchestration" / "run_quality_gate.py"

SHAPES = {
    "unittest_only": (
        "import unittest\n\n\n"
        "class TestOne(unittest.TestCase):\n"
        "    def test_a(self) -> None:\n        pass\n", "unittest"),
    "pytest_only": (
        "def test_a() -> None:\n    pass\n", "pytest"),
    "mixed": (
        "import unittest\n\n\n"
        "class TestOne(unittest.TestCase):\n"
        "    def test_a(self) -> None:\n        pass\n\n\n"
        "def test_b() -> None:\n    pass\n", "pytest"),
    "testcase_mixin": (
        "import unittest\n\n\n"
        "class _Guard(unittest.TestCase):\n"
        "    def test_guard(self) -> None:\n        pass\n\n\n"
        "class TestReal(_Guard):\n    pass\n", "unittest"),
    "no_tests_at_all": (
        "import sys\n\nsys.exit(0)\n", "script"),
    "unparseable": (
        "def broken(:\n", "script"),
}


def _gate():
    spec = importlib.util.spec_from_file_location("run_quality_gate_routing", GATE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def module_level_test_functions(source: str) -> list[str]:
    """Names this file declares at module scope that start with `test`.

    Written independently of the gate on purpose. `python -m unittest` never collects these, so any file
    carrying one of them is a file the unittest route would under-execute -- and if this judgement came
    from the classifier itself, the assertion could not fail for the reason it exists to catch.
    """
    try:
        tree = ast.parse(source)
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    return [node.name for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test")]


class ClassifierShapeTests(unittest.TestCase):
    def test_each_shape_gets_the_runner_that_executes_all_of_it(self) -> None:
        gate = _gate()
        with tempfile.TemporaryDirectory() as tmp:
            for name, (source, expected) in SHAPES.items():
                with self.subTest(shape=name):
                    path = Path(tmp) / f"{name}.py"
                    path.write_text(source, encoding="utf-8")
                    self.assertEqual(expected, gate.governance_member_kind(path))

    def test_the_mixed_shape_is_not_routed_to_unittest(self) -> None:
        """The one line that carries the whole defect class.

        `python -m unittest` collects the TestCase and silently drops the bare `def test_*`, so a mixed
        file sent there reports a clean run while the function cases never execute. pytest collects both.
        """
        gate = _gate()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mixed.py"
            path.write_text(SHAPES["mixed"][0], encoding="utf-8")
            self.assertEqual("pytest", gate.governance_member_kind(path))

    def test_a_member_id_with_no_file_behind_it_keeps_the_loud_route(self) -> None:
        gate = _gate()
        self.assertEqual("unittest", gate.governance_member_route("nf00_module_that_does_not_exist"))


class RealPopulationTests(unittest.TestCase):
    def test_the_population_holds_both_shapes_so_the_sweeps_are_not_over_an_empty_set(self) -> None:
        gate = _gate()
        files = gate.governance_test_files()
        self.assertGreater(len(files), 50, f"only {len(files)} mandatory files were discovered")
        with_bare = [f for f in files if module_level_test_functions((ROOT / f).read_text(encoding="utf-8"))]
        without = [f for f in files if not module_level_test_functions((ROOT / f).read_text(encoding="utf-8"))]
        self.assertGreater(with_bare, [], "no mandatory file declares bare test functions, so the "
                                         "mixed-shape rule below proves nothing about this tree")
        self.assertGreater(without, [])

    def test_no_file_with_bare_test_functions_is_addressed_by_the_unittest_convention(self) -> None:
        """The live version of the leak: a member on disk that one runner sees and the other does not."""
        gate = _gate()
        members = set(gate.mandatory_discovery_modules())
        offenders = []
        for rel in gate.governance_test_files():
            bare = module_level_test_functions((ROOT / rel).read_text(encoding="utf-8"))
            if bare and Path(rel).stem in members:
                offenders.append((rel, bare))
        self.assertEqual([], offenders,
                         "these files declare module-level test functions but are addressed by module "
                         f"stem, i.e. handed to `python -m unittest`: {offenders[:4]}")

    def test_every_mandatory_file_is_addressed_exactly_once(self) -> None:
        """A file that drops out of the member list is never run again, and nothing prints that."""
        gate = _gate()
        members = gate.mandatory_discovery_modules()
        self.assertEqual(len(members), len(set(members)), "a member id is addressed twice")
        addressed = {gate.governance_member_path(m).relative_to(ROOT).as_posix() for m in members}
        missing = sorted(set(gate.governance_test_files()) - addressed)
        self.assertEqual([], missing, f"these mandatory files have no member: {missing[:6]}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
