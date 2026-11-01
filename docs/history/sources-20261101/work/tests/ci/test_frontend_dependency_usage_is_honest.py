"""Gate: the observer front-end manifest must match the code that actually ships.

`npm ci` (CI, ``work-lab-gate.yml``) already fails a lock that disagrees with ``package.json``, so
that axis needs no second checker. Two axes were unguarded, both measured 2026-10-26 while closing
audit finding P2-7: a dependency that is declared, installed and imported by nobody (``recharts`` sat
in the manifest while no file rendered a chart, costing install time and a licence surface for nothing
that existed), and an import that resolves only because a transitive install happened to provide it,
which builds locally and dies on a clean runner.

The census line is the durable half: ``imported`` is counted from the files on disk, so a checker that
quietly stopped reading any suffix would show a drop here instead of passing. The planted fixtures below
are the falsifiers -- a checker that could not convict them would be guarding nothing.

Discovered dynamically by ``run_quality_gate.py governance``.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci" / "verify_frontend_dependency_usage.py"
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))
import project_temp  # noqa: E402


def _load():
    spec = importlib.util.spec_from_file_location("verify_frontend_dependency_usage", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VDF = _load()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture(root: Path, dependencies: dict, sources: dict[str, str]) -> Path:
    _write(root / "package.json", json.dumps(
        {"name": "fixture-frontend", "dependencies": dependencies, "devDependencies": {}}, indent=2))
    for rel, text in sources.items():
        _write(root / rel, text)
    return root


class RealManifestTests(unittest.TestCase):
    """The shipped front-end must agree today, on the numbers this run measured."""

    def test_the_shipped_manifest_has_neither_unused_dependency_nor_undeclared_import(self) -> None:
        report = VDF.audit(VDF.DEFAULT_FRONTEND)
        self.assertEqual([], report["unused"], f"a declared dependency imports nothing: {report['unused']}")
        self.assertEqual([], report["undeclared"], f"an import is not in the manifest: {report['undeclared']}")
        self.assertEqual(7, report["production_dependencies"],
                         "the production dependency population changed; re-derive it before bumping")
        self.assertGreaterEqual(report["imported_names"], 12,
                                "the scanner found fewer importers than the tree carries; it is going blind")


class PlantedFaultTests(unittest.TestCase):
    """Each direction must be able to fail, on bytes this test controls."""

    def setUp(self) -> None:
        self.root = project_temp.fixture_dir(prefix="vdf-")

    def tearDown(self) -> None:
        project_temp.force_release(self.root)

    def test_a_declared_but_imported_by_nobody_dependency_is_convicted(self) -> None:
        fixture = _fixture(self.root / "unused", {
            "react": "^18.0.0",
            "recharts": "^2.1.0",
        }, {"src/App.tsx": "import React from 'react'\nexport const A = () => null\n"})
        report = VDF.audit(fixture)
        self.assertEqual(["recharts"], report["unused"],
                         "an installed dependency nobody imports slipped through")
        self.assertEqual([], report["undeclared"])

    def test_an_import_absent_from_the_manifest_is_convicted_by_file_and_line_of_origin(self) -> None:
        fixture = _fixture(self.root / "undeclared", {
            "react": "^18.0.0",
        }, {
            "src/App.tsx": "import React from 'react'\nexport const A = () => null\n",
            "src/Motion.tsx": "import { motion } from 'framer-motion'\nexport const M = motion\n",
        })
        report = VDF.audit(fixture)
        self.assertEqual(1, len(report["undeclared"]), f"expected one undeclared import: {report['undeclared']}")
        self.assertIn("framer-motion", report["undeclared"][0])
        self.assertIn("Motion.tsx", report["undeclared"][0],
                      "the refusal must name the file that pulled the undeclared import")
        self.assertEqual([], report["unused"])

    def test_a_control_fixture_that_is_consistent_passes(self) -> None:
        fixture = _fixture(self.root / "clean", {
            "react": "^18.0.0",
            "framer-motion": "^11.0.0",
        }, {
            "src/App.tsx": "import React from 'react'\nimport { motion } from 'framer-motion'\n"
                           "export const A = [React, motion]\n",
        })
        report = VDF.audit(fixture)
        self.assertEqual([], report["unused"])
        self.assertEqual([], report["undeclared"])


class ScannerPrecisionTests(unittest.TestCase):
    """The reader must not mistake prose or a builtin for a package claim."""

    def setUp(self) -> None:
        self.root = project_temp.fixture_dir(prefix="vdf-")

    def tearDown(self) -> None:
        project_temp.force_release(self.root)

    def test_prose_and_builtins_and_aliases_are_not_imports(self) -> None:
        fixture = _fixture(self.root / "prose", {
            "react": "^18.0.0",
        }, {
            "src/Notes.tsx": "import React from 'react'\n"
                             "// the count is derived from 'injected but invisible' rows\n"
                             "const url = 'published at https://api.github.com/repos/x/y'\n"
                             "const p = 'read with node:fs at startup'\n",
            "src/Alias.ts": "import { Drawer } from '@/components/drawer'\nexport { Drawer }\n",
            "vite.config.ts": "import { defineConfig } from 'vite'\nimport react from '@vitejs/plugin-react'\n"
                              "export default defineConfig({ plugins: [react()] })\n",
        })
        imports = VDF.imported_names(fixture)
        self.assertIn("react", imports)
        for bogus in ("injected", "https:", "node:", "from"):
            self.assertNotIn(bogus, imports, f"prose was read as a package: {bogus}")
        self.assertNotIn("@/components", " ".join(imports))

    def test_a_scoped_subpath_import_resolves_to_its_manifest_key(self) -> None:
        fixture = _fixture(self.root / "scoped", {
            "@testing-library/react": "^16.0.0",
        }, {"src/a.test.tsx": "import { render } from '@testing-library/react'\n"})
        self.assertEqual(["@testing-library/react"], sorted(VDF.imported_names(fixture)))
        self.assertEqual([], VDF.audit(fixture)["undeclared"])

    def test_a_built_output_tree_is_never_counted_as_a_consumer(self) -> None:
        """Otherwise a stale bundle keeps an unused dependency looking used."""
        fixture = _fixture(self.root / "dist", {
            "react": "^18.0.0",
            "recharts": "^2.1.0",
        }, {
            "src/App.tsx": "import React from 'react'\nexport const A = React\n",
            "dist/assets/index.js": "import{a as r}from'recharts';export default r\n",
        })
        self.assertEqual(["recharts"], VDF.audit(fixture)["unused"],
                         "the scanner credited a built bundle instead of the source")


if __name__ == "__main__":
    unittest.main(verbosity=2)
