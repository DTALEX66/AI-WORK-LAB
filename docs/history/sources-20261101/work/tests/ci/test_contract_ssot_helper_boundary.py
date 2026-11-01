"""The contract-SSOT helper boundary must be able to go red in both directions.

`verify_contract_ssot.py` used to print unlisted schema files as `[advisory]` and still exit 0, so the
only way to trust the new rule is to plant both faults it exists to catch. Nothing here writes to the
tree: the verdict is computed from synthetic path sets, and one assertion runs the real command over the
real tree so the declared set cannot drift from reality by accident.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "ci"))

import verify_contract_ssot as ssot  # noqa: E402


class HelperDeclarationsMatchTheTree(unittest.TestCase):
    def run_ssot(self) -> tuple[int, str]:
        proc = subprocess.run([sys.executable, str(REPO / "scripts" / "ci" /
                                                      "verify_contract_ssot.py")],
                              cwd=REPO, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        return proc.returncode, proc.stdout + proc.stderr

    def test_the_real_tree_passes_the_new_rule(self) -> None:
        code, out = self.run_ssot()
        self.assertEqual(0, code, out)
        self.assertIn("unlisted_declared=", out, f"no bounded count in the receipt: {out}")

    def test_every_declaration_carries_a_measured_reason(self) -> None:
        for path, reason in ssot.DECLARED_HELPER_SCHEMAS.items():
            self.assertTrue((REPO / path).is_file(), f"declared helper is not on disk: {path}")
            self.assertGreaterEqual(len(reason), 40, f"{path}: reason too thin to review")

    # What each declared reason claims, stated as the different kinds of consumer that exist.
    LOADERS = {"packages/contracts/schemas/workflow/canonical-config-intent.schema.json":
               ["packages/client-neutral-core/scripts/backup_restore_drill.py",
                "services/policy/config_compiler.py",
                "tests/ci/test_config_compiler_conforms_to_its_contract.py"]}
    # `emits only, never opens` was the old shape and it shipped a non-conforming document; now the
    # emitter is required to hold no second copy of the version it claims
    DERIVES_VERSION_FROM_CONTRACT = {
        "packages/contracts/schemas/workflow/canonical-config-intent.schema.json":
            ("services/policy/config_compiler.py", "work-lab/canonical-config-intent/v1")}
    CENSUS_ONLY = ["packages/contracts/schemas/workflow/cloud-event-envelope.schema.json"]

    def test_declared_reasons_name_a_consumer_that_exists(self) -> None:
        """Each reason names its consumer and the kind of relation -- re-measured, not trusted.

        This test exists because my first version of the reasons said "no consumer" for
        canonical-config-intent (services/policy/config_compiler.py disagreed), and my second version
        said config_compiler "loads" it (it declared the version string but never opened the file).
        Both errors were caught by measuring, which is the point of asserting the relation kind. The
        second version is the one that let a non-conforming document ship, so the relation is now
        pinned in the stricter direction: the emitter must open the file and hold no copy of the value.
        """
        for path, loaders in self.LOADERS.items():
            name = Path(path).name
            by_path = subprocess.run(["git", "grep", "-l", "-F", name], cwd=REPO,
                                     capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.split()
            for loader in loaders:
                self.assertIn(loader, by_path, f"{name}: {loader} does not reference the file")
        for path, (emitter, version) in self.DERIVES_VERSION_FROM_CONTRACT.items():
            text = (REPO / emitter).read_text(encoding="utf-8")
            self.assertNotIn(version, text,
                             f"{emitter} restates {version} instead of loading it from the contract")
            self.assertIn(Path(path).name, text,
                          f"{emitter} is claimed to open the contract, but never names the file")
            schema = json.loads((REPO / path).read_text(encoding="utf-8"))
            self.assertEqual(version, schema["properties"]["schema_version"]["const"],
                             f"{path} no longer pins {version}")
        for path in self.CENSUS_ONLY:
            name = Path(path).name
            referrers = subprocess.run(["git", "grep", "-l", "-F", name], cwd=REPO,
                                       capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.split()
            # exclusions are measured, not convenient: this file itself names the schema (it is the
            # list under test), and so does the verifier -- both are harness references. The first
            # version of this assertion passed only because `git grep` cannot see an untracked file;
            # the moment the test was committed it became its own referrer and the suite went red.
            here = str(Path(__file__).resolve().relative_to(REPO)).replace("\\", "/")
            real = [r for r in referrers if r != path and r != here
                    and not r.startswith(("scripts/ci/verify_contract_ssot.py", "reports/",
                                          "docs/history/", "taskpacks/"))]
            # measured, not assumed: the census test pins the filename, and verify_core_schemas.py
            # -- which holds per-file expectations for eight of these -- does not name this one at all
            self.assertEqual(["tests/workflow-assistance/test_core_schemas.py"], sorted(real),
                             f"{name} claimed census-only, tree says {real}")


class VerdictFalsification(unittest.TestCase):
    def test_a_new_unlisted_schema_is_undeclared(self) -> None:
        planted = set(ssot.DECLARED_HELPER_SCHEMAS) | {
            "packages/contracts/schemas/workflow/somewhere-new.schema.json"}
        undeclared, stale = ssot.unlisted_verdict(planted)
        self.assertEqual(["packages/contracts/schemas/workflow/somewhere-new.schema.json"],
                         undeclared, "a new unlisted schema slipped through")
        self.assertEqual([], stale)

    def test_a_declaration_that_no_longer_matches_is_stale(self) -> None:
        shrunk = set(ssot.DECLARED_HELPER_SCHEMAS) - {
            "packages/contracts/schemas/workflow/error.schema.json"}
        undeclared, stale = ssot.unlisted_verdict(shrunk)
        self.assertEqual([], undeclared)
        self.assertEqual(["packages/contracts/schemas/workflow/error.schema.json"], stale,
                         "a stale helper declaration is not reported")

    def test_the_declared_set_is_not_empty_by_construction(self) -> None:
        """An allowlist that could be emptied would let the gate pass by deleting the list."""
        self.assertGreaterEqual(len(ssot.DECLARED_HELPER_SCHEMAS), 10)
        undeclared, stale = ssot.unlisted_verdict(set())
        self.assertEqual([], undeclared)
        self.assertEqual(len(stale), len(ssot.DECLARED_HELPER_SCHEMAS))


if __name__ == "__main__":
    unittest.main()
