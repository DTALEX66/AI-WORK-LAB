"""Gate: a throwaway fixture directory must not be created outside the project boundary.

ERR-140: `tests/ci/test_project_authority_reference.py` built its copy of the live authority package
with a bare `tempfile.mkdtemp(prefix="auth-ref-")`. `tearDown` did call `shutil.rmtree(...,
ignore_errors=True)`, and on this machine that swallow let nineteen complete mirrors of
`WORK-LAB-AUTHORITY.md`, both authority indexes, the open-task register, the error ledger and the
current taskcards sit in `%TEMP%` — 304 files / 7,126,653 bytes of governance material outside the
Git root, which `.project/governance/project-data-boundary.json` forbids ("all content this project
produces — builds, caches, temp files, evidence … stays locked inside the project Git root"). The
residue was released by `scripts/maintenance/release_authority_reference_temp_residue.py` after a
per-file manifest and an archive of the contents that differed from the live tree; the root cause is
the `dir=` argument this gate now enforces for its own file.

`mkdtemp` is the target because it leaks unless someone remembers to remove it.
`tempfile.TemporaryDirectory()` deletes itself on context exit, so 300+ of those are not the defect
class here and are deliberately out of scope.

Matching is done on the syntax tree, not on line text: the docstring of the fixed file *mentions*
`mkdtemp(prefix="auth-ref-")`, and a textual matcher reports prose as a violation.

Discovered dynamically by `run_quality_gate.py governance`.
"""
from __future__ import annotations

import ast
import subprocess
import unittest
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXED = "tests/ci/test_project_authority_reference.py"

# Same-module debt: test helpers that build fixtures. Listed so the count is visible and can shrink.
# Closed 2026-10-08: the 21 sites across these 12 files were measured by this gate's own scan and all now
# go through project_temp.fixture_dir() or an explicit in-repo dir=. The table stays as the empty set the
# scan must agree with, so a new bare call anywhere in tracked source fails here instead of being absorbed
# into a tolerance.
DEBT_TESTS: dict[str, int] = {}
# Cross-module debt: closed 2026-10-07 under the subordinate cross-module card
# (WORK-LAB-QODER-FULLSTACK-EXECUTION-CROSS-MODULE-TASKCARD-20261007). Seven bare sites in three
# production self-checks were the ones that actually spilled — they run outside the gate runner, so
# the gate's TMPDIR binding never applied to them. They now go through
# `packages/client-neutral-core/scripts/project_temp.py`, and `gate.py` additionally had to close the
# SQLite handles it never released (a Windows fixture with an open connection cannot be removed).
FIXED_PRODUCTION = {
    "packages/client-neutral-core/scripts/platform_collector.py",
    "packages/client-neutral-core/scripts/verify_gate_runtime_convergence.py",
    "services/session-federation/gate.py",
}


def tracked_python() -> list[str]:
    raw = subprocess.run(["git", "-c", "core.quotePath=false", "ls-files", "-z", "*.py"],
                         cwd=ROOT, capture_output=True).stdout.split(b"\0")
    return [p.decode("utf-8", "replace") for p in raw if p]


def bare_mkdtemp_calls(source: str) -> list[int]:
    """Line numbers of `mkdtemp(...)` calls in this source that pass no `dir=` keyword."""
    found = []
    with warnings.catch_warnings():
        # several parsed modules carry invalid escape sequences in their own docstrings; that is
        # their business, and letting it print once per file buries the gate's actual output
        warnings.simplefilter("ignore", SyntaxWarning)
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return found
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = (func.attr if isinstance(func, ast.Attribute)
                else func.id if isinstance(func, ast.Name) else "")
        if name != "mkdtemp":
            continue
        if any(kw.arg == "dir" for kw in node.keywords):
            continue
        found.append(node.lineno)
    return found


def scan() -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for rel in tracked_python():
        path = ROOT / rel
        if not path.is_file():
            continue
        lines = bare_mkdtemp_calls(path.read_text(encoding="utf-8", errors="replace"))
        if lines:
            out[rel] = lines
    return out


class TempFixtureBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sites = scan()

    def test_the_matcher_distinguishes_a_call_from_a_sentence_about_a_call(self) -> None:
        self.assertEqual(bare_mkdtemp_calls('tmp = tempfile.mkdtemp(prefix="x-")'), [1])
        self.assertEqual(bare_mkdtemp_calls('tempfile.mkdtemp(dir=ROOT)'), [])
        self.assertEqual(bare_mkdtemp_calls('# an earlier version used mkdtemp(prefix="auth-ref-")'), [])
        self.assertEqual(bare_mkdtemp_calls('from tempfile import mkdtemp\nmkdtemp()'), [2])
        # a local name shadowing mkdtemp is treated as a call too: over-reporting is the safe side of
        # a boundary gate, so this is the documented behaviour rather than a precision bug
        self.assertEqual(bare_mkdtemp_calls('mkdtemp = 1\nmkdtemp(3)'), [2])

    def test_the_file_that_leaked_is_now_clean(self) -> None:
        self.assertNotIn(FIXED, self.sites,
                         "the ERR-140 offender is bare again: pass dir= inside .project-local/runs")
        source = (ROOT / FIXED).read_text(encoding="utf-8")
        self.assertIn("dir=_runtime_root()", source, "the fixture no longer pins its temp root")

    def test_every_remaining_bare_site_is_a_named_debt_that_can_only_shrink(self) -> None:
        pinned = dict(DEBT_TESTS)
        measured = {f: len(lines) for f, lines in self.sites.items()}
        new = {f: n for f, n in measured.items() if f not in pinned}
        self.assertEqual(new, {}, f"unadjudicated bare mkdtemp sites: {new}")
        for f, n in measured.items():
            self.assertLessEqual(n, pinned[f],
                                 f"{f} grew from {pinned[f]} to {n} bare mkdtemp sites")

    def test_the_closed_production_sites_stay_closed(self) -> None:
        for rel in FIXED_PRODUCTION:
            self.assertNotIn(rel, self.sites, f"{rel} went back to a bare mkdtemp")
            self.assertTrue((ROOT / rel).is_file(), f"{rel} disappeared from the tree")
        self.assertTrue((ROOT / "packages/client-neutral-core/scripts/project_temp.py").is_file(),
                        "the bounded fixture helper the closed sites depend on is missing")

    def test_the_matcher_is_still_competent_and_the_scan_still_sees_the_tree(self) -> None:
        """Anti-vacuity without a debt floor: prove the guard can still see a violation.

        This test used to assert `sum(DEBT_TESTS.values()) >= 20`, which is only satisfiable while the
        debt exists -- paying it off would have forced a fake number rather than a clean tree. The real
        question was never "is the count big enough" but "would this gate notice a new bare mkdtemp at
        all", so the positive controls are now on the matcher itself, plus a scope check proving the
        walk is not silently empty. A zero result with a wide scope means no debt; a zero result with a
        blind matcher means nothing.
        """
        self.assertEqual(bare_mkdtemp_calls("x = tempfile.mkdtemp()\n"), [1])
        self.assertEqual(bare_mkdtemp_calls("x = mkdtemp()\n"), [1])
        self.assertEqual(bare_mkdtemp_calls("x = tempfile.mkdtemp(dir=str(root))\n"), [])
        self.assertEqual(bare_mkdtemp_calls("x = tempfile.mkdtemp(prefix='p', dir=d)\n"), [])
        # a call buried in the middle of a real body must still be found at the right line
        nested = "def f():\n    with a:\n        t = tempfile.mkdtemp()\n    return t\n"
        self.assertEqual(bare_mkdtemp_calls(nested), [3])
        self.assertGreater(len(tracked_python()), 100,
                           "the scan sees almost no tracked python -- a zero debt result would mean nothing")
        self.assertGreaterEqual(len(scan()), 0)
        self.assertEqual(DEBT_TESTS, {}, "the debt table must list exactly the sites the scan finds")
        self.assertEqual(scan(), {}, "unadjudicated bare mkdtemp sites appeared: %s" % scan())

    def test_the_releaser_and_recovery_tools_exist_for_their_register_citations(self) -> None:
        for tool in ("scripts/maintenance/release_authority_reference_temp_residue.py",
                     "scripts/maintenance/recover_shared_root_original.py",
                     "scripts/audit/outside_root_spill_sweep.py"):
            self.assertTrue((ROOT / tool).is_file(), f"{tool} is cited by the register but missing")


if __name__ == "__main__":
    unittest.main()
