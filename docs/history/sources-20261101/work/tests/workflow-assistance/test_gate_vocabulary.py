"""WLG-030: global tier vocabulary and event contract tests."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/workflow"))

from gate_vocabulary import GLOBAL_TIERS, OBSERVATION_EVENTS, validate_tiers


class GateVocabularyTests(unittest.TestCase):
    def test_global_tiers_are_exactly_the_five_protocol_tiers(self):
        self.assertEqual(
            GLOBAL_TIERS,
            ("TARGETED", "STAGE", "NIGHTLY", "RC", "RELEASE"),
        )

    def test_project_tier_lists_must_be_subsets(self):
        self.assertTrue(validate_tiers(["TARGETED", "STAGE"]))
        self.assertTrue(validate_tiers(["RC", "RELEASE"]))
        self.assertFalse(validate_tiers(["targeted", "module"]))  # old vocabulary
        self.assertFalse(validate_tiers(["full"]))
        self.assertFalse(validate_tiers([]))

    def test_observation_events_are_stable(self):
        self.assertIn("project.profile.loaded", OBSERVATION_EVENTS)
        self.assertIn("gate.plan.observed", OBSERVATION_EVENTS)
        self.assertIn("ci.run.observed", OBSERVATION_EVENTS)
        self.assertIn("stage.qualification.recorded", OBSERVATION_EVENTS)
        self.assertIn("release.evidence.observed", OBSERVATION_EVENTS)

    def test_schemas_use_the_global_tier_vocabulary(self):
        gate_registry = json.loads(
            (ROOT / "packages/contracts/schemas/workflow/gate-registry.schema.json").read_text(encoding="utf-8")
        )
        profile = json.loads(
            (ROOT / "packages/contracts/schemas/workflow/project-profile.schema.json").read_text(encoding="utf-8")
        )
        for schema, path in ((gate_registry, "gate-registry"), (profile, "project-profile")):
            text = json.dumps(schema)
            self.assertIn("TARGETED", text, f"{path} must accept TARGETED")
            self.assertIn("RELEASE", text, f"{path} must accept RELEASE")
            # old tier values must not appear as enum items
            self.assertNotIn('"enum": ["targeted"', text, f"{path} must not accept old 'targeted' tier")
            self.assertNotIn('"module", "full"', text, f"{path} must not accept old 'module/full' tiers")

    def test_profile_registry_uses_global_tiers(self):
        registry = json.loads(
            (ROOT / "config/project-profiles.json").read_text(encoding="utf-8")
        )
        for profile in registry["profiles"]:
            for gate in profile.get("gates", {}).values():
                self.assertTrue(
                    validate_tiers(gate.get("tiers")),
                    f"{profile['project']['id']} gate tiers must use GLOBAL_TIERS",
                )


if __name__ == "__main__":
    unittest.main()
