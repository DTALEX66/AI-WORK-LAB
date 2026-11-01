"""WLOSS-500 tests: canonical skill neutralization + three-way export."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from canonical_skill import (
    CanonicalSkill,
    export_agent_skills,
    export_codex,
    export_hermes,
    parse_hermes_skill_md,
)


def sample_skill() -> CanonicalSkill:
    return CanonicalSkill(
        identity="project-data-boundary",
        purpose="Keep task data inside the current Git project.",
        trigger_hints=["temp files", "cache", "logs", "artifacts"],
        required_inputs=["git root"],
        forbidden_actions=["write to %TEMP%", "write to user home"],
        allowed_tools=["terminal"],
        evidence_contract="All evidence is verifiable; no fabricated results.",
        tests=["test_project_data_boundary"],
        adapters={"hermes": "SKILL.md", "codex": "codex skill", "agent-skills": "open format"},
    )


class CanonicalSkillTests(unittest.TestCase):
    def test_roundtrip_dict(self) -> None:
        skill = sample_skill()
        rebuilt = CanonicalSkill.from_dict(skill.to_dict())
        self.assertEqual(rebuilt.identity, skill.identity)
        self.assertEqual(rebuilt.purpose, skill.purpose)
        self.assertEqual(rebuilt.trigger_hints, skill.trigger_hints)
        self.assertEqual(rebuilt.digest(), skill.digest())

    def test_validate(self) -> None:
        self.assertEqual(sample_skill().validate(), [])
        bad = CanonicalSkill(identity="Bad Name!", purpose="", evidence_contract="")
        errors = bad.validate()
        self.assertTrue(any("identity" in e for e in errors))
        self.assertTrue(any("purpose" in e for e in errors))
        self.assertTrue(any("evidence_contract" in e for e in errors))

    def test_export_hermes_frontmatter(self) -> None:
        md = export_hermes(sample_skill())
        self.assertIn("name: project-data-boundary", md)
        self.assertIn("description:", md)
        self.assertIn("metadata:", md)
        self.assertIn("## Evidence contract", md)

    def test_export_codex(self) -> None:
        md = export_codex(sample_skill())
        self.assertIn("name: project-data-boundary", md)
        self.assertIn("platforms:", md)
        self.assertIn("Forbidden actions", md)

    def test_export_agent_skills(self) -> None:
        md = export_agent_skills(sample_skill())
        self.assertIn("agent-skills: v1", md)
        self.assertIn("Trigger hints", md)

    def test_parse_existing_hermes_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo-skill" / "SKILL.md"
            path.parent.mkdir()
            path.write_text(
                "---\nname: demo-skill\ndescription: \"Demo purpose\"\nversion: 1.2.0\nlicense: MIT\n---\n\n# Demo\n\nBody text.\n",
                encoding="utf-8",
            )
            skill = parse_hermes_skill_md(path)
            self.assertEqual(skill.identity, "demo-skill")
            self.assertEqual(skill.version, "1.2.0")
            self.assertEqual(skill.purpose, "Demo purpose")

    def test_exports_share_canonical_content(self) -> None:
        skill = sample_skill()
        for md in (export_hermes(skill), export_codex(skill), export_agent_skills(skill)):
            self.assertIn(skill.evidence_contract, md)


if __name__ == "__main__":
    unittest.main()
