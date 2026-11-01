# SPDX-License-Identifier: MIT
"""DL-TP-T09 (MULTIMODAL-2026-09-05): ComfyUI task protocol structural tests.

Verifies pinned workflow fingerprints, state machine honesty (cache hits are
never 'new generation success', FAILED/CANCELLED are not completed), and input
binding. No live ComfyUI required.
"""
from __future__ import annotations

import unittest
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC))


class ComfyTaskProtocolTests(unittest.TestCase):
    def test_fingerprint_cannot_bypass_pin_validation(self):
        from design_lab.generators.comfy_task import WorkflowPin, PinnedNode, ComfyTaskError
        invalid = (
            WorkflowPin('../invalid'),
            WorkflowPin('w1', schema_version='unknown'),
            WorkflowPin('w1', nodes=(PinnedNode('n1', 'Model', '1', 'sha256:'+'0'*64),)),
            WorkflowPin('w1', nodes=(PinnedNode('n1', 'Model', '1', 'sha256:'+'a'*64),
                                     PinnedNode('n1', 'Model', '2', 'sha256:'+'b'*64))),
        )
        for pin in invalid:
            with self.subTest(pin=pin), self.assertRaises(ComfyTaskError):
                pin.fingerprint()

    def test_result_rejects_unsafe_artifact_paths(self):
        from design_lab.generators.comfy_task import TaskResult, ComfyTaskError
        for path in ('../escape.png', '/absolute.png', 'C:/out.png', 'C:out.png',
                     'a/../b.png', 'a\\b.png', '', 'a//b.png', 'a/./b.png'):
            with self.subTest(path=path), self.assertRaises(ComfyTaskError):
                TaskResult('t1', 'SUCCEEDED', (path,), 'sha256:'+'a'*64).validate()
        TaskResult('t1', 'SUCCEEDED', ('.project-local/output/a.png',), 'sha256:'+'a'*64).validate()

    def test_result_rejects_fake_or_zero_fingerprint(self):
        from design_lab.generators.comfy_task import TaskResult, ComfyTaskError
        for state in ('SUCCEEDED', 'CACHE_HIT'):
            for value in ('fake', '', 'sha256:'+'0'*64):
                with self.subTest(state=state, value=value), self.assertRaises(ComfyTaskError):
                    TaskResult('t1', state, ('out.png',), value).validate()

    def test_pin_rejects_zero_checksum_and_duplicate_identity(self):
        from design_lab.generators.comfy_task import WorkflowPin, PinnedNode, ComfyTaskError
        for nodes in ((PinnedNode('n1', 'Model', '1', 'sha256:'+'0'*64),),
                      (PinnedNode('n1', 'Model', '1', 'sha256:'+'a'*64),
                       PinnedNode('n1', 'Model', '2', 'sha256:'+'b'*64))):
            with self.subTest(nodes=nodes), self.assertRaises(ComfyTaskError):
                WorkflowPin('w1', nodes=nodes).validate()

    def _pin(self, model_hash: str = "sha256:" + "1" * 64) -> dict:
        from design_lab.generators.comfy_task import PinnedNode, WorkflowPin

        return WorkflowPin(
            "txt2img-minimal",
            nodes=(PinnedNode("ckpt", "CheckpointLoaderSimple", "v1.5", model_hash),),
        )

    def test_workflow_fingerprint_is_stable_and_order_independent(self):
        from design_lab.generators.comfy_task import PinnedNode, WorkflowPin

        a = WorkflowPin(
            "w1",
            nodes=(PinnedNode("n1", "KSampler", "1", "sha256:" + "a" * 64),
                   PinnedNode("n2", "VAEDecode", "2", "sha256:" + "b" * 64)),
        )
        b = WorkflowPin(
            "w1",
            nodes=(PinnedNode("n2", "VAEDecode", "2", "sha256:" + "b" * 64),
                   PinnedNode("n1", "KSampler", "1", "sha256:" + "a" * 64)),
        )
        self.assertEqual(a.fingerprint(), b.fingerprint())
        self.assertTrue(a.fingerprint().startswith("sha256:"))

    def test_pin_rejects_missing_version_or_bad_hash(self):
        from design_lab.generators.comfy_task import ComfyTaskError, PinnedNode, WorkflowPin

        for nodes in (
            (PinnedNode("n1", "KSampler", "", "sha256:" + "a" * 64),),
            (PinnedNode("n1", "KSampler", "1", "md5:abc"),),
        ):
            with self.assertRaises(ComfyTaskError):
                WorkflowPin("w1", nodes=nodes).validate()

    def test_succeeded_requires_artifacts_and_fingerprint(self):
        from design_lab.generators.comfy_task import ComfyTaskError, TaskResult

        with self.assertRaises(ComfyTaskError):
            TaskResult("t1", "SUCCEEDED").validate()
        with self.assertRaises(ComfyTaskError):
            TaskResult("t1", "SUCCEEDED", artifacts=("out.png",)).validate()

    def test_cache_hit_is_not_new_generation(self):
        from design_lab.generators.comfy_task import TaskResult, classify_result

        r = TaskResult("t1", "CACHE_HIT", artifacts=("out.png",),
                       workflow_fingerprint="sha256:" + "a" * 64)
        r.validate()
        self.assertIn("NOT a new generation", classify_result("CACHE_HIT"))
        self.assertNotIn("succeeded", classify_result("CACHE_HIT").lower())

    def test_failed_and_cancelled_are_never_completed(self):
        from design_lab.generators.comfy_task import ComfyTaskError, TaskResult, classify_result

        with self.assertRaises(ComfyTaskError):
            TaskResult("t1", "FAILED").validate()  # missing reason
        ok = TaskResult("t1", "FAILED", note="ckpt missing")
        ok.validate()
        self.assertIn("failed", classify_result("FAILED").lower())
        TaskResult("t1", "CANCELLED").validate()
        self.assertIn("cancelled", classify_result("CANCELLED").lower())

    def test_input_hash_binding(self):
        from design_lab.generators.comfy_task import ComfyTask, ComfyTaskError

        t = ComfyTask("t1", self._pin(), "sha256:" + "2" * 64)
        t.validate()
        with self.assertRaises(ComfyTaskError):
            ComfyTask("t1", self._pin(), "not-a-hash").validate()


class TaskStateMachineTests(unittest.TestCase):
    def test_happy_path_queue_to_success(self):
        from design_lab.generators.comfy_task import TaskStateMachine

        m = TaskStateMachine()
        self.assertEqual(m.transition("RUNNING"), "RUNNING")
        self.assertEqual(m.transition("SUCCEEDED"), "SUCCEEDED")
        self.assertTrue(m.is_terminal)

    def test_terminal_cannot_transition_again(self):
        from design_lab.generators.comfy_task import ComfyTaskError, TaskStateMachine

        m = TaskStateMachine()
        m.transition("RUNNING")
        m.transition("FAILED")
        with self.assertRaises(ComfyTaskError):
            m.transition("SUCCEEDED")  # no silent reset from FAILED

    def test_cancel_is_explicit_and_terminal(self):
        from design_lab.generators.comfy_task import ComfyTaskError, TaskStateMachine

        m = TaskStateMachine()
        m.transition("RUNNING")
        self.assertEqual(m.cancel(), "CANCELLED")
        with self.assertRaises(ComfyTaskError):
            m.transition("RUNNING")

    def test_skip_queue_to_success_rejected(self):
        from design_lab.generators.comfy_task import ComfyTaskError, TaskStateMachine

        m = TaskStateMachine()
        with self.assertRaises(ComfyTaskError):
            m.transition("SUCCEEDED")  # QUEUED -> SUCCEEDED without RUNNING

    def test_cache_hit_is_not_a_success_transition(self):
        from design_lab.generators.comfy_task import ComfyTaskError, TaskStateMachine

        m = TaskStateMachine()
        m.transition("RUNNING")
        with self.assertRaises(ComfyTaskError):
            m.transition("CACHE_HIT")  # must be assigned by classifier, never a success edge


if __name__ == "__main__":
    unittest.main()
