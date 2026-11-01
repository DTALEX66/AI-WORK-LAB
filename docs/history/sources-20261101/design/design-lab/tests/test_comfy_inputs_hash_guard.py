# SPDX-License-Identifier: MIT
"""ComfyTask must refuse an inputs_hash that hashed nothing.

Lives apart from test_comfy_task_protocol.py because that file is the named
artefact of a ledger evidence record; editing it would leave the record's stored
hash pointing at bytes the run it documents never observed.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC))


class ComfyInputsHashGuardTests(unittest.TestCase):
    def _pin(self):
        from design_lab.generators.comfy_task import PinnedNode, WorkflowPin

        return WorkflowPin(
            "txt2img-minimal",
            nodes=(PinnedNode("ckpt", "CheckpointLoaderSimple", "v1.5",
                              "sha256:" + "1" * 64),),
        )

    def test_zero_inputs_hash_is_refused(self):
        from design_lab.generators.comfy_task import ComfyTask, ComfyTaskError

        with self.assertRaises(ComfyTaskError):
            ComfyTask("t1", self._pin(), "sha256:" + "0" * 64).validate()

    def test_a_hashed_input_still_validates(self):
        from design_lab.generators.comfy_task import ComfyTask

        ComfyTask("t1", self._pin(), "sha256:" + "2" * 64).validate()


if __name__ == '__main__':
    unittest.main()
