"""Managed-asset guard tests, including the data-preservation counter-examples
required by the independent review (R1, R2, R4, R6).

Each test below is written so that it FAILS if the guard ever overwrites content
it did not publish. A green guard suite is not evidence of correctness on its own
- the earlier suite passed while adoption silently overwrote reviewed-away live
content - so the assertions here are deliberately about bytes preserved, not
about exit codes.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "integrations/executors/hermes" / "sync_hermes_workflow_assets.py"

CONTRACT = """schema_version: 1
managed:
  display.language: replace
  display.busy_input_mode: replace
preserved:
- model.provider
- model.default
- model.api_key
global_workflow:
  scope: portable-managed-assets
  source_of_truth: repository
  owned_asset_roots:
  - packages/client-neutral-core/skills/demo/alpha
  owned_binary_paths:
  - packages/client-neutral-core/bin/demo-tool
  owned_file_mappings:
  - source: config/SOUL.md
    target: SOUL.md
"""

SKILL_ROOT_REL = "skills/demo/alpha"
SKILL_MD_REL = f"{SKILL_ROOT_REL}/SKILL.md"
BIN_REL = "bin/demo-tool"


def load_module():
    spec = importlib.util.spec_from_file_location("workflow_sync_guard", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GuardFixture:
    """Synthetic repo + Hermes home that satisfy the sync contract."""

    def __init__(self, base: Path) -> None:
        self.repo = base / "repo"
        self.home = base / "home"
        (self.repo / "config").mkdir(parents=True)
        (self.repo / "packages/client-neutral-core/skills/demo/alpha").mkdir(parents=True)
        (self.repo / "packages/client-neutral-core/bin").mkdir(parents=True)
        self.home.mkdir(parents=True)
        (self.repo / "config/managed-config-schema.yaml").write_text(CONTRACT, encoding="utf-8")
        (self.repo / "config/SOUL.md").write_text("# soul v1\n", encoding="utf-8")
        (self.repo / "config/.env.template").write_text("TEMPLATE=1\n", encoding="utf-8")
        (self.repo / "packages/client-neutral-core/skills/demo/alpha/SKILL.md").write_text(
            "# alpha v1\n", encoding="utf-8"
        )
        (self.repo / "packages/client-neutral-core/bin/demo-tool").write_text("#!/bin/sh\n", encoding="utf-8")

    def bump_candidate(self) -> None:
        (self.repo / "packages/client-neutral-core/skills/demo/alpha/SKILL.md").write_text(
            "# alpha v2\n", encoding="utf-8"
        )

    def live(self, relative: str) -> Path:
        return self.home / relative

    def write_live(self, relative: str, text: str) -> None:
        target = self.live(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def live_bytes(self, relative: str) -> bytes:
        return self.live(relative).read_bytes()


class ManagedAssetGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.fixture = GuardFixture(Path(self._temp.name))

    # --- helpers -----------------------------------------------------------
    def verdicts(self, **kwargs):
        rows = self.module.guard_rows(self.fixture.repo, self.fixture.home, **kwargs)
        return {row["target"]: row["verdict"] for row in rows}

    def publish(self, **kwargs):
        self.module.deploy_portable(self.fixture.repo, self.fixture.home, apply=True, **kwargs)

    def adopt(self, reviewed: dict, **kwargs):
        return self.module.adopt_baselines(
            self.fixture.repo, self.fixture.home, reviewed=reviewed, **kwargs
        )

    def live_digest(self, relative: str) -> str:
        inputs = self.module.managed_guard_inputs(self.fixture.repo, self.fixture.home)
        return inputs[relative]["live_sha256"]

    # ===================================================================== #
    # R4 - deletion drift vs first install
    # ===================================================================== #
    def test_absent_target_without_baseline_is_a_first_install(self) -> None:
        self.assertEqual(self.verdicts()[SKILL_ROOT_REL], "CLEAN_UPDATE")
        self.publish()
        expected = (self.fixture.repo / "packages/client-neutral-core/skills/demo/alpha/SKILL.md").read_bytes()
        self.assertEqual(self.fixture.live_bytes(SKILL_MD_REL), expected)

    def test_deleting_a_baselined_target_is_drift_and_is_refused(self) -> None:
        """Removing the whole managed unit is drift; it must not be silently reinstalled."""
        self.publish()
        shutil.rmtree(self.fixture.live(SKILL_ROOT_REL))
        self.assertEqual(self.verdicts()[SKILL_ROOT_REL], "DELETED_DRIFT")
        with self.assertRaisesRegex(RuntimeError, "MANAGED_ASSET_LIVE_CHANGE_REFUSED"):
            self.publish()
        self.assertFalse(self.fixture.live(SKILL_ROOT_REL).exists(), "a user deletion must not be auto-reinstalled")

    def test_partial_deletion_inside_a_managed_unit_is_refused(self) -> None:
        self.publish()
        self.fixture.live(SKILL_MD_REL).unlink()
        self.assertEqual(self.verdicts()[SKILL_ROOT_REL], "UNKNOWN_LIVE_CHANGE")
        with self.assertRaisesRegex(RuntimeError, "MANAGED_ASSET_LIVE_CHANGE_REFUSED"):
            self.publish()
        self.assertFalse(self.fixture.live(SKILL_MD_REL).exists())

    def test_absent_candidate_source_is_refused(self) -> None:
        """Removing live content is never this tool's decision.

        A managed skill root or binary that disappears from the repository is
        rejected earlier by the ownership contract, so the reachable case is the
        un-validated ``.env.template`` mapping.
        """
        self.publish()
        (self.fixture.repo / "config/.env.template").unlink()
        self.assertEqual(self.verdicts()[".env.template"], "CANDIDATE_ABSENT")
        with self.assertRaisesRegex(RuntimeError, "MANAGED_ASSET_LIVE_CHANGE_REFUSED"):
            self.publish()
        self.assertTrue(self.fixture.live(".env.template").exists())

    # ===================================================================== #
    # R2 - converged targets are not rewritten
    # ===================================================================== #
    def test_repeat_apply_converges_and_writes_nothing(self) -> None:
        self.publish()
        rows = self.module.guard_rows(self.fixture.repo, self.fixture.home)
        self.assertEqual(self.module.asset_baseline.written_targets(rows), [])
        before = self.fixture.live_bytes(SKILL_MD_REL)
        self.publish()
        self.assertEqual(self.fixture.live_bytes(SKILL_MD_REL), before)

    def test_native_edit_after_publish_is_refused_and_preserved(self) -> None:
        self.publish()
        self.fixture.write_live(SKILL_MD_REL, "# alpha v1\n\nnative curator lesson\n")
        self.assertEqual(self.verdicts()[SKILL_ROOT_REL], "UNKNOWN_LIVE_CHANGE")
        with self.assertRaisesRegex(RuntimeError, "MANAGED_ASSET_LIVE_CHANGE_REFUSED"):
            self.publish()
        self.assertIn(b"native curator lesson", self.fixture.live_bytes(SKILL_MD_REL))

    def test_unknown_extra_file_in_managed_tree_is_refused(self) -> None:
        self.publish()
        self.fixture.write_live(f"{SKILL_ROOT_REL}/references/native-lesson.md", "curator content\n")
        self.assertEqual(self.verdicts()[SKILL_ROOT_REL], "UNKNOWN_LIVE_CHANGE")
        with self.assertRaisesRegex(RuntimeError, "MANAGED_ASSET_LIVE_CHANGE_REFUSED"):
            self.publish()
        self.assertTrue(self.fixture.live(f"{SKILL_ROOT_REL}/references/native-lesson.md").is_file())

    def test_publish_set_recheck_refuses_when_a_verdict_moves(self) -> None:
        """R2: the re-check covers every written target and re-evaluates, not just re-digests."""
        self.publish()
        self.fixture.bump_candidate()  # now CLEAN_UPDATE (live == baseline, candidate moved)
        planned = self.module.guard_rows(self.fixture.repo, self.fixture.home)
        self.assertIn(SKILL_ROOT_REL, self.module.asset_baseline.written_targets(planned))
        fresh = [dict(row, verdict="UNKNOWN_LIVE_CHANGE") if row["target"] == SKILL_ROOT_REL else row for row in planned]
        live_states = {row["target"]: row["live_sha256"] for row in planned}
        with self.assertRaisesRegex(RuntimeError, "MANAGED_ASSET_PUBLISH_SET_CHANGED"):
            self.module.asset_baseline.assert_publish_set_unchanged(planned, fresh, live_states)

    def test_publish_set_recheck_refuses_when_a_digest_moves(self) -> None:
        self.publish()
        self.fixture.bump_candidate()
        planned = self.module.guard_rows(self.fixture.repo, self.fixture.home)
        live_states = {row["target"]: row["live_sha256"] for row in planned}
        live_states[SKILL_ROOT_REL] = "moved"
        with self.assertRaisesRegex(RuntimeError, "MANAGED_ASSET_PUBLISH_SET_CHANGED"):
            self.module.asset_baseline.assert_publish_set_unchanged(planned, planned, live_states)

    # ===================================================================== #
    # R1 - adoption records a baseline and writes nothing
    # ===================================================================== #
    def test_adoption_records_baseline_and_preserves_content(self) -> None:
        self.fixture.write_live(SKILL_MD_REL, "# alpha v0 native\n")
        before = self.fixture.live_bytes(SKILL_MD_REL)
        digest = self.live_digest(SKILL_ROOT_REL)
        self.assertEqual(self.verdicts()[SKILL_ROOT_REL], "NO_BASELINE")

        adopted = self.adopt({SKILL_ROOT_REL: digest})

        self.assertEqual(adopted, [SKILL_ROOT_REL])
        self.assertEqual(self.fixture.live_bytes(SKILL_MD_REL), before, "adoption must not touch content")
        # the native v0 content is now the baseline, so a publish is a normal update
        state = self.module.asset_baseline.load_state(self.fixture.home)
        self.assertEqual(state["targets"][SKILL_ROOT_REL]["sha256"], digest)
        self.assertEqual(state["adopted"][0]["source"], "operator-reviewed-live")

    def test_adoption_requires_targets_and_digests(self) -> None:
        with self.assertRaisesRegex(ValueError, "ADOPTION_REQUIRES_EXPLICIT_TARGETS"):
            self.module.asset_baseline.adoption_candidates(
                reviewed={}, live_digests={SKILL_ROOT_REL: "x" * 16}, state={}
            )
        with self.assertRaisesRegex(RuntimeError, "ADOPTION_REFUSED"):
            self.adopt({SKILL_ROOT_REL: "short"})

    def test_adoption_refuses_when_content_changed_since_review(self) -> None:
        self.fixture.write_live(SKILL_MD_REL, "# alpha v0 native\n")
        reviewed = self.live_digest(SKILL_ROOT_REL)
        self.fixture.write_live(SKILL_MD_REL, "# alpha v0 native\n\nchanged after review\n")
        with self.assertRaisesRegex(RuntimeError, "ADOPTION_REFUSED"):
            self.adopt({SKILL_ROOT_REL: reviewed})
        self.assertFalse(self.module.asset_baseline.state_path(self.fixture.home).exists())

    def test_adoption_refuses_unknown_targets(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "unknown managed target"):
            self.adopt({"skills/not-managed": "a" * 64})

    def test_adoption_does_not_write_asset_content_or_backups(self) -> None:
        self.fixture.write_live(SKILL_MD_REL, "# alpha v0 native\n")
        before = {p: self.fixture.live_bytes(p) for p in [SKILL_MD_REL, BIN_REL] if self.fixture.live(p).is_file()}
        self.adopt({SKILL_ROOT_REL: self.live_digest(SKILL_ROOT_REL)})
        for rel, content in before.items():
            self.assertEqual(self.fixture.live_bytes(rel), content)
        self.assertFalse((self.fixture.home / "backups").exists(), "adoption must not stage or back up")
        self.assertFalse(list(self.fixture.home.glob(".wa-stg-*")), "adoption must not create staging")

    def test_publish_still_refuses_unadopted_targets(self) -> None:
        """Adopting one target must not implicitly trust the others."""
        self.fixture.write_live(SKILL_MD_REL, "# alpha v0 native\n")
        self.fixture.write_live(BIN_REL, "native-bin\n")
        self.adopt({SKILL_ROOT_REL: self.live_digest(SKILL_ROOT_REL)})
        self.assertEqual(self.verdicts()[BIN_REL], "NO_BASELINE")
        with self.assertRaisesRegex(RuntimeError, "MANAGED_ASSET_LIVE_CHANGE_REFUSED"):
            self.publish()

    # ===================================================================== #
    # R6 - diagnosable commit, baseline never advanced on failure
    # ===================================================================== #
    def test_pending_marker_blocks_a_new_apply(self) -> None:
        self.publish()
        self.module.asset_baseline.write_pending(
            self.fixture.home, run_id="run-x", phase="replaced", records={SKILL_ROOT_REL: {"candidate_sha256": "z"}}
        )
        self.assertIn("MANAGED_ASSET_RUN_INCOMPLETE", self.module.asset_baseline.pending_diagnosis(self.fixture.home))
        with self.assertRaisesRegex(RuntimeError, "MANAGED_ASSET_RUN_INCOMPLETE"):
            self.publish()
        self.module.asset_baseline.clear_pending(self.fixture.home)
        self.assertIsNone(self.module.asset_baseline.pending_diagnosis(self.fixture.home))

    def test_pending_marker_cleared_after_a_successful_publish(self) -> None:
        self.publish()
        self.assertIsNone(self.module.asset_baseline.pending_diagnosis(self.fixture.home))
        state = self.module.asset_baseline.load_state(self.fixture.home)
        self.assertTrue(state.get("run_id"), "the baseline must record which run produced it")

    def test_refused_run_leaves_the_baseline_untouched(self) -> None:
        self.publish()
        state_path = self.module.asset_baseline.state_path(self.fixture.home)
        before = state_path.read_text(encoding="utf-8")
        self.fixture.write_live(SKILL_MD_REL, "# alpha v1\n\nnative edit\n")
        with self.assertRaises(RuntimeError):
            self.publish()
        self.assertEqual(state_path.read_text(encoding="utf-8"), before)

    def test_candidate_changing_mid_run_is_refused_and_baseline_not_advanced(self) -> None:
        """H3: the readback must compare against the FROZEN plan digest.

        With a re-read of the repository source, a candidate that changed after
        planning would certify itself and the baseline would advance to content
        nobody reviewed.
        """
        self.publish()
        self.fixture.bump_candidate()
        original = self.module.prepare_staging

        def racing_prepare_staging(repo, home, managed_roots, managed_binaries, managed_file_mappings, include_config=False):
            (repo / "packages/client-neutral-core/skills/demo/alpha/SKILL.md").write_text(
                "# alpha v3 (changed after planning)\n", encoding="utf-8"
            )
            return original(
                repo, home, managed_roots, managed_binaries, managed_file_mappings, include_config=include_config
            )

        state_path = self.module.asset_baseline.state_path(self.fixture.home)
        before = state_path.read_text(encoding="utf-8")
        with mock.patch.object(self.module, "prepare_staging", racing_prepare_staging):
            with self.assertRaisesRegex(RuntimeError, "MANAGED_ASSET_READBACK_FAIL"):
                self.publish()
        self.assertEqual(state_path.read_text(encoding="utf-8"), before,
                         "a readback failure must not advance the baseline")

    # ===================================================================== #
    # unchanged behaviour that must keep working
    # ===================================================================== #
    def test_suspension_preserves_the_target(self) -> None:
        self.publish()
        self.fixture.write_live(SKILL_MD_REL, "# alpha v1\n\nsuspended-area edit\n")
        self.assertEqual(self.verdicts(suspended=[SKILL_ROOT_REL])[SKILL_ROOT_REL], "SUSPENDED")
        self.publish(suspended=[SKILL_ROOT_REL])
        self.assertIn(b"suspended-area edit", self.fixture.live_bytes(SKILL_MD_REL))

    def test_plan_reports_guard_verdicts_and_write_set(self) -> None:
        self.fixture.write_live(SKILL_MD_REL, "# alpha v0 native\n")
        plan = self.module.build_action_plan(self.fixture.repo, self.fixture.home)
        guard = plan["guard"]
        self.assertEqual(guard["refusing"][0]["target"], SKILL_ROOT_REL)
        # the unproven skill root is not written; the not-yet-installed targets are
        self.assertNotIn(SKILL_ROOT_REL, guard["will_write"])
        self.assertEqual(guard["will_write"], [".env.template", "SOUL.md", BIN_REL])
        self.assertIn("pending_file", guard)

    def test_action_plan_readback_matches_published_state(self) -> None:
        plan = self.module.build_action_plan(self.fixture.repo, self.fixture.home)
        self.publish()
        self.module.verify_action_plan_readback(plan, self.fixture.repo, self.fixture.home)


if __name__ == "__main__":
    unittest.main()
