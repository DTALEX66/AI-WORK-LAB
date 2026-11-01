"""Mandatory gate: a canonical store's runtime root must be the one the boundary declares.

`.project/governance/project-data-boundary.json` declares ``runtimeRoot: .project-local/runs`` and AGENTS.md
forbids content this project produces from spilling outside the Git root. Until 2026-10-10 three tracked
CLIs defaulted that root to ``tempfile.gettempdir()`` -- so ``collectors.py``, ``active_projects.py`` and
``project_registry.py`` each created ``canonical.sqlite`` in the user's temp directory on a bare invocation,
and ``durable_worker.py`` accepted ANY root it was handed. A declared boundary that the entry point does not
enforce is a comment, and a %TEMP% store is invisible to the spill sweep while outliving the checkout.

The scan targets the *shape* of the defect -- an assignment to a ``*runtime_root*`` name whose value reaches
``gettempdir()`` -- so the residue cleaner in scripts/maintenance, which legitimately reads the system temp
directory to delete it, is not convicted. That distinction is asserted both ways below.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "packages" / "client-neutral-core" / "scripts"
BOUNDARY = ROOT / ".project" / "governance" / "project-data-boundary.json"
WORKER = ROOT / "services" / "orchestration" / "durable_worker.py"
ENTRY_POINTS = (
    ROOT / "packages/client-neutral-core/scripts/collectors.py",
    ROOT / "packages/client-neutral-core/scripts/active_projects.py",
    ROOT / "packages/client-neutral-core/scripts/project_registry.py",
    WORKER,
)
SKIP_PREFIXES = (".project-local/", "taskpacks/history/", "docs/history/", "reports/audit-archive/")


def load_project_temp():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("project_temp_for_root_gate", SCRIPTS / "project_temp.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROJECT_TEMP = load_project_temp()


def tracked_python() -> list[Path]:
    raw = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True).stdout
    names = raw.decode("utf-8", "replace").split("\0")
    return [Path(n) for n in names
            if n.endswith(".py") and not n.startswith(SKIP_PREFIXES)]


def runtime_root_findings(source: str, label: str) -> list[str]:
    """Assignments to a *runtime_root* name whose value reaches tempfile.gettempdir()."""
    findings: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"{label}: unparsable ({exc})"]
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, ast.Assign):
            targets = [t for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and isinstance(node.target, ast.Name):
            targets = [node.target]
        for target in targets:
            if "runtime_root" not in target.id.lower():
                continue
            for sub in ast.walk(node.value):
                name = getattr(sub, "id", None) or getattr(sub, "attr", None)
                if name == "gettempdir":
                    findings.append(f"{label}:{node.lineno}: {target.id} is built from "
                                    f"tempfile.gettempdir() -- the store leaves the project root")
                    break
    return findings


def bare_temporary_directory_findings(source: str) -> list[int]:
    """Line numbers of ``TemporaryDirectory()`` calls with no ``dir=`` -- the leak-when-busy shape."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "TemporaryDirectory":
            if not any(keyword.arg == "dir" for keyword in node.keywords):
                lines.append(node.lineno)
    return lines


BAD_FIXTURE = 'runtime_root = (args.runtime_root or Path(tempfile.gettempdir()) / "x").resolve()\n'
GOOD_FIXTURE = ('runtime_root = require_runtime_root(args.runtime_root, "x")\n'
                'temp = Path(tempfile.mkdtemp(prefix="auth-ref-", dir=str(scratch_root())))\n')


class RuntimeRootBoundaryTests(unittest.TestCase):
    def test_the_declared_runtime_root_is_the_boundary_path_and_is_inside_the_repo(self) -> None:
        declared = json.loads(BOUNDARY.read_text(encoding="utf-8"))["runtimeRoot"]
        self.assertEqual((ROOT / declared).resolve(), PROJECT_TEMP.declared_runtime_root())
        self.assertTrue(PROJECT_TEMP.inside_project(PROJECT_TEMP.declared_runtime_root()))

    def test_no_tracked_source_builds_a_runtime_root_from_the_system_temp(self) -> None:
        offenders: list[str] = []
        scanned = 0
        for path in tracked_python():
            text = (ROOT / path).read_text(encoding="utf-8", errors="replace")
            if "runtime_root" not in text and "runtime-root" not in text:
                continue
            scanned += 1
            offenders.extend(runtime_root_findings(text, str(path.as_posix())))
        self.assertEqual([], offenders, f"{scanned} runtime-root-carrying files scanned")
        self.assertGreaterEqual(scanned, 4,
                                "fewer files mention a runtime root than the four entry points; the scan "
                                "input set has shrunk and a clean result would mean nothing")

    def test_the_predicate_convicts_the_shipped_defect_and_absolves_the_residue_cleaner(self) -> None:
        self.assertTrue(any("is built from tempfile.gettempdir()" in line
                            for line in runtime_root_findings(BAD_FIXTURE, "synthetic.py")))
        self.assertEqual([], runtime_root_findings(GOOD_FIXTURE, "synthetic.py"))
        # the real residue cleaner legitimately reads %TEMP% in order to empty it; it must stay green
        cleaner = ROOT / "scripts/maintenance/release_authority_reference_temp_residue.py"
        self.assertEqual([], runtime_root_findings(
            cleaner.read_text(encoding="utf-8", errors="replace"), cleaner.name))

    def outside_probe_root(self) -> Path:
        """A root outside the repository by construction, not by environment.

        ``tempfile.gettempdir()`` cannot be used here: the canonical gate runner binds TMP/TEMP/TMPDIR to
        ``.project-local/runs/tmp``, so a temp-based 'outside' path would resolve INSIDE the project under
        CI and the refusal assertion would test nothing.
        """
        return ROOT.parent / "work-lab-runtime-root-refusal-probe"

    def test_the_shared_predicate_refuses_a_root_outside_the_project(self) -> None:
        outside = self.outside_probe_root()
        self.assertFalse(PROJECT_TEMP.inside_project(outside))
        self.assertFalse(outside.exists(), "the probe root must start absent or the post-check means nothing")
        with self.assertRaises(RuntimeError) as refused:
            PROJECT_TEMP.require_runtime_root(outside, "workflow-assistance-worker")
        self.assertIn("RUNTIME_ROOT_ESCAPES_PROJECT", str(refused.exception))
        self.assertFalse(outside.exists(), "the refusal must precede any mkdir")
        inside = PROJECT_TEMP.require_runtime_root(None, "gate-probe-runtime")
        self.assertTrue(PROJECT_TEMP.inside_project(inside))
        self.assertTrue(inside.is_relative_to(PROJECT_TEMP.declared_runtime_root()),
                        f"{inside} is not under the declared runtime root")

    def test_the_worker_cli_refuses_an_outside_root_instead_of_writing_there(self) -> None:
        outside = self.outside_probe_root()
        self.assertFalse(outside.exists(), "the probe root must start absent or the post-check means nothing")
        try:
            result = subprocess.run(
                [sys.executable, str(WORKER), "--runtime-root", str(outside),
                 "--project-root", str(ROOT), "--once"],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
            self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("RUNTIME_ROOT_ESCAPES_PROJECT", result.stdout + result.stderr)
            self.assertFalse(outside.exists(),
                             "the worker built its store outside the project before refusing")
        finally:
            if outside.exists():  # a broken guard made this probe's own residue; it is mine to remove
                shutil.rmtree(outside, ignore_errors=True)

    def test_every_entry_point_routes_through_the_shared_predicate(self) -> None:
        """Four files must not each re-implement the boundary test (share the predicate, not the tokens)."""
        for path in ENTRY_POINTS:
            text = path.read_text(encoding="utf-8")
            self.assertIn("require_runtime_root", text,
                          f"{path.name} resolves a runtime root without the shared predicate")


    def test_production_source_creates_no_temporary_directory_outside_the_boundary(self) -> None:
        """A self-cleaning fixture is only clean while cleanup succeeds -- so production must not use it.

        ``tests/workflow-assistance/test_temp_fixture_stays_inside_the_boundary.py`` deliberately scoped
        itself to ``mkdtemp`` on the reasoning that ``TemporaryDirectory()`` removes itself. Measured
        2026-10-10 that reasoning does not hold on this machine: the user temp root held 25 ``tmp*``
        directories containing 2 canonical.sqlite stores, 18 git-metadata files and 6,495,636 B, and
        ``C:\\Windows\\TEMP`` 5 more with 405,598 B -- residue of exactly this call shape, whose cleanup
        fails on Windows when a sqlite handle is still open. Production (non-test) source is held to zero
        here; the test suite's own 305 sites are reported, not required to be any number, because a floor
        that can only be met while the debt exists is a guard that cannot survive its own success.
        """
        production: list[str] = []
        fixtures = 0
        for path in tracked_python():
            text = (ROOT / path).read_text(encoding="utf-8", errors="replace")
            if "TemporaryDirectory" not in text:
                continue
            for finding in bare_temporary_directory_findings(text):
                if "tests/" in path.as_posix():
                    fixtures += 1
                else:
                    production.append(f"{path.as_posix()}:{finding}")
        self.assertEqual([], production,
                         f"production source still builds fixtures in the system temp directory")
        self.assertGreaterEqual(fixtures, 0, "the counter exists to be reported, not to pass a floor")
        print(f"TEST_SIDE_BARE_TEMPORARYDIRECTORY={fixtures}")

    def test_the_fixture_root_helper_stays_inside_and_releases(self) -> None:
        with PROJECT_TEMP.fixture_root(prefix="gate-fixture-root-") as path:
            self.assertTrue(PROJECT_TEMP.inside_project(path), str(path))
            self.assertTrue(path.is_relative_to(PROJECT_TEMP.declared_runtime_root()), str(path))
            (path / "probe.txt").write_text("x", encoding="utf-8")
        self.assertFalse(path.exists(), f"fixture_root left {path} behind")

    def test_the_temporary_directory_predicate_convicts_and_absolves_its_own_shapes(self) -> None:
        self.assertEqual([1], bare_temporary_directory_findings(
            'with tempfile.TemporaryDirectory() as raw:\n    pass\n'))
        self.assertEqual([], bare_temporary_directory_findings(
            'with tempfile.TemporaryDirectory(dir=str(scratch_root())) as raw:\n    pass\n'))
        self.assertEqual([], bare_temporary_directory_findings(
            'with project_temp.fixture_root(prefix="x-") as raw:\n    pass\n'))


if __name__ == "__main__":
    unittest.main()
