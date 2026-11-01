# SPDX-License-Identifier: MIT
"""Registered tool bindings: stop reporting installed software as not installed.

DL-R5-004's sibling task DL-R5-007 clause A1 says the Doctor must not call already
registered software "not installed". It did, for anything installed under a declared
shared-input root but absent from PATH -- which on this machine is node and ffmpeg,
both of which exist and run. The fix is a binding in .project/paths.json, and the
guard around it is that a binding must live inside a declared root: the point is to
trust the owner's registration, not to widen what the project will execute.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from design_lab.runtime import doctor  # noqa: E402
from design_lab.runtime.paths import PathPolicyError, resolve_paths  # noqa: E402


class BindingFixture(unittest.TestCase):
    """A temp project whose paths.json declares a tool root and bindings."""

    def setUp(self):
        runtime = ROOT / ".project-local/task-runtime/doctor-binding-tests"
        runtime.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=runtime)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "AGENTS.md").write_text("# synthetic doctor binding project", encoding="utf-8")
        self.toolroot = self.root / "toolchain"
        self.toolroot.mkdir()
        self.real = self.toolroot / "tool.exe"
        self.real.write_bytes(b"MZ fake executable")
        self.outside = self.root / "elsewhere"
        self.outside.mkdir()
        self.stray = self.outside / "stray.exe"
        self.stray.write_bytes(b"MZ")
        self.missing = self.toolroot / "gone.exe"
        self.directory = self.toolroot / "adir"
        self.directory.mkdir()

    def write_config(self, tools, schema="design-lab/project-paths/v2"):
        document = {"schemaVersion": schema, "project_local_root": ".project-local",
                    "shared_inputs": {"toolchain": self.toolroot.as_posix()},
                    **({"tools": tools} if tools else {})}
        config = self.root / ".project/paths.json"
        config.parent.mkdir(exist_ok=True)
        config.write_text(json.dumps(document), encoding="utf-8")

    def bindings(self):
        # environ={} because the authoritative suite runner exports
        # PROJECT_LOCAL_ROOT pointing at this repository's own .project-local,
        # which is not under the temp project and would be rejected as a policy
        # violation. The lock/paths tests in this repo use the same convention.
        return resolve_paths(project_root=self.root, environ={}).tool_bindings()

    def test_a_bound_executable_is_reported_as_bound_with_its_owner(self):
        self.write_config({"tool": self.real.as_posix()})
        entry = self.bindings()["tool"]
        self.assertEqual(entry["status"], "BOUND")
        self.assertEqual(entry["owner"], "toolchain")

    def test_a_binding_outside_every_declared_root_is_not_trusted(self):
        """Otherwise paths.json becomes an arbitrary-executable allowlist."""
        self.write_config({"tool": self.stray.as_posix()})
        entry = self.bindings()["tool"]
        self.assertEqual(entry["status"], "DECLARED_OUTSIDE_SHARED_ROOT")
        self.assertIsNone(entry["owner"])

    def test_a_registered_but_absent_path_says_so_instead_of_claiming_ready(self):
        self.write_config({"tool": self.missing.as_posix()})
        self.assertEqual(self.bindings()["tool"]["status"], "DECLARED_PATH_MISSING")

    def test_a_registered_directory_is_not_an_executable(self):
        self.write_config({"tool": self.directory.as_posix()})
        self.assertEqual(self.bindings()["tool"]["status"], "DECLARED_PATH_NOT_A_FILE")

    def test_tool_bindings_require_schema_v2(self):
        """The version must keep meaning, or it stops being a migration signal."""
        self.write_config({"tool": self.real.as_posix()},
                          schema="design-lab/project-paths/v1")
        with self.assertRaises(PathPolicyError):
            self.bindings()

    def test_v1_config_without_tools_still_resolves(self):
        self.write_config({}, schema="design-lab/project-paths/v1")
        self.assertEqual(self.bindings(), {})


class ProbeUsesTheBinding(unittest.TestCase):
    def _status(self, bindings, which_return=None):
        with patch.object(doctor, "EXPECTED", {"ffmpeg": ">=6.0"}), \
             patch.object(doctor.shutil, "which", return_value=which_return), \
             patch.object(doctor.subprocess, "run",
                          return_value=subprocess.CompletedProcess(
                              [], 0, "ffmpeg version 7.0 Copyright", "")) as run:
            return doctor.probe_tools(bindings=bindings)[0], run

    def test_a_bound_path_is_probed_instead_of_the_path_entry(self):
        status, run = self._status({"ffmpeg": {"status": "BOUND", "path": "D:/bound/ffmpeg.exe",
                                               "owner": "os-toolchain"}},
                                   which_return="D:/onpath/ffmpeg.exe")
        self.assertTrue(status.found)
        self.assertEqual(status.path, "D:/bound/ffmpeg.exe")
        self.assertIn("declared:.project/paths.json#tools.ffmpeg", status.path_source)
        self.assertEqual(run.call_args.args[0], ["D:/bound/ffmpeg.exe", "-version"])
        self.assertEqual(status.version_status, "VERSION_VERIFIED")

    def test_an_unusable_binding_falls_back_to_path_and_says_it_fell_back(self):
        status, _ = self._status({"ffmpeg": {"status": "DECLARED_PATH_MISSING",
                                             "path": "D:/gone/ffmpeg.exe", "owner": "os-toolchain"}},
                                 which_return="D:/onpath/ffmpeg.exe")
        self.assertTrue(status.found, "a working PATH install must not be lost")
        self.assertEqual(status.path, "D:/onpath/ffmpeg.exe")
        self.assertEqual(status.path_source, "shutil.which")
        self.assertTrue(any(d.startswith("DECLARED_BINDING_UNUSABLE") for d in status.drift),
                        status.drift)

    def test_nothing_is_reported_installed_without_a_real_probe(self):
        """A binding is a pointer, not evidence: the version command must still run."""
        status, run = self._status({}, which_return=None)
        self.assertFalse(status.found)
        self.assertEqual(run.call_count, 0)
        self.assertTrue(any("NOT_FOUND_IN_SEARCH_SCOPE" in d for d in status.drift), status.drift)

    def test_binding_scope_is_stated_in_the_report(self):
        status, _ = self._status({"ffmpeg": {"status": "BOUND", "path": "D:/bound/ffmpeg.exe",
                                             "owner": "os-toolchain"}})
        self.assertIn("declared binding", status.search_scope)


class RepoConfigIsInternallyConsistent(unittest.TestCase):
    """Portable: assert the shape of this machine's answer, never its specifics.

    CI runs on a different machine, so "node is BOUND" would be a false assertion
    there. What must hold everywhere is that a binding either resolves inside a
    declared root or is reported as a problem -- never silently dropped.
    """

    def test_every_declared_tool_is_classified_and_none_is_silently_ignored(self):
        bindings = resolve_paths(project_root=doctor.PROJECT_ROOT).tool_bindings()
        recognised = {"BOUND", "DECLARED_PATH_MISSING", "DECLARED_PATH_NOT_A_FILE",
                      "DECLARED_OUTSIDE_SHARED_ROOT", "DECLARED_VALUE_INVALID"}
        for name, entry in bindings.items():
            self.assertIn(entry["status"], recognised, f"{name}: {entry}")
            if entry["status"] == "BOUND":
                self.assertIsNotNone(entry["owner"], f"{name} is BOUND with no owning root")
                self.assertTrue(Path(entry["path"]).is_file(), f"{name} claims BOUND but is not a file")

    def test_the_expected_tools_are_all_declared_or_found_on_path(self):
        """The A1 regression, stated so it can hold on any machine."""
        bindings = resolve_paths(project_root=doctor.PROJECT_ROOT).tool_bindings()
        statuses = doctor.probe_tools()
        for status in statuses:
            if not status.found:
                self.assertNotEqual(
                    bindings.get(status.tool, {}).get("status"), "BOUND",
                    f"{status.tool} is registered and BOUND yet reported not installed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
