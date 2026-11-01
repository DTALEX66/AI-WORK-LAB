from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "integrations/executors/hermes" / "sync_hermes_workflow_assets.py"


def load_module():
    spec = importlib.util.spec_from_file_location("workflow_sync_backups", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WorkflowSyncBackupRetentionTests(unittest.TestCase):
    def test_prunes_only_superseded_workflow_sync_directories(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            backups = home / "backups"
            names = [
                "workflow-assistance-sync-20260701-000000-000000",
                "workflow-assistance-sync-20260702-000000-000000",
                "workflow-assistance-sync-20260703-000000-000000",
            ]
            for name in names:
                (backups / name).mkdir(parents=True)
            unrelated = backups / "pre-update-2026-07-01.zip"
            unrelated.write_text("retain", encoding="utf-8")

            removed = module.prune_workflow_sync_backups(home, apply=True, keep=2)

            self.assertEqual(removed, 1)
            self.assertFalse((backups / names[0]).exists())
            self.assertTrue((backups / names[1]).is_dir())
            self.assertTrue((backups / names[2]).is_dir())
            self.assertTrue(unrelated.is_file())

    def test_refuses_zero_backup_retention(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            with self.assertRaisesRegex(ValueError, "at least one"):
                module.prune_workflow_sync_backups(Path(raw), apply=True, keep=0)


if __name__ == "__main__":
    unittest.main()
