# SPDX-License-Identifier: MIT
"""DL-P1-111: Penpot adapter declaration, .penpot boundary and import plan (E1 structural).

No live Penpot run happens here, and none is claimed: these tests assert that the
declaration *cannot* claim one.
"""
from __future__ import annotations

import io
import json
import re
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from design_lab.interop import InteropError  # noqa: E402
from design_lab.interop import penpot  # noqa: E402

ADAPTER_SCHEMA = ROOT / "design-lab/schemas/adapter-contract.schema.json"
PENPOT_SCHEMA = ROOT / "design-lab/schemas/interop-penpot-adapter.schema.json"

FORBIDDEN_IMPORTS = ("subprocess", "socket", "urllib", "requests", "http", "ctypes", "shutil",
                     "psutil", "opentimelineio", "c2pa")


class PenpotFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent = ROOT / ".project-local/task-runtime/interop-penpot-tests"
        parent.mkdir(parents=True, exist_ok=True)
        cls._temp = tempfile.TemporaryDirectory(dir=parent)
        cls.addClassCleanup(cls._temp.cleanup)
        cls.workdir = Path(cls._temp.name)


class PenpotAdapterTest(PenpotFixture):
    def test_module_declares_the_task_and_the_boundary(self):
        docstring = (penpot.__doc__ or "").lower()
        self.assertIn("DL-P1-111", penpot.__doc__ or "")
        self.assertIn("no live penpot import or export ran", docstring)
        self.assertEqual(penpot.TASK_ID, "DL-P1-111")
        self.assertEqual(penpot.SCHEMA_VERSION, "design-lab/interop-penpot-adapter/v1")
        self.assertEqual(penpot.TERMINATOR, "requires a live Penpot run: NOT_EXECUTED")

    def test_adapter_declaration_matches_the_repository_contract(self):
        import jsonschema
        schema = json.loads(ADAPTER_SCHEMA.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(penpot.ADAPTER)
        adapter = penpot.ADAPTER
        self.assertEqual(adapter["status"], "structural")
        self.assertEqual(adapter["mode"], "external-local-api")
        self.assertEqual(adapter["license"], "MPL-2.0")
        self.assertTrue(adapter["capabilities"])
        for capability in adapter["capabilities"]:
            self.assertFalse(capability["supported"], capability["name"])
        evidence = adapter["evidence"]
        self.assertEqual(evidence["level"], "E1")
        self.assertIn("DL-P1-111", evidence["task_ids"])
        self.assertIn(penpot.LIVE_RUN_MARKER, evidence["note"])
        self.assertIn("no live Penpot import or export ran", evidence["note"])

    def test_adapter_is_returned_as_a_copy(self):
        first = penpot.adapter()
        first["status"] = "runtime"
        self.assertEqual(penpot.ADAPTER["status"], "structural")
        self.assertEqual(penpot.adapter()["status"], "structural")

    def test_validate_adapter_reports_a_structural_adapter(self):
        report = penpot.validate_adapter(penpot.ADAPTER)
        self.assertEqual(report["status"], "structural")
        self.assertEqual(report["evidence_level"], "E1")
        self.assertEqual(report["supported_capabilities"], [])
        self.assertEqual(report["live_run"], "NOT_EXECUTED")
        self.assertEqual(report["task_ids"], ["DL-P1-111"])

    def test_a_structural_adapter_cannot_claim_a_live_capability(self):
        broken = penpot.adapter()
        broken["capabilities"] = [{"name": "penpot.import", "supported": True}]
        with self.assertRaises(InteropError) as caught:
            penpot.validate_adapter(broken)
        self.assertIn("needs a live host run", str(caught.exception))

        safe = penpot.adapter()
        safe["capabilities"] = [{"name": "schema.validate", "supported": True}]
        self.assertEqual(penpot.validate_adapter(safe)["supported_capabilities"], ["schema.validate"])

    def test_structural_status_cannot_claim_above_e1_or_hide_the_marker(self):
        promoted = penpot.adapter()
        promoted["evidence"]["level"] = "E2"
        with self.assertRaises(InteropError) as caught:
            penpot.validate_adapter(promoted)
        self.assertIn("must carry E1 evidence", str(caught.exception))

        unmarked = penpot.adapter()
        unmarked["evidence"]["note"] = "live run performed"
        with self.assertRaises(InteropError) as caught:
            penpot.validate_adapter(unmarked)
        self.assertIn(penpot.LIVE_RUN_MARKER, str(caught.exception))

    def test_contract_schema_violations_fail_closed(self):
        broken = penpot.adapter()
        broken["status"] = "available"
        with self.assertRaises(InteropError) as caught:
            penpot.validate_adapter(broken)
        self.assertIn("adapter-contract.schema.json", str(caught.exception))

    def test_declaration_package_validates_offline(self):
        document = penpot.declaration()
        self.assertEqual(document["schemaVersion"], penpot.SCHEMA_VERSION)
        self.assertIsNone(document["import_plan"])
        report = penpot.validate_declaration(document)
        self.assertEqual(report["status"], "structural")
        self.assertIsNone(report["import_plan_status"])
        self.assertFalse(report["read_performed"])

        schema = json.loads(PENPOT_SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(schema["$id"],
                         "https://dtalex66.local/schemas/interop-penpot-adapter.schema.json")
        self.assertEqual(schema["properties"]["adapter_contract"]["$ref"],
                         "https://design-lab.local/schemas/adapter-contract.schema.json")

    def test_declaration_rejects_a_capability_claim(self):
        document = penpot.declaration()
        document["adapter_contract"]["capabilities"] = [{"name": "penpot.export", "supported": True}]
        with self.assertRaises(InteropError):
            penpot.validate_declaration(document)


class PenpotFileBoundaryTest(PenpotFixture):
    def test_boundary_describes_the_zip_container_and_read_only_policy(self):
        boundary = penpot.file_boundary()
        self.assertEqual(boundary["task_id"], "DL-P1-111")
        self.assertEqual(boundary["extension"], ".penpot")
        self.assertEqual(boundary["container"]["format"], "zip")
        self.assertEqual(boundary["container"]["index_entry"], "manifest.json")
        self.assertTrue(boundary["container"]["index_is_json"])
        self.assertEqual(boundary["container"]["schema_owner"], "Penpot")
        self.assertEqual(boundary["access"]["read_policy"], "opaque-read-only-external-asset")
        self.assertEqual(boundary["access"]["write_policy"], "never")
        self.assertEqual(boundary["access"]["user_personal_libraries"], "NEVER_READ")
        self.assertEqual(boundary["state"]["importer"], "NOT_IMPLEMENTED")
        self.assertEqual(boundary["state"]["exporter"], "NOT_IMPLEMENTED")
        self.assertEqual(boundary["state"]["live_run"], "NOT_EXECUTED")
        self.assertEqual(boundary["state"]["evidence_level"], "E1")
        self.assertTrue(boundary["prohibited"])

    def test_boundary_is_deterministic(self):
        self.assertEqual(penpot.file_boundary(), penpot.file_boundary())

    def test_boundary_is_part_of_the_declaration_package(self):
        document = penpot.declaration()
        self.assertEqual(document["file_boundary"], penpot.file_boundary())
        self.assertEqual(penpot.validate_declaration(document)["status"], "structural")


class PenpotImportPlanTest(PenpotFixture):
    def test_plan_ends_with_the_terminator_and_reads_nothing(self):
        plan = penpot.import_plan(str(self.workdir / "missing-fixture.penpot"))
        self.assertEqual(plan["mode"], "read-only-plan")
        self.assertEqual(plan["status"], "PLAN_ONLY_NOT_EXECUTED")
        self.assertEqual(plan["terminates_with"], penpot.TERMINATOR)
        self.assertEqual(plan["steps"][-1]["action"], penpot.TERMINATOR)
        self.assertEqual(plan["steps"][-1]["gate"], "REQUIRES_LIVE_HOST")
        self.assertFalse(plan["target"]["read_performed"])
        self.assertEqual(plan["target"]["source_probed"], "NOT_EXECUTED")
        self.assertEqual([step["step"] for step in plan["steps"]],
                         list(range(1, len(plan["steps"]) + 1)))
        self.assertTrue(any(step["gate"] == "REQUIRES_LIVE_HOST" for step in plan["steps"]))
        self.assertTrue(any(step["gate"] == "HUMAN_GATE_RIGHTS" for step in plan["steps"]))

    def test_plan_does_not_touch_the_filesystem(self):
        target = self.workdir / "absent.penpot"
        plan = penpot.import_plan(str(target))
        self.assertFalse(target.exists(), "the plan must not create or read the target")
        self.assertEqual(plan["target"]["path"], str(target).replace("\\", "/"))

    def test_plan_locations_are_labelled(self):
        inside = penpot.import_plan(str(ROOT / "fixtures/design.penpot"))
        self.assertEqual(inside["target"]["location"], "inside-repository")
        outside = penpot.import_plan("C:/external/design.penpot")
        self.assertEqual(outside["target"]["location"], "outside-repository")

    def test_protected_and_foreign_targets_fail_closed(self):
        cases = {
            "protected drive": r"E:\protected\design.penpot",
            "network path": r"\\server\share\design.penpot",
            "wrong extension": "design.penpot.json",
            "no extension": "design",
            "shell expansion": "%TEMP%/design.penpot",
            "empty": "",
            "padded": " design.penpot ",
        }
        for label, path in cases.items():
            with self.subTest(label):
                with self.assertRaises(InteropError):
                    penpot.import_plan(path)

    def test_plan_is_part_of_the_declaration_package(self):
        document = penpot.declaration(import_target="fixtures/design.penpot")
        report = penpot.validate_declaration(document)
        self.assertEqual(report["import_plan_status"], "PLAN_ONLY_NOT_EXECUTED")
        self.assertFalse(report["read_performed"])

    def test_plan_target_must_match_the_container_extension(self):
        plan = penpot.import_plan("fixtures/Design.PENPOT")
        self.assertEqual(plan["target"]["extension"], ".penpot")


class PenpotArchiveTest(PenpotFixture):
    """Structural validation of a synthetic .penpot archive (E1; no Penpot is run).

    The archives below are built here with the standard library. They are *not* a
    Penpot export: no Penpot installation, no network and no host call is involved,
    and the validator never claims more than the container's internal consistency.
    """

    def build(self, manifest, files, *, extra=None, duplicate=None, manifest_text=None):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json",
                             manifest_text if manifest_text is not None
                             else json.dumps(manifest))
            for name, payload in files.items():
                self.writestr(archive, name, payload)
            if extra is not None:
                for name, payload in extra:
                    self.writestr(archive, name, payload)
            if duplicate is not None:
                name, payload = duplicate
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)  # duplicate-name warning
                    self.writestr(archive, name, payload)
        return buffer.getvalue()

    @staticmethod
    def writestr(archive, name, payload):
        """Write an entry under *name*."""
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        info = zipfile.ZipInfo(name)
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, payload)

    def valid_manifest(self):
        return {
            "version": 3,
            "files": [
                "objects/page-1.json",
                {"name": "assets/logo.png", "size": 3},
            ],
        }

    def valid_archive(self) -> bytes:
        return self.build(self.valid_manifest(),
                          {"objects/page-1.json": "{\"page\": 1}",
                           "assets/logo.png": "PNG",
                           "preview.png": "PNG",
                           "meta.json": "{}"})

    def test_a_valid_archive_is_validated_structurally(self):
        report = penpot.validate_penpot_archive(self.valid_archive())
        self.assertEqual(report["manifest_entry"], "manifest.json")
        self.assertEqual(report["manifest_declared_key"], "files")
        self.assertEqual(report["manifest_version"], 3)
        self.assertEqual(report["declared_files"], ["assets/logo.png", "objects/page-1.json"])
        self.assertEqual(report["declared_file_count"], 2)
        self.assertEqual(report["undeclared_allowlisted"], ["meta.json", "preview.png"])
        self.assertEqual(report["file_count"], 5)
        self.assertGreater(report["total_file_bytes"], 0)
        self.assertFalse(report["extraction_performed"])
        self.assertFalse(report["write_performed"])
        self.assertEqual(report["live_run"], "NOT_EXECUTED")
        self.assertEqual(report["evidence_level"], "E1")

    def test_the_validator_never_claims_a_penpot_run(self):
        report = penpot.validate_penpot_archive(self.valid_archive())
        docstring = (penpot.validate_penpot_archive.__doc__ or "").lower()
        self.assertIn("not** a penpot import", docstring)
        self.assertIn("live_run", docstring)
        self.assertEqual(report["live_run"], "NOT_EXECUTED")

    def test_missing_manifest_fails_closed(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("objects/page-1.json", "{}")
        with self.assertRaises(InteropError) as caught:
            penpot.validate_penpot_archive(buffer.getvalue())
        self.assertIn("manifest.json", str(caught.exception))

    def test_a_declared_file_that_is_absent_fails_closed(self):
        manifest = {"version": 3, "files": ["objects/page-1.json", "objects/missing.json"]}
        data = self.build(manifest, {"objects/page-1.json": "{}"})
        with self.assertRaises(InteropError) as caught:
            penpot.validate_penpot_archive(data)
        message = str(caught.exception)
        self.assertIn("objects/missing.json", message)
        self.assertIn("no such entry", message)

    def test_path_traversal_entries_fail_closed(self):
        cases = {
            "../escape.json": "escapes the archive root",
            "objects/../../escape.json": "escapes the archive root",
            "/absolute.json": "absolute path",
            "C:/drive/logo.png": "names a drive",
            "./manifest.json": "path segment",
        }
        for name, rule in cases.items():
            with self.subTest(name):
                data = self.build({"version": 3, "files": ["objects/page-1.json"]},
                                  {"objects/page-1.json": "{}"},
                                  extra=[(name, "{}")])
                with self.assertRaises(InteropError) as caught:
                    penpot.validate_penpot_archive(data)
                message = str(caught.exception)
                self.assertIn(rule, message)
                self.assertIn(name.rsplit("/", 1)[-1], message)

    def test_a_declared_traversal_or_absolute_name_fails_closed(self):
        # A declared name comes straight from manifest.json, so it is checked before
        # it is ever matched against the archive -- including a backslash name, which
        # zipfile itself normalises on Windows and therefore cannot be reached
        # through the central directory on this platform.
        cases = {
            "../escape.json": "escapes the archive root",
            "/absolute.json": "absolute path",
            "C:/drive/logo.png": "names a drive",
            "assets" + chr(92) + "logo.png": "backslash",
            "./a.json": "path segment",
            "": "nonempty entry name",
        }
        for name, rule in cases.items():
            with self.subTest(name):
                data = self.build({"version": 3, "files": [name]},
                                  {"objects/page-1.json": "{}"})
                with self.assertRaises(InteropError) as caught:
                    penpot.validate_penpot_archive(data)
                self.assertIn(rule, str(caught.exception))

    def test_duplicate_entries_fail_closed(self):
        data = self.build({"version": 3, "files": ["objects/page-1.json"]},
                          {"objects/page-1.json": "{}"},
                          duplicate=("objects/page-1.json", "{}"))
        with self.assertRaises(InteropError) as caught:
            penpot.validate_penpot_archive(data)
        message = str(caught.exception)
        self.assertIn("objects/page-1.json", message)
        self.assertIn("more than once", message)

    def test_a_declared_size_that_disagrees_with_the_zip_fails_closed(self):
        manifest = {"version": 3, "files": [{"name": "objects/page-1.json", "size": 999}]}
        data = self.build(manifest, {"objects/page-1.json": "{}"})
        with self.assertRaises(InteropError) as caught:
            penpot.validate_penpot_archive(data)
        message = str(caught.exception)
        self.assertIn("objects/page-1.json", message)
        self.assertIn("999", message)
        self.assertIn("2 byte(s)", message)

    def test_a_declared_file_may_be_declared_twice_only_once(self):
        manifest = {"version": 3, "files": ["objects/page-1.json", "objects/page-1.json"]}
        data = self.build(manifest, {"objects/page-1.json": "{}"})
        with self.assertRaises(InteropError) as caught:
            penpot.validate_penpot_archive(data)
        self.assertIn("a second time", str(caught.exception))

    def test_an_undeclared_payload_entry_fails_closed(self):
        data = self.build({"version": 3, "files": ["objects/page-1.json"]},
                          {"objects/page-1.json": "{}"},
                          extra=[("assets/secret.bin", b"\x00\x01")])
        with self.assertRaises(InteropError) as caught:
            penpot.validate_penpot_archive(data)
        message = str(caught.exception)
        self.assertIn("assets/secret.bin", message)
        self.assertIn("allow-list", message)

    def test_undeclared_json_metadata_and_thumbnails_are_allowlisted(self):
        data = self.build({"version": 3, "files": ["objects/page-1.json"]},
                          {"objects/page-1.json": "{}"},
                          extra=[("meta/page-meta.json", "{}"),
                                 ("thumbnails/thumb.webp", "RIFF"),
                                 ("page-2.json", "{}")])
        report = penpot.validate_penpot_archive(data)
        self.assertEqual(report["undeclared_allowlisted"],
                         ["meta/page-meta.json", "page-2.json", "thumbnails/thumb.webp"])

    def test_manifest_shape_and_size_fail_closed(self):
        cases = {
            "not json": {"version": 3, "files": ["a.json"]},
            "not an object": [1, 2, 3],
            "no file list": {"version": 3},
            "empty file list": {"version": 3, "files": []},
            "record without a name": {"version": 3, "files": [{"size": 12}]},
            "negative size": {"version": 3, "files": [{"name": "a.json", "size": -1}]},
        }
        for label, manifest in cases.items():
            with self.subTest(label):
                if label == "not json":
                    data = self.build(None, {"a.json": "{}"}, manifest_text="{not json")
                else:
                    data = self.build(manifest, {"a.json": "{}"})
                with self.assertRaises(InteropError):
                    penpot.validate_penpot_archive(data)

    def test_non_zip_and_empty_input_fail_closed(self):
        for label, data in (("not a zip", b"not a zip at all"), ("empty", b""),
                            ("truncated", b"PK\x03\x04")):
            with self.subTest(label):
                with self.assertRaises(InteropError):
                    penpot.validate_penpot_archive(data)
        for label, value in (("none", None), ("string", "not bytes"), ("dict", {})):
            with self.subTest(label):
                with self.assertRaises(InteropError):
                    penpot.validate_penpot_archive(value)

    def test_a_directory_entry_is_not_a_payload_file(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("manifest.json", json.dumps({"version": 3, "files": ["a.json"]}))
            self.writestr(archive, "a.json", "{}")
            archive.writestr("objects/", "")
        report = penpot.validate_penpot_archive(buffer.getvalue())
        self.assertEqual(report["directory_count"], 1)
        self.assertEqual(report["file_count"], 2)

    def test_boundary_documents_the_validator(self):
        boundary = penpot.file_boundary()
        validation = boundary["validation"]
        self.assertEqual(validation["entry_point"], "validate_penpot_archive")
        self.assertEqual(validation["extraction"], "NEVER")
        self.assertEqual(validation["live_run"], "NOT_EXECUTED")
        self.assertEqual(validation["evidence_level"], "E1")
        self.assertEqual(validation["declared_file_list_keys"], ["files", "entries"])
        self.assertTrue(validation["rejects"])
        self.assertEqual(penpot.validate_declaration(penpot.declaration())["status"], "structural")


class InteropBoundaryTest(PenpotFixture):
    """Structural evidence that no interop module can reach a host, a socket or a process."""

    def test_no_interop_module_imports_a_process_or_network_library(self):
        package = SRC / "design_lab/interop"
        modules = sorted(package.glob("*.py"))
        self.assertEqual(len(modules), 6)
        pattern = re.compile(r"^\s*(?:import|from)\s+(" + "|".join(FORBIDDEN_IMPORTS) + r")\b", re.M)
        for module in modules:
            with self.subTest(module.name):
                source = module.read_text(encoding="utf-8")
                match = pattern.search(source)
                self.assertIsNone(match, f"{module.name} imports {match.group(1) if match else ''}")

    def test_no_interop_module_reads_the_protected_drive(self):
        package = SRC / "design_lab/interop"
        for module in sorted(package.glob("*.py")):
            with self.subTest(module.name):
                source = module.read_text(encoding="utf-8")
                # The only E: mention allowed is the lexical guard that rejects it.
                for line in source.splitlines():
                    if re.search(r"\bE:", line):
                        self.assertIn("drive", line.lower(), f"{module.name}: {line.strip()}")

    def test_package_exposes_one_error_type(self):
        import design_lab.interop as interop
        self.assertTrue(issubclass(interop.InteropError, RuntimeError))
        self.assertIn("InteropError", interop.__all__)


if __name__ == "__main__":
    unittest.main(verbosity=2)
