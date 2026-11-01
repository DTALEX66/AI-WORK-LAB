from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_verifier():
    path = ROOT / "scripts" / "verify_observer_skeleton.py"
    spec = importlib.util.spec_from_file_location("observer_skeleton_verifier", path)
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load observer verifier")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ObserverSkeletonTests(unittest.TestCase):
    def test_profile_is_read_only_observer(self):
        profile = json.loads((ROOT / "module-profile.json").read_text(encoding="utf-8"))
        self.assertEqual(profile["id"], "work-lab-observer")
        self.assertFalse(profile["externalMutationDefault"])

    def test_required_schemas_parse(self):
        for name in ("observer-event.schema.json", "data-quality.schema.json"):
            with self.subTest(name=name):
                schema = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
                self.assertTrue(schema["$id"].startswith("work-lab/"))

    def test_structure_verifier_passes(self):
        self.assertEqual(load_verifier().main(), 0)


if __name__ == "__main__":
    unittest.main()
