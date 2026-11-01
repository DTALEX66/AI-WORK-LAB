from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "workflow"))
from build_context_pack import build_context_pack  # noqa: E402
from context_lines import ContextLineError, normalize_context_lines, render_context_lines  # noqa: E402


class ContextLineTests(unittest.TestCase):
    def line(self, *, line_id: str, decision: str, project_id: str = "work-lab") -> dict:
        return {
            "line_id": line_id,
            "project_id": project_id,
            "source_digest": "a" * 64,
            "status": "observed",
            "goal": "improve workflow",
            "current_state": "local",
            "decisions": decision,
            "constraints": "offline",
            "evidence_refs": [".hermes/task-artifacts/evidence.json"],
            "blockers": [],
            "next_action": "run tests",
        }

    def test_normalization_is_idempotent_and_deduplicates(self) -> None:
        raw = [self.line(line_id="old", decision="keep"), self.line(line_id="old", decision="keep")]
        first = normalize_context_lines(raw, project_id="work-lab")
        second = normalize_context_lines(first, project_id="work-lab")
        self.assertEqual(first, second)
        self.assertEqual(len(first), 1)

    def test_new_decision_supersedes_old_and_stale_is_not_injected(self) -> None:
        old = self.line(line_id="old", decision="use-old")
        new = self.line(line_id="new", decision="use-new")
        new["status"] = "approved"
        new["supersedes"] = ["old"]
        stale = self.line(line_id="stale", decision="old-price")
        stale["freshness"] = "stale"
        result = normalize_context_lines([old, new, stale], project_id="work-lab")
        self.assertEqual([item["line_id"] for item in result], ["new"])
        self.assertEqual(render_context_lines(result).count("use-new"), 1)
        self.assertNotIn("old-price", render_context_lines(result))

    def test_cross_project_and_unknown_or_sensitive_fields_fail_closed(self) -> None:
        with self.assertRaises(ContextLineError):
            normalize_context_lines([self.line(line_id="foreign", decision="x", project_id="other")], project_id="work-lab")
        unknown = self.line(line_id="unknown", decision="x")
        unknown["prompt"] = "body"
        with self.assertRaises(ContextLineError):
            normalize_context_lines([unknown], project_id="work-lab")
        unknown = self.line(line_id="unknown", decision="x")
        unknown["unexpected"] = "value"
        with self.assertRaises(ContextLineError):
            normalize_context_lines([unknown], project_id="work-lab")

    def test_context_lines_are_rendered_into_the_existing_pack_api(self) -> None:
        line = self.line(line_id="pack-line", decision="pack-decision")
        rendered = build_context_pack(Path(__file__).resolve().parents[2], max_chars=30000, context_lines=[line], context_project_id="work-lab")
        self.assertIn("## Context Lines", rendered)
        self.assertIn("pack-decision", rendered)


if __name__ == "__main__":
    unittest.main()
