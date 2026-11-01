# SPDX-License-Identifier: MIT
"""DL-V2 P1-A: design kernel tests (state machine + command validation)."""
from __future__ import annotations

import unittest

import importlib.util
from pathlib import Path

_CORE = Path(__file__).resolve().parents[1] / "core"

def _load(name):
    import sys
    p = _CORE / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"dl_core_{name}", p)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m

_ps = _load("project_state")
_cm = _load("commands")
DesignProject, ProjectTransitionError = _ps.DesignProject, _ps.ProjectTransitionError
STAGES, TRANSITIONS = _ps.STAGES, _ps.TRANSITIONS
validate_command, is_tool_name = _cm.validate_command, _cm.is_tool_name


class DesignProjectStateTests(unittest.TestCase):
    def test_initial_state(self):
        p = DesignProject(project_id="DL-TEST-001", domain="brand.identity", user_mode="director")
        self.assertEqual(p.stage, "draft")
        self.assertEqual(p.validate(), [])

    def test_valid_chain(self):
        p = DesignProject(project_id="DL-TEST-002")
        chain = ["research", "direction", "system", "variant", "critique", "revision", "critique", "approved", "render", "preflight", "packaged", "delivered", "archived"]
        for s in chain:
            p.transition(s, f"step {s}")
        self.assertEqual(p.stage, "archived")
        self.assertEqual(len(p.history), len(chain))

    def test_invalid_transition_rejected(self):
        p = DesignProject(project_id="DL-TEST-003")
        with self.assertRaises(ProjectTransitionError):
            p.transition("archived", "skip")  # draft -> archived not allowed

    def test_revision_increments_on_attach(self):
        p = DesignProject(project_id="DL-TEST-004")
        p.attach("brief", "obj://brief-1")
        self.assertEqual(p.revision, 2)


class DesignCommandTests(unittest.TestCase):
    def test_valid_command(self):
        errs = validate_command({
            "command_id": "cmd-1", "schemaVersion": "design-lab/design-command/v1",
            "capability": "image.layer.mask", "document": "artifact://master",
            "args": {"target": "layer://product", "mode": "non_destructive"}, "project_id": "DL-TEST-005",
        })
        self.assertEqual(errs, [])

    def test_unknown_capability_rejected(self):
        errs = validate_command({
            "command_id": "cmd-2", "schemaVersion": "design-lab/design-command/v1",
            "capability": "photoshop.execute", "document": "artifact://x", "project_id": "p",
        })
        self.assertTrue(any("unknown capability" in e for e in errs))

    def test_tool_name_rejected(self):
        self.assertTrue(is_tool_name("photoshop.text"))
        self.assertFalse(is_tool_name("image.text.create"))


if __name__ == "__main__":
    unittest.main()


class UserModeTests(unittest.TestCase):
    def test_all_modes_valid(self):
        import sys
        p = _CORE / "user_modes.py"
        spec = importlib.util.spec_from_file_location("dl_core_user_modes_test", p)
        m = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = m
        spec.loader.exec_module(m)
        for mode in ("guided", "copilot", "director", "method", "production"):
            self.assertIsNotNone(m.mode_semantics(mode))

    def test_guided_requires_direction_approval(self):
        import sys
        p = _CORE / "user_modes.py"
        spec = importlib.util.spec_from_file_location("dl_core_user_modes_test2", p)
        m = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = m
        spec.loader.exec_module(m)
        self.assertTrue(m.requires_human_approval("guided", "direction"))
        self.assertFalse(m.requires_human_approval("production", "direction"))

    def test_quality_gate_auto(self):
        import sys
        p = _CORE / "user_modes.py"
        spec = importlib.util.spec_from_file_location("dl_core_user_modes_test3", p)
        m = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = m
        spec.loader.exec_module(m)
        self.assertTrue(m.quality_gate_auto("director"))
        self.assertFalse(m.quality_gate_auto("guided"))
