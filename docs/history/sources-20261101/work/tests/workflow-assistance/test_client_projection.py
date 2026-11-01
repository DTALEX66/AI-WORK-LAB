"""Contract tests for client projection (WL3-700 / MR-15).

Covers six neutral adapters, graceful unavailable, no hard-coded install
paths/versions/ports/model names, layer precedence.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/workflow"))

from client_projection import ClientProjection, precedence_label


class ClientProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.proj = ClientProjection()

    def test_hermes_never_switches_global_provider(self) -> None:
        result = self.proj.project("hermes", "code.read")
        self.assertEqual(result["global_provider_switch"],
                         "forbidden_without_explicit_user_action")

    def test_codex_task_contract(self) -> None:
        result = self.proj.project("codex", "code.write", data_privacy="private")
        self.assertEqual(result["kind"], "task_contract")
        self.assertEqual(result["data_privacy"], "private")
        self.assertEqual(result["sandbox"], "workspace-write")

    def test_cc_switch_never_task_routing(self) -> None:
        result = self.proj.project("cc-switch", "anything")
        self.assertEqual(result["task_routing"], "never")
        self.assertEqual(result["profile_apply"], "none")

    def test_cc_switch_approved_profile_only(self) -> None:
        proj = ClientProjection({"cc-switch": {"available": True, "overlay_approved": True}})
        result = proj.project("cc-switch", "profile")
        self.assertEqual(result["profile_apply"], "approved_only")

    def test_github_unapproved_requires_approval(self) -> None:
        result = self.proj.project("github", "repo.delete")
        self.assertEqual(result["status"], "APPROVAL_REQUIRED")

    def test_github_approved_op(self) -> None:
        result = self.proj.project("github", "pr.read")
        self.assertEqual(result["kind"], "approved_github_op")

    def test_open_design_observe_only(self) -> None:
        result = self.proj.project("open-design", "capability")
        self.assertFalse(result["apply_supported"])
        self.assertTrue(result["observe_only"])

    def test_openhuman_observe_only(self) -> None:
        result = self.proj.project("openhuman", "capability")
        self.assertFalse(result["apply_supported"])

    def test_unknown_client(self) -> None:
        result = self.proj.project("bogus-client", "x")
        self.assertEqual(result["status"], "UNKNOWN_CLIENT")

    def test_missing_client_graceful_unavailable(self) -> None:
        proj = ClientProjection({"hermes": {"available": False}})
        result = proj.project("hermes", "x")
        self.assertEqual(result["status"], "UNAVAILABLE")

    def test_no_hardcoded_paths_or_models(self) -> None:
        import json
        all_projs = [self.proj.project(c, "test") for c in
                     ("hermes", "codex", "cc-switch", "github", "openhuman", "open-design")]
        serialized = json.dumps(all_projs, ensure_ascii=False)
        for banned in ("C:/", "D:/", ":11434", ":8080", "qwen", "gpt-", "0.0.0.0"):
            self.assertNotIn(banned, serialized, banned)

    def test_precedence_order(self) -> None:
        self.assertEqual(precedence_label(["global", "task", "project"]),
                         "global -> project -> task")


if __name__ == "__main__":
    unittest.main()
