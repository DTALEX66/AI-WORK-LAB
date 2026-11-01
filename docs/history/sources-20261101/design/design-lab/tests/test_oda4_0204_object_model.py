# SPDX-License-Identifier: MIT
"""ODA4-0203/0204 / V42-0203/0204: user modes and four-object model contracts.

V42-0203: Guided/Copilot/Director/Method/Production modes over a single engine.
V42-0204: Project/Knowledge/Evidence/Artifact object model with lifecycle,
versioning, rights and references — schema-validated (E2).
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ASSISTANCE = REPO / "design-lab"

USER_MODES = ASSISTANCE / "profiles" / "user-modes.json"
USER_MODES_SCHEMA = ASSISTANCE / "schemas" / "user-modes.schema.json"
OBJECT_MODEL = ASSISTANCE / "config" / "object-model.json"
OBJECT_MODEL_SCHEMA = ASSISTANCE / "schemas" / "object-model.schema.json"

EXPECTED_MODES = {"guided", "copilot", "director", "method", "production"}
EXPECTED_OBJECTS = {"project", "knowledge", "evidence", "artifact"}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(schema: Path, instance: Path) -> list[str]:
    import jsonschema

    sch = _load(schema)
    inst = _load(instance)
    errors: list[str] = []
    for err in sorted(jsonschema.Draft202012Validator(sch).iter_errors(inst), key=lambda e: list(e.path)):
        errors.append(f"{'/'.join(str(p) for p in err.path)}: {err.message}")
    return errors


class UserModesTest(unittest.TestCase):
    def test_five_modes_complete(self):
        data = _load(USER_MODES)
        ids = {m["id"] for m in data["modes"]}
        self.assertEqual(ids, EXPECTED_MODES)

    def test_modes_against_doc(self):
        doc = (REPO / "docs" / "current" / "USER_MODES.md").read_text(encoding="utf-8")
        for mid in EXPECTED_MODES:
            self.assertIn(mid, doc, f"USER_MODES.md must mention mode {mid}")

    def test_no_second_product_shell(self):
        doc = (REPO / "docs" / "current" / "USER_MODES.md").read_text(encoding="utf-8")
        self.assertIn("不做五套产品", doc)

    def test_schema_validates(self):
        errs = _validate(USER_MODES_SCHEMA, USER_MODES)
        self.assertEqual(errs, [])


class ObjectModelTest(unittest.TestCase):
    def test_thirteen_objects_complete(self):
        data = _load(OBJECT_MODEL)
        ids = {o["id"] for o in data["objects"]}
        # V2 kernel: 13 core objects retained + DesignProject/Command/ExecutionResult/QualityReport/DeliveryManifest/MemoryRecord
        self.assertGreaterEqual(len(ids), 13, f"expected >=13 core objects, got {len(ids)}")
        required = {"brief", "reference-set", "research-finding", "method-card", "direction", "design-system",
                    "domain-pack", "artifact", "tool-run", "quality-assessment", "preflight-report",
                    "handoff-package", "evidence-record", "project", "command", "execution-result",
                    "quality-report", "delivery-manifest", "memory-record"}
        self.assertTrue(required <= set(ids), f"missing objects: {sorted(required - set(ids))}")
        expected = {
            "brief", "reference-set", "research-finding", "method-card",
            "direction", "design-system", "domain-pack", "artifact",
            "tool-run", "quality-assessment", "preflight-report",
            "handoff-package", "evidence-record",
            "project", "command", "execution-result",
            "quality-report", "delivery-manifest", "memory-record",
            "extraction-job", "candidate-knowledge",
        }
        self.assertEqual(ids, expected)

    def test_every_object_has_schema_ref(self):
        for obj in _load(OBJECT_MODEL)["objects"]:
            self.assertIn("schemaRef", obj, obj["id"])
            self.assertTrue(obj["schemaRef"].startswith("schemas/"), f"{obj['id']} schemaRef must live under schemas/")

    def test_evidence_record_is_immutable(self):
        data = _load(OBJECT_MODEL)
        ev = next(o for o in data["objects"] if o["id"] == "evidence-record")
        self.assertTrue(ev["adapterMappable"])

    def test_schema_validates(self):
        errs = _validate(OBJECT_MODEL_SCHEMA, OBJECT_MODEL)
        self.assertEqual(errs, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
