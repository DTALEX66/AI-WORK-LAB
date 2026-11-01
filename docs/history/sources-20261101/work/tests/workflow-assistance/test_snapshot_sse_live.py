"""WLGM-150/160/170 tests: snapshot API, persistent SSE, evidence-driven LIVE."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "workflow"))

from live_gate import evaluate_live
from snapshot_api import build_snapshot
from sse_revision import SseRevisionHub, resync_frame


class SnapshotApiTests(unittest.TestCase):
    def test_snapshot_has_required_meta(self) -> None:
        snapshot = build_snapshot(revision=3, generated_at="2026-08-14T00:00:00Z")
        self.assertEqual(snapshot["schemaVersion"], "workflow/snapshot/v3")
        self.assertEqual(snapshot["revision"], 3)
        self.assertEqual(snapshot["generatedAt"], "2026-08-14T00:00:00Z")
        self.assertIn("projects", snapshot)
        self.assertIn("executions", snapshot)
        self.assertIn("tasks", snapshot)
        self.assertIn("tokenSummary", snapshot)

    def test_null_vs_zero_distinct(self) -> None:
        snapshot = build_snapshot(revision=1)
        # No usage -> null, not 0; costQuality UNKNOWN, never EXACT.
        self.assertIsNone(snapshot["tokenSummary"]["inputTokens"])
        self.assertIsNone(snapshot["tokenSummary"]["outputTokens"])
        self.assertIsNone(snapshot["tokenSummary"]["totalTokens"])
        self.assertEqual(snapshot["tokenSummary"]["costQuality"], "UNKNOWN")
        self.assertEqual(snapshot["executions"], [])
        project = snapshot["projects"][0] if snapshot["projects"] else {
            "projectId": "p", "token": {"inputTokens": None, "outputTokens": None, "totalTokens": None, "costQuality": "UNKNOWN"}
        }
        self.assertIsNone(project["token"]["inputTokens"])

    def test_partial_usage_missing_field_is_null(self) -> None:
        """P0-3: a field missing from every sample stays null, not 0."""
        snapshot = build_snapshot(
            revision=1,
            usage=[{"projectId": "p", "inputTokens": 10, "costQuality": "EXACT"}],
            projects=[{"projectId": "p", "displayName": "P"}],
        )
        self.assertEqual(snapshot["tokenSummary"]["inputTokens"], 10)
        self.assertIsNone(snapshot["tokenSummary"]["outputTokens"])
        self.assertIsNone(snapshot["tokenSummary"]["totalTokens"])
        self.assertIsNone(snapshot["projects"][0]["token"]["outputTokens"])
        self.assertEqual(snapshot["projects"][0]["token"]["inputTokens"], 10)

    def test_executions_is_flat_list(self) -> None:
        """P0-3: executions must be a 1-D list, never [[...]]."""
        snapshot = build_snapshot(
            revision=1,
            executions=[{"executionId": "e1", "state": "RUNNING", "anchorProjectId": "p"}],
        )
        self.assertIsInstance(snapshot["executions"], list)
        self.assertEqual(len(snapshot["executions"]), 1)
        self.assertEqual(snapshot["executions"][0]["executionId"], "e1")
        self.assertIsInstance(snapshot["executions"][0], dict)

    def test_transport_events_url_passthrough(self) -> None:
        """P0-4: eventsUrl flows through transport when provided; null otherwise."""
        with_events = build_snapshot(
            revision=1,
            transport={"transportState": "LIVE", "eventsUrl": "http://127.0.0.1:9/api/v1/events"},
        )
        self.assertEqual(with_events["transport"]["eventsUrl"], "http://127.0.0.1:9/api/v1/events")
        without = build_snapshot(revision=1)
        self.assertIsNone(without["transport"]["eventsUrl"])

    def test_token_rollup_exact_estimated(self) -> None:
        snapshot = build_snapshot(
            revision=1,
            usage=[
                {"projectId": "p", "inputTokens": 10, "outputTokens": 5, "totalTokens": 15, "costQuality": "EXACT"},
                {"projectId": "p", "inputTokens": 2, "outputTokens": 3, "totalTokens": 5, "costQuality": "ESTIMATED"},
            ],
            projects=[{"projectId": "p", "displayName": "P"}],
        )
        self.assertEqual(snapshot["tokenSummary"]["inputTokens"], 12)
        self.assertEqual(snapshot["tokenSummary"]["costQuality"], "ESTIMATED")

    def test_git_match_state(self) -> None:
        matched = build_snapshot(revision=1, git_state={"localSha": "a" * 40, "remoteSha": "a" * 40, "ciSha": "a" * 40})
        self.assertEqual(matched["git"]["matchState"], "MATCH")
        no_local = build_snapshot(revision=1, git_state={})
        self.assertEqual(no_local["git"]["matchState"], "NO_LOCAL_CLAIM")

    def test_execution_projection_separated_from_tasks(self) -> None:
        snapshot = build_snapshot(
            revision=1,
            store_projection={"tasks_by_status": {"PENDING": 2}},
            executions=[{"executionId": "e1", "anchorProjectId": "p", "state": "RUNNING", "sourceRef": "src-1", "workingArea": "services/x"}],
            projects=[{"projectId": "p", "displayName": "P"}],
        )
        self.assertEqual(snapshot["tasks"], {"PENDING": 2})
        self.assertEqual(snapshot["projects"][0]["activeExecutionCount"], 1)
        self.assertEqual(snapshot["projects"][0]["workingAreas"], ["services/x"])

    def test_governance_drift_projection(self) -> None:
        snapshot = build_snapshot(revision=1, governance={
            "state": "DRIFT",
            "rules": {"current": 12, "drift": 1},
            "skills": {"current": 13, "drift": 0},
            "adapters": {"current": 4, "drift": 0},
        })
        families = snapshot["governance"]["families"]
        self.assertEqual(families["rules"]["state"], "DRIFT")
        self.assertEqual(families["skills"]["state"], "CLEAN")
        self.assertEqual(families["memory"]["state"], "UNKNOWN")
        self.assertEqual(snapshot["governance"]["state"], "DRIFT")

    def test_governance_unknown_when_absent(self) -> None:
        snapshot = build_snapshot(revision=1)
        self.assertEqual(snapshot["governance"]["state"], "UNKNOWN")
        self.assertIsNone(snapshot["governance"]["families"]["rules"]["current"])


class SseRevisionHubTests(unittest.TestCase):
    def test_resync_helper_binds_the_revision_as_event_id(self) -> None:
        frame = resync_frame("manual_recovery", 42)
        self.assertIn("event: resync_required", frame)
        self.assertIn("id: 42", frame)

    def test_publish_increments_persistent_revision(self) -> None:
        hub = SseRevisionHub()
        r1 = hub.publish("observed", {"executionId": "e1"})
        r2 = hub.publish("heartbeat", {"ts": 1})
        self.assertEqual(r2, r1 + 1)
        self.assertEqual(hub.current_revision, 2)

    def test_hub_seed_keeps_restart_revision_monotonic(self) -> None:
        """P0: a restarted hub must continue from the persisted seed so a
        client's Last-Event-ID never sees a rolled-back cursor."""
        hub = SseRevisionHub()
        for _ in range(5):
            hub.publish("observed", {"executionId": "e1"})
        self.assertEqual(hub.current_revision, 5)
        restarted = SseRevisionHub(seed_revision=hub.current_revision)
        self.assertEqual(restarted.current_revision, 5)
        next_revision = restarted.publish("observed", {"executionId": "e2"})
        self.assertEqual(next_revision, 6)
        self.assertEqual(restarted.current_revision, 6)

    def test_unknown_event_rejected(self) -> None:
        hub = SseRevisionHub()
        with self.assertRaises(ValueError):
            hub.publish("teleport", {})

    def test_last_event_id_replay(self) -> None:
        hub = SseRevisionHub()
        hub.publish("observed", {"executionId": "e1"})
        hub.publish("observed", {"executionId": "e2"})
        client = hub.connect("c1", last_event_id="1")
        frames = hub.frames_for(client)
        self.assertEqual(len(frames), 1)
        self.assertIn("e2", frames[0])
        self.assertIn("id: 2", frames[0])

    def test_gap_triggers_resync_required(self) -> None:
        hub = SseRevisionHub()
        hub.publish("observed", {"executionId": "e1"})
        hub.publish("observed", {"executionId": "e2"})
        hub._history = hub._history[-1:]  # simulate prune: seq 1 gone
        client = hub.connect("c1", last_event_id="1")
        frames = hub.frames_for(client)
        self.assertTrue(any("resync_required" in f for f in frames))
        self.assertTrue(any("id: 2" in f for f in frames))
        self.assertEqual(client.last_event_id, "2")
        self.assertEqual(hub.frames_for(client), [], "resync must converge instead of repeating forever")

    def test_cursor_ahead_triggers_resync(self) -> None:
        hub = SseRevisionHub()
        hub.publish("observed", {"executionId": "e1"})
        client = hub.connect("c1", last_event_id="99")
        frames = hub.frames_for(client)
        self.assertTrue(any("resync_required" in f for f in frames))
        self.assertTrue(any("id: 1" in f for f in frames))
        self.assertEqual(client.last_event_id, "1")
        self.assertEqual(hub.frames_for(client), [], "future cursor resync must converge")

    def test_named_event_in_frame(self) -> None:
        hub = SseRevisionHub()
        hub.publish("observed", {"executionId": "e1"})
        client = hub.connect("c1", last_event_id="0")
        frames = hub.frames_for(client)
        self.assertTrue(any("event: observed" in f for f in frames))

    def test_bounded_connections(self) -> None:
        hub = SseRevisionHub(max_connections=2)
        hub.connect("c1")
        hub.connect("c2")
        self.assertIsNone(hub.connect("c3"))

    def test_heartbeat_named_frame(self) -> None:
        hub = SseRevisionHub()
        frame = hub.heartbeat_frame()
        self.assertIn("event: heartbeat", frame)
        self.assertIn("id:", frame)


class LiveGateTests(unittest.TestCase):
    def _all_ok(self, **overrides):
        base = dict(
            snapshot_valid=True,
            sse_connected=True,
            heartbeat_age_seconds=2.0,
            heartbeat_threshold_seconds=15.0,
            cursor_valid=True,
            writer_watermark_age_seconds=3.0,
            writer_watermark_threshold_seconds=15.0,
            coverage={"numerator": 2, "denominator": 2, "scope": "key-collectors"},
            is_fixture=False,
        )
        base.update(overrides)
        return base

    def test_live_when_all_conditions_hold(self) -> None:
        verdict = evaluate_live(**self._all_ok())
        self.assertTrue(verdict.live)
        self.assertEqual(verdict.state, "LIVE")

    def test_any_single_condition_breaks_live(self) -> None:
        cases = [
            {"snapshot_valid": False},
            {"sse_connected": False},
            {"heartbeat_age_seconds": 99.0},
            {"cursor_valid": False},
            {"writer_watermark_age_seconds": 99.0},
            {"is_fixture": True},
            {"coverage": {"numerator": 1, "denominator": 2, "scope": "key-collectors"}},
        ]
        for case in cases:
            with self.subTest(case=case):
                verdict = evaluate_live(**self._all_ok(**case))
                self.assertFalse(verdict.live)

    def test_offline_when_disconnected(self) -> None:
        verdict = evaluate_live(**self._all_ok(sse_connected=False))
        self.assertEqual(verdict.state, "OFFLINE")

    def test_delayed_when_heartbeat_stale_but_connected(self) -> None:
        verdict = evaluate_live(**self._all_ok(heartbeat_age_seconds=99.0, writer_watermark_age_seconds=2.0))
        self.assertEqual(verdict.state, "DELAYED")

    def test_fixture_never_live(self) -> None:
        verdict = evaluate_live(**self._all_ok(is_fixture=True))
        self.assertFalse(verdict.live)
        self.assertIn("no_fixture", verdict.missing)


if __name__ == "__main__":
    unittest.main()
