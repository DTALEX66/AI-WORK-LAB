# SPDX-License-Identifier: MIT
"""Teeth for design-lab/scripts/verify_test_selfsufficiency.py.

Three obligations, and each is falsified rather than asserted:

1. the SHIPPED tree passes, and the counts it reports are re-measured here (206 modules, 206
   executable) so a scanner that silently found nothing cannot report a clean pass;
2. each shape that the gate is meant to refuse -- a file with no entry guard, a file that imports a
   second-party name with no sys.path insert, a file with no test cases, an empty scan, an
   unparseable file -- goes red FOR ITS OWN REASON in a scratch tree;
3. a weakened COPY of the gate stops convicting exactly those cases, which proves the verdicts come
   from the rules and not from the fixtures.
"""
from __future__ import annotations

import ast
import contextlib
import importlib.util
import io
import shutil
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GATE_PATH = REPO / 'design-lab' / 'scripts' / 'verify_test_selfsufficiency.py'
SCRATCH_BASE = REPO / '.project-local' / 'task-runtime' / 'test-selfsufficiency-scratch'

# Re-measured 2026-10-08: 206 test modules under design-lab/tests, all 206 carrying an entry guard
# after 17 of them were given one (they used to exit 0 having run nothing) and one more was given its
# own src bootstrap. A floor, not a snapshot: a module that disappears is a finding, and so is a
# scanner that reports fewer than this because its own glob broke.
MIN_MODULES = 206

GUARDED = '''# SPDX-License-Identifier: MIT
"""A module in the shape the gate expects."""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))

import design_lab  # noqa: E402


class ShapeTests(unittest.TestCase):
    def test_the_module_exists(self):
        self.assertTrue(design_lab is not None)


if __name__ == '__main__':
    unittest.main()
'''


def load_gate(path: Path = None):
    target = Path(path or GATE_PATH)
    spec = importlib.util.spec_from_file_location('verify_test_selfsufficiency_under_test', target)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_gate(gate) -> tuple[int, str]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = gate.main([])
    return code, buffer.getvalue()


class ShippedTreeTests(unittest.TestCase):
    def test_the_shipped_tree_passes_with_the_counts_this_file_claims(self):
        gate = load_gate()
        code, output = run_gate(gate)
        self.assertEqual(code, 0, f'the shipped tree is red:\n{output}')
        self.assertIn('TEST_SELF_SUFFICIENCY=OK', output)
        scanned = int([token for token in output.split() if token.startswith('scanned=')]
                      [0].split('=')[1])
        executable = int([token for token in output.split() if token.startswith('executable=')]
                         [0].split('=')[1])
        self.assertGreaterEqual(scanned, MIN_MODULES,
                                f'only {scanned} modules scanned -- the glob broke, not the tree')
        self.assertEqual(executable, scanned,
                         f'{scanned - executable} module(s) run nothing when executed as a file')

    def test_the_gate_is_reachable_by_a_test_and_not_only_by_its_own_file(self):
        """A verifier nobody invokes is documentation; this file is the invocation."""
        self.assertTrue(GATE_PATH.is_file())
        self.assertIn('verify_test_selfsufficiency.py',
                      (REPO / 'design-lab/scripts/verify_design_lab.py').read_text(encoding='utf-8'),
                      'the aggregate verifier does not run this gate, so CI never would either')


class ScratchTreeTests(unittest.TestCase):
    """A synthetic repo whose roots and test dir are small enough to mutate on purpose."""

    def setUp(self):
        self.gate = load_gate()

    def scratch(self, name: str) -> Path:
        root = SCRATCH_BASE / name
        if root.exists():
            shutil.rmtree(root)
        (root / 'src' / 'design_lab').mkdir(parents=True)
        (root / 'src' / 'design_lab' / '__init__.py').write_text('', encoding='utf-8')
        package = root / 'packages' / 'capabilities' / 'reconstruction'
        package.mkdir(parents=True)
        (package / '__init__.py').write_text('', encoding='utf-8')
        tests = root / 'design-lab' / 'tests'
        tests.mkdir(parents=True)
        self.gate.REPO = root
        self.gate.TEST_DIR = tests
        return tests

    def write(self, tests: Path, name: str, source: str) -> Path:
        path = tests / name
        path.write_text(source, encoding='utf-8', newline='\n')
        return path

    def test_a_clean_synthetic_tree_passes(self):
        tests = self.scratch('clean')
        self.write(tests, 'test_shape.py', GUARDED)
        code, output = run_gate(self.gate)
        self.assertEqual(code, 0, f'the control tree is red:\n{output}')
        self.assertIn('modules=1', output)

    def test_a_module_without_an_entry_guard_is_named_for_that(self):
        tests = self.scratch('no-guard')
        self.write(tests, 'test_shape.py', GUARDED.replace(
            "if __name__ == '__main__':\n    unittest.main()\n", ''))
        code, output = run_gate(self.gate)
        self.assertEqual(code, 1, f'a file that runs nothing when executed passed:\n{output}')
        self.assertIn('NOT_EXECUTABLE', output)
        self.assertIn('test_shape.py', output)

    def test_a_module_that_borrows_a_root_from_a_neighbour_is_named_for_that(self):
        tests = self.scratch('borrowed')
        self.write(tests, 'test_shape.py', GUARDED.replace(
            "sys.path.insert(0, str(REPO / 'src'))\n", ''))
        code, output = run_gate(self.gate)
        self.assertEqual(code, 1, f'an import that only works by accident passed:\n{output}')
        self.assertIn('BORROWED_IMPORT_PATH', output)

    def test_a_slice_assignment_or_an_indirect_root_variable_still_counts_as_a_bootstrap(self):
        """The two spellings this repository really uses, so the rule does not invent work."""
        tests = self.scratch('spellings')
        self.write(tests, 'test_slice.py', GUARDED.replace(
            "sys.path.insert(0, str(REPO / 'src'))",
            "sys.path[:0] = [str(REPO / 'src')]"))
        self.write(tests, 'test_indirect.py', GUARDED.replace(
            "sys.path.insert(0, str(REPO / 'src'))",
            "_ROOT = REPO / 'src'\nsys.path.insert(0, str(_ROOT))"))
        code, output = run_gate(self.gate)
        self.assertEqual(code, 0, f'both real spellings were refused:\n{output}')

    def test_a_capabilities_bootstrap_under_its_own_spelling_is_not_flagged(self):
        tests = self.scratch('capabilities')
        self.write(tests, 'test_pkg.py', GUARDED.replace(
            "sys.path.insert(0, str(REPO / 'src'))",
            "_PKG = REPO / 'packages' / 'capabilities'\n"
            "sys.path.insert(0, str(_PKG))").replace('import design_lab', 'import reconstruction'))
        code, output = run_gate(self.gate)
        self.assertEqual(code, 0, f'the capabilities root was refused:\n{output}')

    def test_a_module_with_no_test_case_is_named_for_that(self):
        tests = self.scratch('no-cases')
        self.write(tests, 'test_empty.py', GUARDED.replace(
            "    def test_the_module_exists(self):\n        self.assertTrue(design_lab is not None)\n",
            "    def helper_not_a_test(self):\n        pass\n"))
        code, output = run_gate(self.gate)
        self.assertEqual(code, 1, f'a module that collects nothing passed:\n{output}')
        self.assertIn('NO_CASES', output)

    def test_an_unparseable_module_is_a_finding_not_a_skip(self):
        tests = self.scratch('unparseable')
        self.write(tests, 'test_shape.py', GUARDED)
        self.write(tests, 'test_broken.py', 'def test(:\n')
        code, output = run_gate(self.gate)
        self.assertEqual(code, 1, f'a file that cannot even parse passed:\n{output}')
        self.assertIn('UNPARSEABLE', output)

    def test_an_empty_scan_fails_closed(self):
        tests = self.scratch('empty')
        self.assertEqual(list(tests.glob('test_*.py')), [])
        code, output = run_gate(self.gate)
        self.assertEqual(code, 1, f'scanning nothing reported success:\n{output}')
        self.assertIn('modules=0', output)

    def test_provided_roots_that_do_not_exist_cannot_make_the_gate_blind(self):
        """If both second-party roots resolved to nothing, every import would look innocent."""
        tests = self.scratch('missing-roots')
        self.write(tests, 'test_shape.py', GUARDED)
        self.gate.REPO = self.gate.REPO / 'nowhere'
        self.gate.TEST_DIR = tests
        self.gate.PROVIDED = {label: self.gate.provided_by(label)
                              for label in self.gate.SECOND_PARTY}
        code, output = run_gate(self.gate)
        self.assertEqual(code, 1, f'a gate with no known roots still passed:\n{output}')
        self.assertIn('roots_with_nothing_provided', output)


class WeakenedGateTests(unittest.TestCase):
    """The verdicts must come from the rules: break a copy of the gate and they disappear."""

    def source(self) -> str:
        return GATE_PATH.read_text(encoding='utf-8')

    def load_weakened(self, replacements) -> object:
        directory = SCRATCH_BASE / 'weakened'
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)
        source = self.source()
        for old, new in replacements:
            self.assertEqual(source.count(old), 1, f'gate anchor is not unique: {old[:50]!r}')
            source = source.replace(old, new, 1)
        ast.parse(source)
        path = directory / 'verify_test_selfsufficiency.py'
        path.write_text(source, encoding='utf-8', newline='\n')
        gate = load_gate(path)
        gate.REPO = REPO
        gate.TEST_DIR = REPO / 'design-lab' / 'tests'
        # The copy computed its own root inventory from its scratch location; re-derive it against
        # the tree this case actually judges, or the copy would fail closed for the wrong reason.
        gate.PROVIDED = {label: gate.provided_by(label) for label in gate.SECOND_PARTY}
        return gate

    def test_removing_the_entry_guard_rule_stops_convicting_the_shipped_history(self):
        tests = SCRATCH_BASE / 'weaken-target'
        if tests.exists():
            shutil.rmtree(tests)
        tests.mkdir(parents=True)
        (tests / 'src' / 'design_lab').mkdir(parents=True)
        (tests / 'src' / 'design_lab' / '__init__.py').write_text('', encoding='utf-8')
        (tests / 'packages' / 'capabilities').mkdir(parents=True)
        (tests / 'design-lab' / 'tests').mkdir(parents=True)
        unguarded = GUARDED.replace("if __name__ == '__main__':\n    unittest.main()\n", '')
        (tests / 'design-lab' / 'tests' / 'test_shape.py').write_text(unguarded, encoding='utf-8')
        shipped = load_gate()
        shipped.REPO = tests
        shipped.TEST_DIR = tests / 'design-lab' / 'tests'
        code, output = run_gate(shipped)
        self.assertEqual(code, 1, f'the shipped gate should refuse this file:\n{output}')
        self.assertIn('NOT_EXECUTABLE', output)
        weak = self.load_weakened([("        if not guarded:\n", "        if False:\n")])
        weak.REPO = tests
        weak.TEST_DIR = tests / 'design-lab' / 'tests'
        weak_code, weak_output = run_gate(weak)
        self.assertEqual(weak_code, 0,
                         f'the weakened gate still refuses, so the fixture -- not the rule -- was '
                         f'doing the work:\n{weak_output}')

    def test_removing_the_bootstrap_rule_stops_convicting_a_borrowed_import(self):
        tests = SCRATCH_BASE / 'weaken-borrowed'
        if tests.exists():
            shutil.rmtree(tests)
        (tests / 'src' / 'design_lab').mkdir(parents=True)
        (tests / 'src' / 'design_lab' / '__init__.py').write_text('', encoding='utf-8')
        (tests / 'packages' / 'capabilities').mkdir(parents=True)
        (tests / 'design-lab' / 'tests').mkdir(parents=True)
        borrowed = GUARDED.replace("sys.path.insert(0, str(REPO / 'src'))\n", '')
        (tests / 'design-lab' / 'tests' / 'test_shape.py').write_text(borrowed, encoding='utf-8')
        shipped = load_gate()
        shipped.REPO = tests
        shipped.TEST_DIR = tests / 'design-lab' / 'tests'
        code, output = run_gate(shipped)
        self.assertIn('BORROWED_IMPORT_PATH', output,
                      f'the shipped gate did not name the borrowed import:\n{output}')
        weak = self.load_weakened([("            if label in reachable:\n",
                                    "            if True:\n")])
        weak.REPO = tests
        weak.TEST_DIR = tests / 'design-lab' / 'tests'
        weak_code, weak_output = run_gate(weak)
        self.assertNotIn('BORROWED_IMPORT_PATH', weak_output,
                         'the weakened gate still convicts, so the rule was never the cause')
        self.assertEqual(weak_code, 0, weak_output)


if __name__ == '__main__':
    unittest.main()
