from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "packages/client-neutral-core/scripts/growth_watcher.py"


def load_module():
    spec = importlib.util.spec_from_file_location("growth_watcher", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def memory_record(**overrides: object) -> dict:
    value = {
        "schema_version": "workflow/runtime-context-record/v1",
        "memory_id": "memory-1",
        "layer": "session",
        "kind": "preference",
        "status": "observed",
        "project_id": "work-lab",
        "source_digest": "a" * 64,
        "content_digest": "b" * 64,
        "confidence": "medium",
        "promotion": "manual-approval",
        "redaction": {"prompt_response_bodies": "excluded", "credentials": "excluded"},
    }
    value.update(overrides)
    return value


class GrowthWatcherTests(unittest.TestCase):
    def test_memory_observation_has_no_body_and_isolated_promotion(self) -> None:
        module = load_module()
        observed = module.validate_memory(memory_record())
        self.assertEqual(observed["status"], "observed")
        proposed = module.propose_memory(observed, "project")
        self.assertEqual(proposed["status"], "proposed")
        with self.assertRaisesRegex(ValueError, "approval"):
            module.approve_memory(proposed)
        approved = module.approve_memory(proposed, approval=True)
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(approved["layer"], "project")

    def test_memory_global_promotion_is_not_implicit(self) -> None:
        module = load_module()
        with self.assertRaisesRegex(ValueError, "global"):
            module.propose_memory(memory_record(), "global")

    def test_watcher_is_read_only_and_quarantines_unknown_candidate(self) -> None:
        module = load_module()
        result = module.watch_candidates(
            [{"candidateId": "known", "sourceDigest": "a" * 64}, {"candidateId": "new", "sourceDigest": "c" * 64}],
            {"known": "a" * 64},
        )
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["new_candidate_ids"], ["new"])
        self.assertEqual(result["quarantined_candidate_ids"], ["new"])

    def test_rule_drift_projection_reports_changes_without_mutation(self) -> None:
        module = load_module()
        baseline = {"rule-a": "a" * 64, "rule-b": "b" * 64}
        observed = {"rule-a": "c" * 64, "rule-c": "d" * 64}
        projection = module.project_rule_drift(baseline, observed)
        self.assertEqual(projection["status"], "REVIEW_REQUIRED")
        self.assertEqual([item["state"] for item in projection["drift"]], ["changed", "missing", "new"])
        self.assertEqual(baseline, {"rule-a": "a" * 64, "rule-b": "b" * 64})

    def test_malformed_memory_record_fails_closed(self) -> None:
        module = load_module()
        bad = memory_record()
        bad["content"] = "must not be persisted"
        with self.assertRaisesRegex(ValueError, "invalid memory"):
            module.validate_memory(bad)


if __name__ == "__main__":
    unittest.main()