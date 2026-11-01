# SPDX-License-Identifier: MIT
"""DL-TP-T06 (MULTIMODAL-2026-09-05): planar decomposition mapping tests.

Verifies structural honesty: no module may set host ids, unmapped objects
cannot carry host_object_id, locking prevents silent re-map, font substitution
is explicit, and the emitted JSON validates against the planar-decomposition
schema contract. No real OCR/tracing or host execution is claimed.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC))
REPO = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO / "design-lab" / "schemas" / "contracts" / "planar-decomposition.schema.json"


class PlanarDecompositionTests(unittest.TestCase):
    def _plan(self):
        from design_lab.analysis.decomposition import CanvasRegion, Plan, PlanObject

        plan = Plan(
            decomposition_id="dec-1",
            source_ref="reference/poster.png",
            source_sha256="sha256:" + "a" * 64,
            canvas=CanvasRegion(0, 0, 1000, 1400),
            objects=[
                PlanObject("o1", "text", CanvasRegion(50, 50, 300, 80),
                           module="ocr", text_content="标题", font_status="matched"),
                PlanObject("o2", "image", CanvasRegion(50, 200, 500, 600), module="heuristic"),
            ],
        )
        plan.validate()
        return plan

    def test_module_detection_never_sets_host_id(self):
        """Replaceable modules return candidates; host ids only via verifier."""
        from design_lab.analysis.decomposition import DecomposeModule

        class FakeOcr(DecomposeModule):
            module_id = "ocr-fixture"

            def detect(self, source_path):
                return [{"kind": "text", "region": {"x": 0, "y": 0, "width": 1, "height": 1}}]

        raw = FakeOcr().detect("x.png")
        self.assertNotIn("host_object_id", raw[0])

    def test_unmapped_cannot_carry_host_object_id(self):
        from design_lab.analysis.decomposition import DecompositionError

        plan = self._plan()
        plan.objects[0].host_object_id = "AI:1"
        with self.assertRaisesRegex(DecompositionError, "unmapped"):
            plan.validate()

    def test_lock_requires_host_and_prevents_silent_remap(self):
        from design_lab.analysis.decomposition import DecompositionError

        plan = self._plan()
        with self.assertRaisesRegex(DecompositionError, "cannot lock without"):
            plan.objects[0].lock()
        plan.objects[0].mark_host_mapping("AI:layer:1", by_user=True)
        plan.objects[0].lock()
        with self.assertRaisesRegex(DecompositionError, "locked"):
            plan.objects[0].mark_host_mapping("AI:layer:2")

    def test_font_substitution_is_explicit(self):
        from design_lab.analysis.decomposition import DecompositionError

        plan = self._plan()
        plan.objects[0].font_status = "substituted"
        plan.validate()  # allowed but explicit
        plan.objects[0].font_status = "magic"
        with self.assertRaises(DecompositionError):
            plan.validate()

    def test_contract_json_validates_against_schema(self):
        import jsonschema

        plan = self._plan()
        payload = json.loads(plan.to_json())
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.validate(instance=payload, schema=schema)

    # --- schema invalid-input negative fixtures (T18) ---------------------

    def _schema(self):
        import jsonschema
        return jsonschema.Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))

    def _payload(self, **overrides):
        plan = self._plan()
        payload = json.loads(plan.to_json())
        for key, value in overrides.items():
            if key == "object":
                payload["objects"][0].update(value)
            else:
                payload[key] = value
        return payload

    def test_schema_rejects_missing_required_fields(self):
        validator = self._schema()
        for drop in ("decomposition_id", "source_ref", "canvas", "objects"):
            payload = self._payload()
            payload.pop(drop)
            self.assertTrue(
                list(validator.iter_errors(payload)),
                f"missing {drop} must be rejected",
            )

    def test_schema_rejects_empty_object_id(self):
        validator = self._schema()
        payload = self._payload(object={"object_id": ""})
        self.assertTrue(list(validator.iter_errors(payload)))

    def test_schema_rejects_unknown_object_kind(self):
        validator = self._schema()
        payload = self._payload(object={"kind": "polygon"})
        self.assertTrue(list(validator.iter_errors(payload)))

    def test_schema_rejects_bad_region(self):
        validator = self._schema()
        payload = self._payload(object={"region": {"x": 0, "y": 0, "width": -1, "height": 5}})
        self.assertTrue(list(validator.iter_errors(payload)))

    def test_schema_rejects_bad_mapping_state(self):
        validator = self._schema()
        payload = self._payload(object={"mapping_state": "verified"})
        self.assertTrue(list(validator.iter_errors(payload)))


if __name__ == "__main__":
    unittest.main()
