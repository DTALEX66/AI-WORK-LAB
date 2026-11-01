from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "packages/client-neutral-core/scripts/user_profile_export.py"
spec = importlib.util.spec_from_file_location("user_profile_export", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class UserProfileExportTests(unittest.TestCase):
    def test_profile_contains_only_portable_manage_allowlist(self) -> None:
        profile = module.build_profile(
            hermes_preferences={
                "display": {"busy_input_mode": "queue", "language": "zh", "theme": "dark"},
                "model": {"provider": "private-provider"},
                "sessions": {"raw": "forbidden"},
            },
            codex_preferences={
                "approval_policy": "on-request",
                "sandbox_mode": "workspace-write",
                "project_doc_max_bytes": 65536,
                "model": "private-model",
            },
        )
        payload = json.dumps(profile, ensure_ascii=False)
        self.assertEqual(profile["schema_version"], "worklab/user-environment-profile/v2")
        self.assertEqual(profile["profile_mode"], "USER_OVERLAY_ONLY")
        self.assertFalse(profile["discovery"]["absolute_paths_persisted"])
        self.assertEqual(profile["discovery"]["runtime_roots"], "CAPABILITY_DISCOVERY")
        self.assertEqual(profile["hermes"]["preferences"]["display.language"], "zh")
        self.assertNotIn("private-provider", payload)
        self.assertNotIn("private-model", payload)
        self.assertNotIn("sessions", profile)
        self.assertNotIn("generated_at", profile)

    def test_cli_is_plan_only_without_write(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".hermes" / "task-runtime") as raw:
            output = Path(raw) / "profile.json"
            output.write_text("sentinel\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--output", str(output)],
                cwd=ROOT,
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(output.read_text(encoding="utf-8"), "sentinel\n")
            self.assertIn("PLAN_ONLY", result.stdout)

    def test_cli_writes_only_with_explicit_flag(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".hermes" / "task-runtime") as raw:
            output = Path(raw) / "profile.json"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--output", str(output), "--write"],
                cwd=ROOT,
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8"))["schema_version"],
                "worklab/user-environment-profile/v2",
            )


if __name__ == "__main__":
    unittest.main()
