"""Gate: the module-dependency manifest must be reconciled against the imports the tree really makes.

Why this exists: `.project/governance/module-dependencies.json` declared `runtimeEdges: []` and "runtime
coupling forbidden" while six tracked sites in `apps/observer` import code out of
`packages/client-neutral-core` at runtime -- and `scripts/ci/verify_module_dependencies.py` validated the
JSON shape and never read an import. A manifest that nothing reads against the tree is a description, not a
gate, and this repository has been burned by exactly that shape of green.

The load-bearing assertions here are the planted ones: a synthetic cross-root import, a synthetic
`sys.path.insert` into the other root, and a synthetic `importlib.util.spec_from_file_location` whose path
reaches the other root through a module-level constant must each be convicted. The controls matter just as
much -- an intra-root import, an import of a supporting surface (`services/`, not a module root) and a
stdlib import must NOT be convicted, or the scanner is only loud and not accurate.

Fixture roots come from `project_temp.fixture_dir`, the project's bounded helper (ERR-163): scratch stays
inside `.project-local/runs/` and a failed release is reported instead of swallowed.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci" / "verify_module_dependencies.py"
MANIFEST = ROOT / ".project" / "governance" / "module-dependencies.json"
PROJECT_TEMP = ROOT / "packages" / "client-neutral-core" / "scripts" / "project_temp.py"

_spec = importlib.util.spec_from_file_location("verify_module_dependencies", SCRIPT)
deps = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(deps)  # type: ignore[attr-defined]

_pt_spec = importlib.util.spec_from_file_location("project_temp", PROJECT_TEMP)
project_temp = importlib.util.module_from_spec(_pt_spec)
assert _pt_spec.loader is not None
_pt_spec.loader.exec_module(project_temp)  # type: ignore[attr-defined]

WORKFLOW = "workflow-assistance"
OBSERVER = "work-lab-observer"
WORKFLOW_ROOT = "packages/client-neutral-core"
OBSERVER_ROOT = "apps/observer"


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def manifest(edges: list[dict]) -> dict:
    return {
        "schemaVersion": "work-lab-module-dependencies/v1",
        "dependencyTypes": ["governance", "runtime", "build", "handoff", "observed-by",
                            "fixture", "archive-of"],
        "modules": {
            WORKFLOW: {"path": WORKFLOW_ROOT, "dependencies": [], "observedBy": [OBSERVER]},
            OBSERVER: {"path": OBSERVER_ROOT,
                       "dependencies": [{"module": WORKFLOW, "types": ["governance"]}],
                       "observedBy": []},
        },
        "runtimeEdges": edges,
        "policy": {
            "crossModuleRuntimeCoupling": "forbidden-unless-explicitly-approved",
            "buildAndHandoffAreNotRuntimeDependencies": True,
            "observedByIsReadOnly": True,
            "runtimeEdgesAreReconciledAgainstRealImports": True,
        },
    }


def fixture_repo(root: Path, *, observer_source: str, edges: list[dict] | None = None) -> Path:
    """A two-root tree: a producer module, a consumer file, and the manifest judging it."""
    write(root, f"{WORKFLOW_ROOT}/scripts/canonical_store.py", "class CanonicalStore:\n    pass\n")
    write(root, f"{WORKFLOW_ROOT}/scripts/project_temp.py", "def inside_project(p):\n    return True\n")
    write(root, "services/orchestration/sidecar.py", "class WorkflowSidecar:\n    pass\n")
    write(root, f"{OBSERVER_ROOT}/scripts/write_artifact_receipt.py", "def write_receipt():\n    return {}\n")
    write(root, f"{OBSERVER_ROOT}/src/observer_store.py", observer_source)
    (root / ".project" / "governance").mkdir(parents=True, exist_ok=True)
    (root / ".project/governance/module-dependencies.json").write_text(
        json.dumps(manifest(edges if edges is not None else []), indent=2), encoding="utf-8")
    return root


def edge_site(file: str, line: int = 1, form: str = "from-import") -> dict:
    return {"from": OBSERVER, "to": WORKFLOW, "coupling": "runtime-import",
            "basis": "fixture basis", "authority": "fixture authority",
            "sites": [{"file": file, "line": line, "form": form, "symbols": ["canonical_store"]}]}


class LiveTreeTests(unittest.TestCase):
    """The tree as it stands must be clean, and clean for the right reason."""

    def run_verifier(self) -> tuple[int, str]:
        proc = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
        return proc.returncode, proc.stdout + proc.stderr

    def test_the_live_manifest_passes_the_reconciled_gate(self) -> None:
        code, out = self.run_verifier()
        self.assertEqual(0, code, out)
        self.assertIn("MODULE_DEPENDENCIES_PASS", out)
        self.assertNotIn("MODULE_DEPS_UNDECLARED", out)
        self.assertNotIn("MODULE_DEPS_STALE", out)

    def test_the_scan_is_not_a_green_nothing(self) -> None:
        """Every site named in the task's defect report has to be found by name.

        A scanner that reports zero edges on this tree would exit 0 and prove nothing, so the sites it
        must convict are pinned here: the bare-stem import, the sys.path inserts and the importlib-by-path
        load of the boundary helper.
        """
        measured = deps.scan_edges(ROOT)
        found = {(edge["file"], edge["form"]) for edge in measured}
        for file, form in (
            ("apps/observer/src/observer_store.py", "from-import"),
            ("apps/observer/tests/test_observer_store.py", "from-import"),
            ("apps/observer/tests/test_observer_store.py", "sys.path"),
            ("apps/observer/scripts/u19_webview_e2e.py", "sys.path"),
            ("apps/observer/scripts/u19_chromium_readback.py", "sys.path"),
            ("apps/observer/scripts/window_state_readback.py", "importlib-by-path"),
        ):
            self.assertIn((file, form), found, f"{file} [{form}] is not in {sorted(found)}")

    def test_the_manifest_declares_every_measured_site(self) -> None:
        measured = deps.scan_edges(ROOT)
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        declared_sites = {site["file"] for edge in data["runtimeEdges"] for site in edge["sites"]}
        self.assertEqual(declared_sites, {edge["file"] for edge in measured},
                         "the declared site set and the measured site set have to be the same set")
        self.assertEqual({(edge["from"], edge["to"]) for edge in measured},
                         {(edge["from"], edge["to"]) for edge in data["runtimeEdges"]})

    def test_the_producer_does_not_import_the_consumer(self) -> None:
        """Direction is the point of the decoupling rule: observer reads workflow, never the reverse."""
        for edge in deps.scan_edges(ROOT):
            self.assertNotEqual((edge["from"], edge["to"]), (WORKFLOW, OBSERVER),
                                f"{edge['file']}:{edge['line']} imports the consumer module from the "
                                "producer, which no dependency entry approves")

    def test_every_declared_site_carries_a_basis_and_an_authority(self) -> None:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for edge in data["runtimeEdges"]:
            self.assertTrue(str(edge.get("basis", "")).strip(), "an edge without a basis is not approved")
            self.assertTrue(str(edge.get("authority", "")).strip(),
                            "an edge without an authority is a self-granted exemption")


class PlantedEdgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = project_temp.fixture_dir(prefix="wl-moddeps-")
        self.addCleanup(self._release)

    def _release(self) -> None:
        if not project_temp.force_release(self.tmp):
            self.fail(f"fixture root was not released: {self.tmp}")

    def measure(self, observer_source: str, edges: list[dict] | None = None):
        root = fixture_repo(self.tmp, observer_source=observer_source, edges=edges)
        return deps.scan_edges(root), deps.reconcile(root)

    def run_main(self) -> tuple[int, str]:
        """`main()` on the fixture, with its report captured instead of shouted into the test log."""
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = deps.main(["--root", str(self.tmp)])
        return code, buffer.getvalue()

    def test_a_planted_cross_root_import_is_convicted(self) -> None:
        measured, (all_edges, undeclared, stale) = self.measure(
            "from canonical_store import CanonicalStore\n")
        self.assertEqual(1, len([e for e in all_edges if e["file"].endswith("observer_store.py")]),
                         f"the planted import was not measured: {measured}")
        self.assertEqual([], stale)
        self.assertEqual(1, len(undeclared), undeclared)
        self.assertIn("apps/observer/src/observer_store.py", undeclared[0])

    def test_the_verifier_exits_nonzero_and_names_the_count(self) -> None:
        fixture_repo(self.tmp, observer_source="from canonical_store import CanonicalStore\n")
        code, out = self.run_main()
        self.assertEqual(1, code, out)
        self.assertIn("MODULE_DEPS_FAIL undeclared_edges=1", out)
        self.assertNotIn("MODULE_DEPENDENCIES_PASS", out)

    def test_a_planted_sys_path_into_the_other_root_is_convicted(self) -> None:
        source = ("import sys\n"
                  'sys.path.insert(0, str(__import__("pathlib").Path("/nowhere") /\n'
                  '                   "packages" / "client-neutral-core" / "scripts"))\n')
        _, (_, undeclared, _) = self.measure(source)
        self.assertEqual(1, len(undeclared), undeclared)
        self.assertIn("sys.path", undeclared[0])

    def test_a_planted_importlib_load_by_constant_path_is_convicted(self) -> None:
        """The real site reaches the loader through a module-level constant, so the scan must follow it."""
        source = ("import importlib.util\n"
                  'HELPER = ("/nowhere" / "packages" / "client-neutral-core" / "scripts" / "project_temp.py")\n'
                  "def load():\n"
                  '    return importlib.util.spec_from_file_location("project_temp", HELPER)\n')
        measured, (_, undeclared, _) = self.measure(source)
        forms = {edge["form"] for edge in measured if edge["file"].endswith("observer_store.py")}
        self.assertIn("importlib-by-path", forms, f"the planted loader was not measured: {measured}")
        self.assertEqual(1, len(undeclared), undeclared)

    def test_a_declared_edge_that_no_longer_exists_is_stale(self) -> None:
        """Reconciliation runs both ways: a declaration without an import is a claim about nothing."""
        fixture_repo(self.tmp, observer_source="import json\n",
                     edges=[edge_site("apps/observer/src/observer_store.py")])
        code, out = self.run_main()
        self.assertEqual(1, code, out)
        self.assertIn("MODULE_DEPS_STALE", out)

    def test_a_declared_site_that_still_imports_is_enough(self) -> None:
        fixture_repo(self.tmp, observer_source="from canonical_store import CanonicalStore\n",
                     edges=[edge_site("apps/observer/src/observer_store.py", line=99)])
        code, out = self.run_main()
        self.assertEqual(0, code, out)

    # --- controls: the scanner must be accurate, not merely loud -------------------------------
    def test_an_intra_root_import_is_not_convicted(self) -> None:
        _, (_, undeclared, _) = self.measure(
            "import sys\n"
            'sys.path.insert(0, str(__import__("pathlib").Path("/nowhere") / "apps" / "observer" / "scripts"))\n'
            "from write_artifact_receipt import write_receipt\n")
        self.assertEqual([], undeclared, "an observer file importing observer code is not a cross-root edge")

    def test_a_supporting_surface_import_is_not_convicted(self) -> None:
        """`services/` is an active source surface, not a canonical module root (module-ownership.json)."""
        _, (_, undeclared, _) = self.measure(
            "import sys\n"
            'sys.path.insert(0, str(__import__("pathlib").Path("/nowhere") / "services" / "orchestration"))\n'
            "from sidecar import WorkflowSidecar\n")
        self.assertEqual([], undeclared, undeclared)

    def test_a_stdlib_import_is_not_convicted(self) -> None:
        _, (_, undeclared, _) = self.measure("import json\nimport hashlib\nfrom pathlib import Path\n")
        self.assertEqual([], undeclared, undeclared)


if __name__ == "__main__":
    unittest.main()
