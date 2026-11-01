"""Gate: the declared toolchains must be the toolchains the repository actually uses.

U02's path convergence was recorded as done for the entry documents while the project's package
managers, pins and runtime root had never been stated anywhere a machine could check them. This file
asserts each line of `.project/governance/toolchain-declarations.json` against the tree: a lockfile
that is declared must exist and be tracked; the Python pin must be readable from the workflow YAML;
a null pin must still be true (no setup-node step); the runtime root must be read from the boundary
file rather than restated from memory.

Deliberately NOT asserted: any Node or Rust version. Nothing in the repository pins them, so the
only honest value is `null` plus the recorded gap — writing a version here would be the fabricated
baseline this project has repeatedly refused.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
DECL = ROOT / ".project/governance/toolchain-declarations.json"
WORKFLOW = ROOT / ".github/workflows/work-lab-gate.yml"
BOUNDARY = ROOT / ".project/governance/project-data-boundary.json"
MANIFEST = ROOT / "packages/client-neutral-core/workflow-manifest.yaml"
# Most CI commands live in the required-group manifest, not in the YAML, so the command set spans two files.
GROUPS = ROOT / "scripts/ci/required_groups.json"
LOCKFILE_NAMES = {"package-lock.json", "Cargo.lock", "requirements.lock"}


class ToolchainDeclarationGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = json.loads(DECL.read_text(encoding="utf-8"))
        cls.workflow = WORKFLOW.read_text(encoding="utf-8").replace("\r\n", "\n")
        cls.groups = json.loads(GROUPS.read_text(encoding="utf-8"))
        cls.boundary = json.loads(BOUNDARY.read_text(encoding="utf-8"))

    def ci_commands(self) -> set:
        lines = {m.group(1).strip() for m in re.finditer(r"run:\s*(.+)", self.workflow)}
        for group in self.groups["groups"].values():
            lines.update(" ".join(cmd) for cmd in group["commands"])
        return lines

    def lockfiles_in_the_repository(self) -> set:
        """The tracked file list, not a walk of the working tree.

        The property is about the repository: an ignored cache under `.project-local/` can hold a
        hundred `package-lock.json` files that are nobody's declaration obligation. Walking it also
        crashed the whole governance batch — `ROOT.rglob` raised FileNotFoundError on an atlas
        extraction directory that a concurrent cleanup removed mid-walk (ERR-162), so a locally dead
        gate hid behind a CI checkout that has no ignored root at all.
        """
        import subprocess
        listing = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True)
        out = set()
        for raw in listing.stdout.split(b"\0"):
            if not raw:
                continue
            rel = raw.decode("utf-8", "replace")
            if rel.startswith(".project-local/") or "/node_modules/" in f"/{rel}":
                continue
            if PurePosixPath(rel).name in LOCKFILE_NAMES:
                out.add(rel)
        return out

    def test_the_file_declares_every_lockfile_that_exists_in_the_repository(self) -> None:
        declared = {m["lockfile"] for m in self.doc["managers"]}
        real = self.lockfiles_in_the_repository()
        self.assertEqual(real, declared,
                         "the declaration drifted from the tree: added or removed lockfiles")
        self.assertGreaterEqual(len(real), 5)

    def test_every_declared_lockfile_is_tracked(self) -> None:
        import subprocess
        listing = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace").stdout.split()
        tracked = set(listing)
        for manager in self.doc["managers"]:
            self.assertIn(manager["lockfile"], tracked, manager["id"])

    def test_the_python_pin_claimed_in_ci_is_the_pin_in_the_workflow(self) -> None:
        python = next(m for m in self.doc["managers"] if m["ecosystem"] == "python")
        self.assertIn("actions/setup-python@", self.workflow)
        # The `uses:` line is a pinned SHA followed by a version comment, so the rest of that line is
        # skipped as opaque text rather than parsed — the pin we check lives on the `python-version:`
        # input two lines down.
        block = re.search(r"uses:\s*actions/setup-python@[0-9a-f]+[^\n]*\n\s*with:\s*\n"
                          r"\s*python-version:\s*'?([^'\n]+)'?", self.workflow)
        self.assertIsNotNone(block, "the workflow no longer provisions python the way this file claims")
        self.assertEqual(str(python["ciPin"]["version"]), block.group(1).strip())

    def test_a_pin_claim_matches_whether_ci_provisions_that_ecosystem(self) -> None:
        # Read in both directions: a null pin is only true while no provisioning step exists, and a
        # step that does not exist cannot carry a version claim. The first falsification run caught
        # a one-directional gate happily accepting a fabricated Node version.
        for manager in self.doc["managers"]:
            needle = {"node": "setup-node", "cargo": "setup-rust", "rust": "setup-rust"}.get(
                manager["ecosystem"])
            if needle is None:
                continue
            if needle in self.workflow:
                self.assertIsNotNone(
                    manager["ciPin"]["version"],
                    f"{manager['id']}: CI now provisions {needle} but the pin still says runner-provided")
            else:
                self.assertIsNone(
                    manager["ciPin"]["version"],
                    f"{manager['id']}: no {needle} step exists, so no version may be claimed")
                self.assertNotIn("setup-", manager["ciPin"]["provisioned_by"], manager["id"])

    def test_the_runtime_root_is_pointed_at_rather_than_restated(self) -> None:
        self.assertIn("runtimeRoot", self.boundary)
        self.assertEqual(".project-local/runs", self.boundary["runtimeRoot"])
        self.assertEqual(".project/governance/project-data-boundary.json",
                         self.doc["authority"]["runtimeRoot"])
        # The declaration must not carry its own copy of the root value, or the two can drift.
        self.assertNotIn("runtimeRoot", self.doc["managers"][0])
        body = DECL.read_text(encoding="utf-8")
        self.assertEqual(1, body.count('"runtimeRoot"'),
                         "the root is named once as a pointer; a second copy is a fork of the truth")

    def test_every_declared_install_and_test_command_is_one_ci_actually_runs(self) -> None:
        commands = self.ci_commands()
        for manager in self.doc["managers"]:
            self.assertIn(manager["install"], commands, manager["id"])
            tests = manager.get("tests")
            if tests:
                # The field leads with the literal command, then explains where it runs.
                self.assertIn(tests.split(" (")[0], commands, manager["id"])

    def test_manifest_python_floor_is_recorded_as_a_floor_not_the_ci_pin(self) -> None:
        text = MANIFEST.read_text(encoding="utf-8")
        self.assertIn("python: '>=3.11'", text)
        python = next(m for m in self.doc["managers"] if m["ecosystem"] == "python")
        self.assertEqual(">=3.11", python["manifestValue"])
        self.assertNotEqual(python["manifestValue"], str(python["ciPin"]["version"]),
                            "the manifest floor and the CI pin are different kinds of claim")

    def test_the_recorded_gaps_stay_recorded_until_someone_closes_them(self) -> None:
        gaps = {d["id"]: d["status"] for d in self.doc["divergences"]}
        self.assertEqual("OPEN_RECORDED", gaps["node-version-unpinned"])
        self.assertEqual("ACCEPTED_WITH_REASON", gaps["manifest-package-name"])
        self.assertNotIn("setup-node", self.workflow)


if __name__ == "__main__":
    unittest.main(verbosity=2)
