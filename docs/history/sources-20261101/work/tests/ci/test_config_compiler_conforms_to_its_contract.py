"""Every byte the config compiler writes must satisfy the contract it declares -- measured, not assumed.

This module exists because `services/policy/config_compiler.py` declared `work-lab/canonical-config-intent/v1`
while writing `schemaVersion`, and the registered schema requires `schema_version` with
`additionalProperties: false`. All three lifecycle stages therefore produced documents that violated the
contract by exactly two counts, and nothing noticed: the only file that opened the schema was a drill script
no gate runs, and the only code that named the version was the emitter itself. The assertions here re-run the
real CLI and validate the real bytes against the real registered schema, and one test proves the schema
still rejects the shape that shipped.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema

REPO = Path(__file__).resolve().parents[2]
COMPILER = REPO / "services" / "policy" / "config_compiler.py"
SCHEMA_PATH = (REPO / "packages" / "contracts" / "schemas" / "workflow"
               / "canonical-config-intent.schema.json")
VERSION = "work-lab/canonical-config-intent/v1"


def _runtime_root() -> Path:
    """The git-ignored in-boundary runtime root, auto-created.

    `dir=` is mandatory (a bare mkdtemp lands in the user's system temp, outside the declared project
    boundary), and the parent must be created because a fresh CI checkout has no `.project-local/` at
    all -- on this machine the directory exists, so the omission would only go red there.
    """
    p = REPO / ".project-local" / "runs"
    p.mkdir(parents=True, exist_ok=True)
    return p


class Harness(unittest.TestCase):
    def setUp(self) -> None:
        self.workdir = Path(tempfile.mkdtemp(prefix="config-compiler-conformance-",
                                            dir=str(_runtime_root())))
        self.addCleanup(shutil.rmtree, self.workdir, True)
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def cli(self, *args: str) -> tuple[int, str]:
        proc = subprocess.run([sys.executable, str(COMPILER), *args], cwd=REPO,
                              capture_output=True)
        return proc.returncode, (proc.stdout + proc.stderr).decode("utf-8", "replace")

    def create(self, name: str, *extra: str) -> tuple[int, str, Path]:
        out = self.workdir / f"{name}.json"
        code, text = self.cli("create", "--client", "hermes", "--type", "set-field",
                              "--target", "display.language", "--value", '"zh"',
                              "--reason", "conformance probe", "--output", str(out), *extra)
        return code, text, out

    def violations(self, document: object) -> list[str]:
        validator = jsonschema.Draft202012Validator(self.schema)
        return [f"{list(e.absolute_path) or ['<root>']}: {e.message}"
                for e in sorted(validator.iter_errors(document), key=lambda e: str(e.json_path))]


class LifecycleDocumentsConform(Harness):
    def test_create_plan_and_approve_all_satisfy_the_registered_schema(self) -> None:
        code, text, path = self.create("draft")
        self.assertEqual(0, code, text)
        draft = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual([], self.violations(draft), "create wrote a document off contract")

        code, text = self.cli("plan", "--intent", str(path))
        self.assertEqual(0, code, text)
        planned = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual([], self.violations(planned), "plan wrote a document off contract")

        code, text = self.cli("approve", "--intent", str(path))
        self.assertEqual(0, code, text)
        approved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual([], self.violations(approved), "approve wrote a document off contract")
        self.assertEqual("approved", approved["status"])

    def test_the_written_version_is_the_one_the_contract_pins(self) -> None:
        _, _, path = self.create("versioned")
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(self.schema["properties"]["schema_version"]["const"],
                         document["schema_version"])
        self.assertNotIn("schemaVersion", document,
                         "the camelCase key the contract forbids is back in the written bytes")


class TheEmitterDoesNotHoldItsOwnCopyOfTheContract(Harness):
    def test_the_version_literal_appears_once_and_the_emitter_reads_it(self) -> None:
        """Two copies of a constant drift; the schema is the only place the value may live."""
        emitter_text = COMPILER.read_text(encoding="utf-8")
        self.assertNotIn(VERSION, emitter_text,
                         "config_compiler restates the contract version instead of loading it")
        self.assertIn(SCHEMA_PATH.name, emitter_text,
                      "config_compiler no longer opens the schema it claims to conform to")

    def test_the_enums_are_taken_from_the_schema_not_retyped(self) -> None:
        emitter_text = COMPILER.read_text(encoding="utf-8")
        for token in ("set-field", "enable-plugin", "opendesign"):
            self.assertNotIn(token, emitter_text,
                             f"{token!r} is a second copy of a contract enum value")


class OffContractInputIsRefused(Harness):
    def test_an_unknown_client_or_type_writes_no_file(self) -> None:
        out = self.workdir / "never.json"
        code, text = self.cli("create", "--client", "not-a-client", "--type", "set-field",
                              "--target", "display.language", "--output", str(out))
        self.assertEqual(2, code, text)
        self.assertIn("REFUSED_BY_CONTRACT", text)
        self.assertFalse(out.exists(), "a refused intent still landed on disk")

        code, text = self.cli("create", "--client", "hermes", "--type", "make-coffee",
                              "--target", "display.language", "--output", str(out))
        self.assertEqual(2, code, text)
        self.assertIn("REFUSED_BY_CONTRACT", text)
        self.assertFalse(out.exists())

    def test_an_empty_target_is_refused(self) -> None:
        out = self.workdir / "empty.json"
        code, text = self.cli("create", "--client", "hermes", "--type", "set-field",
                              "--target", "", "--output", str(out))
        self.assertEqual(2, code, text)
        self.assertFalse(out.exists())


class SelfReportedCountsAreTrue(Harness):
    def test_the_plan_report_counts_diff_entries_not_dict_keys(self) -> None:
        _, _, path = self.create("counted")
        code, text = self.cli("plan", "--intent", str(path))
        self.assertEqual(0, code, text)
        written = json.loads(path.read_text(encoding="utf-8"))["plan"]["diff"]
        reported = int(text.split("(")[1].split("diff")[0].strip())
        self.assertEqual(len(written), reported,
                         f"plan reported {reported} diff entries but wrote {len(written)}")


class TheSchemaReallyIsStrict(Harness):
    """Without this, the conformance test above could pass because the contract accepts anything."""

    def test_the_shipped_shape_is_rejected_by_the_contract(self) -> None:
        shipped = {"schemaVersion": VERSION, "intentId": "intent-000000000000",
                   "client": "hermes", "intent": {"type": "set-field", "target": "display.language",
                                                  "value": "zh", "reason": ""},
                   "plan": {"diff": [], "approval_required": True, "idempotency_key": "k"},
                   "status": "draft"}
        found = self.violations(shipped)
        self.assertEqual(2, len(found), f"expected exactly the two shipped faults, got {found}")
        joined = " ".join(found)
        self.assertIn("schema_version", joined)
        self.assertIn("schemaVersion", joined)

    def test_a_diff_entry_off_the_operation_enum_is_rejected(self) -> None:
        document = json.loads(json.dumps({
            "schema_version": VERSION, "intentId": "intent-000000000000", "client": "hermes",
            "intent": {"type": "set-field", "target": "x"},
            "plan": {"diff": [{"path": "p", "operation": "nuke"}], "approval_required": True},
            "status": "draft"}))
        found = self.violations(document)
        self.assertEqual(1, len(found), f"operation enum is not enforced: {found}")


if __name__ == "__main__":
    unittest.main()
