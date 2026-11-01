from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from observer_runtime import (  # noqa: E402
    IncrementalCursor,
    ObserverInputError,
    TRANSFERRED_PROJECT_IDS,
    append_events,
    mutation_surface,
    project_projection,
    project_read_only_dashboard,
    project_authority_dashboard,
    project_cost,
    project_tasks,
    project_usage,
    quality_summary,
)


def event(event_id: str, *, task_id: str = "WA-001", quality: str = "source-exact") -> dict:
    return {
        "eventId": event_id,
        "schemaVersion": "work-lab/observer-event/v1",
        "eventType": "task.status",
        "sourceModule": "workflow-assistance",
        "sourceId": "ledger",
        "taskId": task_id,
        "observedAt": "2026-08-06T00:00:00Z",
        "contentDigest": hashlib.sha256(event_id.encode()).hexdigest(),
        "coverage": "full",
        "quality": quality,
    }


class ObserverRuntimeTests(unittest.TestCase):
    def test_incremental_cursor_deduplicates_and_tracks_rotation(self):
        cursor = IncrementalCursor(max_batch=2)
        first = cursor.ingest([event("e1"), event("e2")], next_cursor="b")
        second = cursor.ingest([event("e2"), event("e3")], next_cursor="a")
        self.assertEqual([item["eventId"] for item in first], ["e1", "e2"])
        self.assertEqual([item["eventId"] for item in second], ["e3"])
        self.assertEqual(cursor.rotation, 1)

    def test_event_budget_and_sensitive_input_fail_closed(self):
        with self.assertRaises(ObserverInputError):
            IncrementalCursor(max_batch=1).ingest([event("e1"), event("e2")], next_cursor="a")
        unsafe = event("unsafe")
        unsafe["payload"] = {"token": "[REDACTED]"}
        with self.assertRaises(ObserverInputError):
            IncrementalCursor().ingest([unsafe], next_cursor="a")

    def test_projection_is_rebuildable_and_does_not_change_input(self):
        history = [event("e1"), event("e2", task_id="WA-002", quality="partial")]
        before = [dict(item) for item in history]
        projection = project_tasks(history)
        self.assertEqual(projection["WA-001"]["events"], 1)
        self.assertEqual(projection["WA-002"]["quality"], "partial")
        self.assertEqual(history, before)

    def test_append_is_observer_owned_and_deduplicated(self):
        log = []
        self.assertEqual(append_events(log, [event("e1"), event("e1")]), 1)
        self.assertEqual(len(log), 1)

    def test_quality_and_mutation_surface_are_fail_closed(self):
        summary = quality_summary([event("e1"), event("e2", quality="partial")])
        self.assertEqual(summary["quality"], "partial")
        surface = mutation_surface()
        self.assertFalse(surface["externalMutation"])
        self.assertFalse(surface["ledgerMutation"])
        # R2 third batch: allowedWrites removed entirely — Observer owns no
        # write surface.
        self.assertNotIn("allowedWrites", surface)

    def test_usage_projection_aggregates_only_explicit_metrics(self):
        history = [
            {"usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5, "records": 1}},
            {"usage": {"input_tokens": 4, "output_tokens": 1, "total_tokens": 5, "records": 1}},
        ]
        before = [dict(item) for item in history]
        self.assertEqual(project_usage(history), {"input_tokens": 6, "output_tokens": 4, "total_tokens": 10, "records": 2})
        self.assertEqual(history, before)

    def test_read_only_dashboard_projection_is_rebuildable_and_has_no_controls(self):
        history = [event("e1"), event("e2", task_id="WA-002", quality="partial")]
        projection = project_read_only_dashboard(history)
        self.assertEqual(projection["overview"]["taskCount"], 2)
        self.assertEqual(projection["overview"]["eventCount"], 2)
        self.assertIn("tasks", projection)
        self.assertIn("usage", projection)
        self.assertIn("quality", projection)
        self.assertIn("dataQuality", projection)
        self.assertFalse(projection["mutationSurface"]["externalMutation"])
        serialized = str(projection).lower()
        self.assertNotIn("wa-001", serialized)
        self.assertNotIn("wa-002", serialized)
        self.assertNotIn("open design", serialized)
        self.assertNotIn("approve", serialized)
        self.assertNotIn("retry", serialized)

    def test_cost_projection_is_idempotent_and_uses_explicit_pricing(self):
        events = [
            {"eventId": "u1", "sourceId": "fixture", "usage": {"input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500, "records": 1}},
            {"eventId": "u1", "sourceId": "fixture", "usage": {"input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500, "records": 1}},
        ]
        pricing = {"fixture": {"alias": "fixture", "billing": "metered", "source": "fixture", "effective_at": "2026-08-07", "currency": "USD", "stale": False, "input_per_million": 1, "output_per_million": 2}}
        result = project_cost(events, pricing)
        self.assertEqual(result["records"], 1)
        self.assertEqual(result["estimated_cost"], "0.00200000")
        self.assertEqual(result["cost_status"], "estimated")
        self.assertEqual(result, project_cost(events, pricing))

    def test_cost_projection_marks_subscription_and_stale_pricing_without_fake_dollars(self):
        subscription = [{"eventId": "s1", "sourceId": "codex", "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2, "records": 1}}]
        subscription_pricing = {"codex": {"alias": "codex", "billing": "subscription", "source": "fixture", "effective_at": "2026-08-07", "currency": "USD", "stale": False}}
        self.assertEqual(project_cost(subscription, subscription_pricing)["cost_status"], "subscription/not-metered")
        stale_pricing = {"codex": {"alias": "codex", "billing": "metered", "source": "fixture", "effective_at": "2025-01-01", "currency": "USD", "stale": True, "input_per_million": 1, "output_per_million": 1}}
        stale = project_cost(subscription, stale_pricing)
        self.assertEqual(stale["cost_status"], "stale")
        self.assertIsNone(stale["estimated_cost"])

    def test_cost_projection_rejects_corrupt_usage_and_unknown_pricing_explicitly(self):
        with self.assertRaises(ObserverInputError):
            project_cost([{"eventId": "bad", "sourceId": "fixture", "usage": {"input_tokens": -1}}], {})
        unknown = project_cost([{"eventId": "unknown", "sourceId": "missing", "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2, "records": 1}}], {})
        self.assertEqual(unknown["cost_status"], "unknown")
        self.assertIsNone(unknown["estimated_cost"])

    def test_authority_projection_never_invents_live_running_or_zero_evidence(self):
        empty = project_authority_dashboard([])
        self.assertEqual(empty["mode"], "UNKNOWN")
        self.assertIsNone(empty["ci"]["running"])
        self.assertIsNone(empty["governance"]["memoryContext"]["current"])

        unknown_event = event("unknown-state")
        projection = project_authority_dashboard([unknown_event])
        self.assertEqual(projection["mode"], "SNAPSHOT")
        self.assertEqual(projection["projects"][0]["state"], "unknown")
        self.assertEqual(project_authority_dashboard([unknown_event], mode="LIVE")["mode"], "LIVE")
        with self.assertRaises(ObserverInputError):
            project_authority_dashboard([unknown_event], mode="BOGUS")

    def test_transferred_project_ids_exclude_legacy_minigame(self):
        # Only open-design remains a transferred project id; the retired
        # minigame tree must not be referenced by the Observer anymore.
        self.assertEqual(TRANSFERRED_PROJECT_IDS, {"open-design"})
        open_design_event = event("run")
        open_design_event["projectId"] = "open-design"
        projection = project_projection([open_design_event])
        self.assertEqual(projection["count"], 0)

        work_lab_event = event("run")
        work_lab_event["projectId"] = "work-lab"
        projection = project_projection([open_design_event, work_lab_event])
        self.assertEqual(projection["count"], 1)
        self.assertEqual(projection["projects"][0]["projectId"], "work-lab")


if __name__ == "__main__":
    unittest.main()
