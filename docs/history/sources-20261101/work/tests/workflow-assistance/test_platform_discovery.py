"""WL3-710: platform discovery covers cc-switch and the Hermes GUI launcher."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]


def load_discovery():
    scripts = ROOT / "packages" / "client-neutral-core" / "scripts"
    sys.path.insert(0, str(scripts))
    path = scripts / "platform_discovery.py"
    spec = importlib.util.spec_from_file_location("platform_discovery", path)
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load platform_discovery")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PlatformDiscoveryTests(unittest.TestCase):
    def test_cc_switch_config_root_discovered(self):
        module = load_discovery()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "config.yaml").write_text("providers: []\n", encoding="utf-8")
            with mock.patch.dict("os.environ", {"CC_SWITCH_HOME": str(root)}), mock.patch.object(module, "_running_processes", return_value=set()):
                entries = module.discover_cc_switch()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].logical_instance_id, "cc-switch")
        self.assertEqual(entries[0].source, "config-root")
        self.assertEqual(entries[0].effective_config_root, str(root))

    def test_cc_switch_missing_is_observable(self):
        module = load_discovery()
        with mock.patch.dict("os.environ", {"CC_SWITCH_HOME": ""}), mock.patch.object(module, "_running_processes", return_value=set()), mock.patch.object(module.shutil, "which", return_value=None), mock.patch.object(module, "_config_root_home", return_value=None):
            entries = module.discover_cc_switch()
        self.assertEqual(entries[0].source, "missing")
        self.assertEqual(entries[0].executable_realpath, "")

    def test_hermes_gui_launcher_adds_observation(self):
        module = load_discovery()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            launcher = root / "Hermes.exe"
            launcher.write_bytes(b"stub-binary")
            with mock.patch.dict("os.environ", {"HERMES_HOME": str(root)}), mock.patch.object(module, "_running_processes", return_value=set()), mock.patch.object(module.shutil, "which", return_value=None), mock.patch.object(module, "_hermes_gui_launcher", return_value=launcher):
                entries = module.discover_hermes()
        ids = {entry.launcher_id for entry in entries}
        self.assertIn("hermes-gui-exe", ids)
        gui = next(entry for entry in entries if entry.launcher_id == "hermes-gui-exe")
        self.assertEqual(gui.source, "desktop-launcher")
        self.assertEqual(gui.launcher_target, str(launcher))

    def test_hermes_cli_and_gui_resolve_to_alias_duplicate_not_dual_install(self):
        module = load_discovery()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            exe = root / "hermes.exe"
            exe.write_bytes(b"stub-binary")
            launcher = root / "Hermes.exe"
            launcher.write_bytes(b"stub-binary")
            with mock.patch.dict("os.environ", {"HERMES_HOME": str(root)}), mock.patch.object(module, "_running_processes", return_value=set()), mock.patch.object(module.shutil, "which", return_value=str(exe)), mock.patch.object(module, "_hermes_gui_launcher", return_value=launcher):
                observations = module.discover_all()
        hermes_obs = [obs for obs in observations if obs["logical_instance_id"] == "hermes"]
        self.assertEqual(len(hermes_obs), 2)
        resolved = module.identity.resolve_identity(hermes_obs)
        self.assertEqual(resolved["identity_count"], 1)
        self.assertEqual(resolved["identities"][0]["state"], "ALIAS_DUPLICATE")

    def test_discover_all_includes_cc_switch(self):
        module = load_discovery()
        with mock.patch.dict("os.environ", {"CC_SWITCH_HOME": "", "CODEX_HOME": "", "HERMES_HOME": ""}), mock.patch.object(module, "_running_processes", return_value=set()), mock.patch.object(module.shutil, "which", return_value=None):
            observations = module.discover_all()
        ids = {obs["logical_instance_id"] for obs in observations}
        self.assertIn("cc-switch", ids)
        self.assertIn("codex", ids)
        self.assertIn("hermes", ids)

    def test_resolve_current_platform_reports_probe_coverage(self):
        module = load_discovery()
        with mock.patch.dict("os.environ", {"CC_SWITCH_HOME": "", "CODEX_HOME": "", "HERMES_HOME": ""}), mock.patch.object(module, "_running_processes", return_value=set()), mock.patch.object(module.shutil, "which", return_value=None), mock.patch.object(module, "_hermes_gui_launcher", return_value=None):
            resolved = module.resolve_current_platform()
        probed = resolved["probed"]
        for key in ("codex_cli", "hermes_cli", "hermes_gui_launcher", "cc_switch_config_root", "os", "start_menu_links"):
            self.assertIn(key, probed)


if __name__ == "__main__":
    unittest.main()
