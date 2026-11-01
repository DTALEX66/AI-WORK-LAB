from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "packages/client-neutral-core/scripts/skill_lifecycle.py"
spec = importlib.util.spec_from_file_location("skill_lifecycle", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

AGENT_MD = "---\nname: my-skill\ndescription: 'Short description.'\ncreated_by: agent\n---\n\n# My skill\n"
REPO_MD = "---\nname: repo-skill\ndescription: 'Short description.'\n---\n\n# Repo skill\n"


def make_skill(root: Path, name: str, content: str = AGENT_MD) -> Path:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(content, encoding="utf-8")
    return d


def old_activity(days: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.isoformat(timespec="seconds")


class SkillLifecycleTests(unittest.TestCase):
    def test_provenance_filter_only_manages_agent_created(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            make_skill(root, "managed", AGENT_MD)
            make_skill(root, "repo-owned", REPO_MD)
            self.assertTrue(module._is_agent_created(root / "managed"))
            self.assertFalse(module._is_agent_created(root / "repo-owned"))

    def test_record_bumps_counters_and_activity(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            make_skill(root, "managed", AGENT_MD)
            module._record(root, "managed", "use")
            module._record(root, "managed", "patch")
            usage = module._load_usage(root)
            self.assertEqual(usage["managed"]["use_count"], 1)
            self.assertEqual(usage["managed"]["patch_count"], 1)
            self.assertTrue(usage["managed"]["last_activity_at"])

    def test_stale_then_archive_transitions_with_backup(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            make_skill(root, "aged", AGENT_MD)
            module._record(root, "aged", "use")
            usage = module._load_usage(root)
            usage["aged"]["last_activity_at"] = old_activity(120)  # > 90d archive
            module._atomic_write_usage(root, usage)

            results = module._apply_transitions(root)

            self.assertTrue(any("ARCHIVED aged" in r for r in results))
            self.assertFalse((root / "aged").exists())
            self.assertTrue((root / ".archive" / "aged" / "SKILL.md").is_file())
            self.assertTrue(list((root / ".backups").glob("aged-*")))
            self.assertEqual(module._load_usage(root)["aged"]["state"], "archived")

    def test_pinned_skill_bypasses_transitions(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            make_skill(root, "pinned-skill", AGENT_MD)
            module._set_pinned(root, "pinned-skill", True)
            usage = module._load_usage(root)
            usage["pinned-skill"]["last_activity_at"] = old_activity(200)
            module._atomic_write_usage(root, usage)

            results = module._apply_transitions(root)

            self.assertTrue((root / "pinned-skill").exists())
            self.assertFalse(any("ARCHIVED pinned-skill" in r for r in results))

    def test_archive_restore_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            make_skill(root, "cycler", AGENT_MD)
            self.assertIn("ARCHIVED cycler", module._archive(root, "cycler"))
            self.assertFalse((root / "cycler").exists())
            self.assertIn("RESTORED cycler", module._restore(root, "cycler"))
            self.assertTrue((root / "cycler" / "SKILL.md").is_file())
            self.assertEqual(module._load_usage(root)["cycler"]["state"], "active")

    def test_non_managed_skill_refuses_archive(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            make_skill(root, "repo-owned", REPO_MD)
            result = module._archive(root, "repo-owned")
            self.assertIn("NOT_MANAGED", result)
            self.assertTrue((root / "repo-owned" / "SKILL.md").is_file())

    def test_dry_run_archives_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            make_skill(root, "aged", AGENT_MD)
            module._record(root, "aged", "use")
            usage = module._load_usage(root)
            usage["aged"]["last_activity_at"] = old_activity(200)
            module._atomic_write_usage(root, usage)

            results = module._apply_transitions(root, dry_run=True)

            self.assertTrue(any("WOULD_ARCHIVE aged" in r for r in results))
            self.assertTrue((root / "aged").exists())

    def test_usage_sidecar_is_valid_json_after_operations(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            make_skill(root, "managed", AGENT_MD)
            module._record(root, "managed", "view")
            module._archive(root, "managed")
            module._restore(root, "managed")
            parsed = json.loads((root / ".usage.json").read_text(encoding="utf-8"))
            self.assertEqual(parsed["managed"]["state"], "active")


if __name__ == "__main__":
    unittest.main()
