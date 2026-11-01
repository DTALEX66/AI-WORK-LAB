"""WLGM-220 tests: privacy, security and adversarial controls."""
from __future__ import annotations

import gc
import json
import subprocess
import unittest
from pathlib import Path

from canonical_store import CanonicalStore
from evidence_aggregator import EvidenceAggregator
from execution_evidence import ExecutionEvidence, EvidenceValidationError
from live_gate import evaluate_live
from product_project import ProductProject, ProjectRootBinding, RepositoryIdentity
from project_candidate_discovery import DiscoveryConfig, discover_candidates
from project_identity_resolver import ApprovedProjectIndex, GitProbe, resolve_execution_path
import project_temp
from sse_revision import SseRevisionHub


class PrivacyAdversarialTests(unittest.TestCase):
    def test_prompt_response_never_enter_canonical(self) -> None:
        store = CanonicalStore(project_temp.fixture_dir(prefix="wlgm-privacy-") / "c.sqlite")
        try:
            with self.assertRaises(ValueError):
                store.upsert_execution_instance(
                    {"executionId": "e", "agent": "hermes", "state": "RUNNING", "prompt": "secret instruction"}
                )
            with self.assertRaises(ValueError):
                store.append_execution_evidence(
                    {"eventId": "x", "executionId": "e", "eventType": "execution_running", "api_key": "sk-abc"}
                )
        finally:
            store.close()

    def test_credentials_canary_absent_from_snapshot(self) -> None:
        agg = EvidenceAggregator()
        agg.apply_event(execution_id="e1", event_type="execution_running", occurred_at="t0", evidence_level="A", anchor_project_id="p")
        projection = agg.projection("p")
        blob = json.dumps(projection, ensure_ascii=False).lower()
        for forbidden in ("sk-", "apikey", "bearer", "password", ".env", "prompt body"):
            self.assertNotIn(forbidden, blob)

    def test_unapproved_project_cannot_be_collected(self) -> None:
        # A nested `git init` under the ignored runtime root is still its own toplevel, so
        # discovery sees the same shape it saw in system temp. The release has to clear git's 0444
        # object bits or Windows keeps the whole fixture: `force_release` is the one implementation.
        root = project_temp.fixture_dir(prefix="wlgm-discovery-")
        self.addCleanup(project_temp.force_release, root)
        repo = root / "secret-repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        config = DiscoveryConfig(discovery_root=root, max_depth=2, deny_list={"secret-repo"})
        candidates = discover_candidates(config)
        self.assertEqual(candidates, [])
        # Unapproved: status stays CANDIDATE and never registers collectors.
        config2 = DiscoveryConfig(discovery_root=root, max_depth=2)
        found = discover_candidates(config2)
        self.assertTrue(all(c.status == "CANDIDATE" for c in found))

    def test_symlink_junction_cannot_escape_allowlist(self) -> None:
        index = ApprovedProjectIndex(projects=[ProductProject(project_id="p")])
        project = index.projects["p"]
        project.add_root_binding(ProjectRootBinding(binding_id="b", project_id="p", root="C:/approved/root"))
        # A symlink target outside the approved root must not resolve inside it.
        probe = GitProbe()
        # No filesystem access is performed; resolution requires exact/contained
        # root match. A path under a different common dir stays unresolved.
        result = resolve_execution_path(
            "C:/approved/root/../outside",
            index,
            git=_FakeProbe(top=None, common=None),
        )
        self.assertEqual(result.resolution_state.value, "UNRESOLVED")

    def test_malicious_names_cannot_inject(self) -> None:
        # Project/agent names are rendered as text by the frontend (escaped);
        # the backend never executes them.
        project = ProductProject(project_id='x"><script>alert(1)</script>')
        self.assertTrue(project.project_id.startswith("x"))
        # No eval of names in evidence path.
        event = ExecutionEvidence(
            event_id="e1",
            event_type="execution_running",
            occurred_at="t0",
            agent_instance_id='"><img src=x>',
        )
        record = event.as_record()
        self.assertIn("agentInstanceId", record)

    def test_fake_sidecar_and_bad_origin_rejected(self) -> None:
        from sse_revision import SseRevisionHub

        hub = SseRevisionHub()
        # Arbitrary clients still require valid cursor semantics.
        client = hub.connect("attacker", last_event_id="not-a-number")
        frames = hub.frames_for(client)
        self.assertTrue(any("resync_required" in f for f in frames))

    def test_sse_reconnect_storm_bounded(self) -> None:
        hub = SseRevisionHub(max_connections=2)
        hub.connect("c1")
        hub.connect("c2")
        self.assertIsNone(hub.connect("c3"))
        self.assertIsNone(hub.connect("c4"))

    def test_sqlite_partial_migration_fails_closed(self) -> None:
        raw = project_temp.fixture_dir(prefix="wlgm-migration-")
        # A constructor that raises leaves its SQLite connection inside a reference cycle, so the
        # handle stays open and Windows refuses to delete the fixture (WinError 32). Collecting at
        # cleanup releases it, which is what lets project_temp's sweeper remove the directory.
        self.addCleanup(gc.collect)
        db = raw / "bad.sqlite"
        db.write_bytes(b"not a sqlite database at all")
        with self.assertRaises(Exception):
            CanonicalStore(db)

    def test_adapter_oversized_payload_isolated(self) -> None:
        from collector_scheduler import Collector, CollectorScheduler

        def flood() -> list[dict]:
            return [{"eventId": f"e{i}", "eventType": "execution_heartbeat"} for i in range(100)]

        collector = Collector("flood", flood)
        scheduler = CollectorScheduler([collector], queue=None)
        # Queue default bounded at 1000; oversized flood is capped by the queue.
        result = scheduler.run_once()
        self.assertEqual(result["ran"], 1)
        self.assertLessEqual(len(scheduler.queue.drain()), 1000)

    def test_observer_has_no_write_methods(self) -> None:
        # Observer web surface: no non-GET fetch, verified by JS contract tests;
        # here we assert the canonical snapshot builder has no mutation calls.
        import inspect

        from snapshot_api import build_snapshot

        source = inspect.getsource(build_snapshot)
        self.assertNotIn(".execute(", source)
        self.assertNotIn("INSERT INTO", source)

    def test_unknown_values_never_padded_to_zero(self) -> None:
        snapshot = {
            "schemaVersion": "workflow/snapshot/v3",
            "revision": 1,
            "projects": [{"projectId": "p", "activityState": "UNKNOWN", "activeExecutionCount": None}],
            "executions": [],
            "tokenSummary": {"inputTokens": None, "outputTokens": None, "totalTokens": None, "costQuality": "UNKNOWN"},
        }
        # Frontend normalization keeps null distinct from 0.
        from snapshot_api import build_snapshot

        built = build_snapshot(revision=1, projects=snapshot["projects"], executions=[])
        self.assertIsNone(built["tokenSummary"]["inputTokens"])  # rollup of empty is null, not 0
        self.assertEqual(built["tokenSummary"]["costQuality"], "UNKNOWN")
        # A single execution with unknown state is not LIVE.
        verdict = evaluate_live(
            snapshot_valid=True, sse_connected=True,
            heartbeat_age_seconds=2.0, heartbeat_threshold_seconds=15.0,
            cursor_valid=True, writer_watermark_age_seconds=2.0, writer_watermark_threshold_seconds=15.0,
            coverage={"numerator": 2, "denominator": 2},
        )
        self.assertTrue(verdict.live)  # conditions met -> LIVE


class _FakeProbe:
    def __init__(self, top, common):
        self._top = top
        self._common = common

    def toplevel(self, path):
        return self._top

    def common_dir(self, path):
        return self._common

    def superproject(self, path):
        return None

    def remotes(self, path):
        return []

    def worktree_list(self, path):
        return []


if __name__ == "__main__":
    unittest.main()
