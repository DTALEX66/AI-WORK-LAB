"""WUI-10 constraint 3: restore-point scope, publish digest, guarded restore.

The recovery point keeps only the prior value of the field this operation
touched, plus the digest of the state it published.  A restore is automatic
only while that digest still matches; a concurrent change is preserved and the
restore is refused.  Every path here uses a temporary directory: no real client
target, no ``config.apply``, no network.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _load(name: str, relative: str):
    path = os.path.join(ROOT, *relative.split("/"))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _sha(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


class RecoveryPointTests(unittest.TestCase):
    TARGET = "display.language"

    def setUp(self) -> None:
        self.loop_mod = _load("wui10_sfal", "services/policy/single_field_apply_loop.py")
        self.baseline = _load(
            "wui10_baseline", "integrations/executors/hermes/managed_asset_baseline.py")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.state_dir = os.path.join(self._tmp.name, "state")
        os.makedirs(self.state_dir, exist_ok=True)
        self.home = os.path.join(self._tmp.name, "home")
        os.makedirs(self.home, exist_ok=True)
        self.loop = self.loop_mod.SingleFieldApplyLoop(self.state_dir, "op-wui10")

    def _seed_prior(self, value: str) -> None:
        path = os.path.join(self.state_dir, "single_field_state.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({self.TARGET: value}, fh, indent=2, sort_keys=True)

    def _plan_and_apply(self, prior: str, target: str) -> dict:
        plan = self.loop.plan({
            "path": self.TARGET,
            "old_value": prior,
            "new_value": target,
            "adapter": "hermes",
        })
        self.assertEqual(plan["status"], "PLANNED")
        out = self.loop.apply(plan)
        self.assertEqual(out["status"], "APPLIED")
        self.assertEqual(out["readback"]["status"], "PASS")
        return out

    def test_restore_point_holds_only_the_touched_field(self) -> None:
        self._seed_prior("en")
        applied = self._plan_and_apply("en", "zh")
        published = _sha(self.loop.state_file)

        with open(self.loop.applied_ledger, "r", encoding="utf-8") as fh:
            ledger = json.load(fh)
        self.assertEqual(ledger["last_written"], {self.TARGET: "zh"})
        with open(self.loop.state_file, "r", encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), {self.TARGET: "zh"})

        restored = self.loop.restore(self.TARGET, "en")
        self.assertEqual(restored["status"], "RESTORED")
        self.assertNotEqual(_sha(self.loop.state_file), published)
        self.assertEqual(self.loop.readback(self.TARGET, "en")["status"], "PASS")
        with open(self.loop.state_file, "r", encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), {self.TARGET: "en"})

        card = self.loop_mod.honest_card_status(applied)
        self.assertTrue(card["mechanism_proven"])
        self.assertFalse(card["real_adapter_exercised"])
        self.assertEqual(card["real_field_status"], "NOT_PASSED_AWAITING_AUTHORIZATION")

    def test_restore_requires_the_published_digest_to_still_match(self) -> None:
        self._seed_prior("en")
        self._plan_and_apply("en", "zh")
        published = _sha(self.loop.state_file)

        # A concurrent user edit lands after publish: the published digest no
        # longer matches, so the restore must be refused and the value kept.
        self.loop._write_field(self.TARGET, "de")
        after_concurrent = _sha(self.loop.state_file)
        self.assertNotEqual(after_concurrent, published)

        with self.assertRaises(self.loop_mod.FieldConflictRefused):
            self.loop.restore(self.TARGET, "en")
        self.assertEqual(self.loop.readback(self.TARGET, "de")["status"], "PASS")
        with open(self.loop.state_file, "r", encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), {self.TARGET: "de"})

    def test_publish_set_digest_must_be_unchanged(self) -> None:
        target = "skills/example/SKILL.md"
        baseline_sha = "a" * 64
        candidate_sha = "b" * 64
        targets = {
            target: {
                "live_sha256": baseline_sha,
                "live_exists": True,
                "candidate_sha256": candidate_sha,
            }
        }
        state = {"targets": {target: {"sha256": baseline_sha}}, "suspended": []}
        rows = self.baseline.evaluate(targets, state)
        self.assertEqual(rows[0]["verdict"], "CLEAN_UPDATE")

        self.baseline.assert_publish_set_unchanged(
            rows, rows, {target: baseline_sha})

        with self.assertRaises(RuntimeError) as moved:
            self.baseline.assert_publish_set_unchanged(
                rows, rows, {target: "c" * 64})
        self.assertIn("MANAGED_ASSET_PUBLISH_SET_CHANGED", str(moved.exception))

        fresh = [dict(rows[0], verdict="UNKNOWN_LIVE_CHANGE")]
        with self.assertRaises(RuntimeError) as changed:
            self.baseline.assert_publish_set_unchanged(
                rows, fresh, {target: baseline_sha})
        self.assertIn("MANAGED_ASSET_PUBLISH_SET_CHANGED", str(changed.exception))

        recorded = self.baseline.baseline_records(rows)
        self.assertEqual(recorded, {target: {"sha256": candidate_sha}})

    def test_interrupted_run_is_diagnosed_not_guessed(self) -> None:
        target = "skills/example/SKILL.md"
        self.baseline.write_pending(
            self.home,
            run_id="run-wui10",
            phase="publish",
            records={target: {"candidate_sha256": "b" * 64}},
        )
        diagnosis = self.baseline.pending_diagnosis(self.home)
        self.assertIsNotNone(diagnosis)
        self.assertIn("MANAGED_ASSET_RUN_INCOMPLETE", diagnosis)
        self.assertIn("run_id=run-wui10", diagnosis)
        self.assertIn("phase=publish", diagnosis)
        self.assertIn(target, diagnosis)
        self.baseline.clear_pending(self.home)
        self.assertIsNone(self.baseline.pending_diagnosis(self.home))


if __name__ == "__main__":
    unittest.main(verbosity=2)
