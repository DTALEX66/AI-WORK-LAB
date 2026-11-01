from __future__ import annotations

import hashlib
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))
sys.path.insert(0, str(ROOT / "services" / "authority"))

def load(name: str):
    # Modules migrated to services/*, packages/client-neutral-core/scripts, integrations/*;
    # tests/conftest.py already adds those roots to sys.path.
    return importlib.import_module(name)

identity = load("platform_identity")
reconciler = load("instance_reconciler")
repro = load("controlled_repro")


def obs(**kw):
    base = {"logical_instance_id": "hermes-main", "package_identity": "nous.hermes", "executable_realpath": "C:/Hermes/hermes.exe", "binary_digest": hashlib.sha256(b"hermes").hexdigest(), "discovered_version": "1", "launcher_id": "cli", "launcher_target": "C:/Hermes/hermes.exe", "effective_config_root": "C:/Users/ALEX/.hermes", "profile_id": "default", "freshness": "CURRENT"}
    base.update(kw)
    return base

class ReconcilerTests(unittest.TestCase):
    def test_unique_chain_allows_apply(self):
        result = reconciler.reconcile(identity.resolve_identity([obs()]))
        self.assertTrue(result["apply_allowed"])
        self.assertEqual(result["chains"][0]["config_root"], "C:/Users/ALEX/.hermes")

    def test_split_chain_never_selects_config(self):
        projection = identity.resolve_identity([obs(), obs(launcher_id="desktop", effective_config_root="C:/Users/ALEX/.hermes-alt")])
        result = reconciler.reconcile(projection)
        self.assertFalse(result["apply_allowed"])
        self.assertIsNone(result["chains"][0]["config_root"])

    def test_controlled_repro_only_classifies_metadata(self):
        result = repro.controlled_repro([{"layer": "desktop_internal", "before": {"digest": "a"}, "after": {"digest": "b"}}])
        self.assertEqual(result["classification"], "PLATFORM_INTERNAL_STATE_CHANGED")
        self.assertNotIn("content", result)

if __name__ == "__main__":
    unittest.main()
