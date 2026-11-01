# SPDX-License-Identifier: MIT
"""DL-R5-003 acceptance: a missing dependency must not look like a broken product.

Measured failure mode this guards against: run the suite with an interpreter that
lacks scikit-image and `packages/capabilities/reconstruction/metrics.py` fails to
import, so unittest surfaces it as `unittest.loader._FailedTest` -- 43 errors and
11 failures that read as product defects. The wrapper still exits 0 in some call
paths, and the only signal that the environment was wrong is the test count
dropping (1807 -> 1734 observed on 2026-10-06). Nothing in the repo distinguished
"dependency absent" from "code broken"; `design_layer.py:62` catches
ModuleNotFoundError for an unrelated purpose.

This test runs first-class in the same suite, so the diagnosis appears by name
instead of being buried under import errors.

The requirement list is READ FROM pyproject.toml rather than duplicated here: a
test that hardcodes its own dependency list drifts silently the moment someone
adds a dependency to the package. The distribution->module map is asserted to
cover every declared dependency, so an unmapped new dependency fails loudly
instead of going unchecked.
"""
import importlib
import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Distribution name -> top-level import name. Only where they differ from the
# lowercased distribution name does an entry matter; anything absent is attempted
# under the lowercased name and, if that fails, is reported as unmapped.
MODULE_OVERRIDES = {
    "scikit-image": "skimage",
    "pillow": "PIL",
    "defusedxml": "defusedxml",
    "jsonschema": "jsonschema",
    "numpy": "numpy",
}


def declared_dependencies(pyproject: Path) -> list[str]:
    """Names from the [project] dependencies array, without version specifiers."""
    text = pyproject.read_text(encoding="utf-8")
    block = re.search(r"^dependencies\s*=\s*\[(.*?)\]", text, re.M | re.S)
    if not block:
        raise AssertionError("no [project] dependencies array found in pyproject.toml")
    names = re.findall(r"['\"]\s*([A-Za-z0-9._-]+)\s*(?:[<>=!~;\[]|$)", block.group(1))
    return [n for n in names if n and not n.startswith("#")]


def resolve_module(dist: str) -> str:
    """Distribution names are not import names. Beyond the explicit overrides, a
    hyphen in a distribution name becomes an underscore in the module, and the
    falsification test caught this being missed: without it any hyphenated
    dependency would be reported as absent forever."""
    name = dist.strip().lower()
    if name in MODULE_OVERRIDES:
        return MODULE_OVERRIDES[name]
    return name.replace("-", "_")


def missing_dependencies(deps) -> list[tuple[str, str]]:
    """(distribution, import name) pairs that this interpreter cannot import."""
    out = []
    for dist in deps:
        mod = resolve_module(dist)
        try:
            importlib.import_module(mod)
        except ImportError:
            out.append((dist.strip(), mod))
    return out


class TestEnvironmentGuardTests(unittest.TestCase):
    def test_every_declared_dependency_is_importable(self):
        deps = declared_dependencies(REPO / "pyproject.toml")
        self.assertGreaterEqual(len(deps), 5,
                                'dependency list parsed to %d entries; the parse is suspect'
                                % len(deps))
        unmapped = [d for d in deps
                    if d.strip().lower() not in MODULE_OVERRIDES
                    and not importlib.util.find_spec(d.strip().lower())]
        missing = missing_dependencies(deps)
        if missing or unmapped:
            self.fail(
                "ENVIRONMENT_INCOMPLETE (not a product defect): this interpreter is "
                "missing declared runtime dependencies.\n"
                "  interpreter: %s\n  python: %s\n  missing: %s\n  unmapped: %s\n"
                "  remedy: run the suite with the project venv "
                "(.venv\\Scripts\\python.exe on Windows), which matches the "
                "environmentFingerprint recorded in the projections. An external venv "
                "produces dozens of _FailedTest errors that look like broken code."
                % (sys.executable, sys.version.split()[0], missing, unmapped))

    def test_guard_actually_detects_an_absent_package(self):
        """Without this the check above could pass by never detecting anything."""
        fake = [("definitely-not-installed-xyz", "definitely_not_installed_xyz")]
        found = missing_dependencies(["definitely-not-installed-xyz"])
        self.assertEqual(found, fake,
                         "the detector reported no missing package for a name that "
                         "cannot exist -- the guard is not measuring anything")
        self.assertEqual(missing_dependencies(["jsonschema"]), [],
                         "the detector flagged an installed dependency as missing")

    def test_dependency_parse_matches_the_declaration(self):
        deps = set(d.strip().lower() for d in declared_dependencies(REPO / "pyproject.toml"))
        for expected in ("jsonschema", "pillow", "numpy", "scikit-image", "defusedxml"):
            self.assertIn(expected, deps,
                          "%s is declared in pyproject.toml but the parser missed it "
                          "(got %s)" % (expected, sorted(deps)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
