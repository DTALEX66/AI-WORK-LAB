from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "packages/client-neutral-core/scripts" / "platform_identity.py"
SCHEMA = ROOT / "packages" / "contracts" / "schemas" / "workflow" / "platform-identity.schema.json"
spec = importlib.util.spec_from_file_location("platform_identity", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def observation(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "schema_version": "workflow/platform-identity/v1",
        "platform_id": "codex",
        "logical_instance_id": "codex-main",
        "package_identity": "com.openai.codex",
        "publisher": "OpenAI",
        "install_channel": "official-installer",
        "executable_realpath": "C:/Program Files/Codex/codex.exe",
        "binary_digest": hashlib.sha256(b"codex").hexdigest(),
        "discovered_version": "1.0.0",
        "launcher_id": "start-menu-codex",
        "launcher_target": "C:/Program Files/Codex/codex.exe",
        "arguments": [],
        "working_directory": "C:/Users/ALEX",
        "effective_config_root": "C:/Users/ALEX/.codex",
        "profile_id": "default",
        "user_context": "current-user",
        "capabilities": ["observe", "plan"],
        "evidence_source": ["path", "launcher"],
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "freshness": "CURRENT",
        "state": "UNIQUE",
    }
    base.update(overrides)
    return base


class PlatformIdentityTests(unittest.TestCase):
    def test_schema_is_valid_and_contains_required_identity_fields(self) -> None:
        data = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(data["properties"]["schema_version"]["const"], "workflow/platform-identity/v1")
        self.assertTrue(set(data["required"]).issuperset({"logical_instance_id", "effective_config_root", "state"}))

    def test_same_target_with_two_launchers_is_alias_duplicate(self) -> None:
        result = module.resolve_identity([observation(launcher_id="start"), observation(launcher_id="taskbar", launcher_target="C:/Program Files/Codex/codex.exe")])
        self.assertEqual(result["identities"][0]["state"], "ALIAS_DUPLICATE")
        self.assertEqual(result["identities"][0]["observation_count"], 2)

    def test_same_binary_with_two_config_roots_fails_closed(self) -> None:
        result = module.resolve_identity([observation(), observation(launcher_id="cli", effective_config_root="C:/Users/ALEX/.codex-alt")])
        self.assertEqual(result["identities"][0]["state"], "CONFIG_SPLIT")
        self.assertEqual(result["ambiguous_count"], 1)

    def test_different_binary_digests_are_dual_installation(self) -> None:
        result = module.resolve_identity([observation(), observation(launcher_id="portable", binary_digest=hashlib.sha256(b"other").hexdigest(), executable_realpath="D:/Tools/codex.exe")])
        self.assertEqual(result["identities"][0]["state"], "DUAL_INSTALLATION")

    def test_empty_discovery_is_not_unique(self) -> None:
        result = module.resolve_identity([])
        self.assertEqual(result["identity_count"], 0)
        self.assertEqual(result["ambiguous_count"], 0)


if __name__ == "__main__":
    unittest.main()
