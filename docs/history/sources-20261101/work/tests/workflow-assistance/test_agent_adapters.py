"""WLGM-080/090 tests: Hermes + Codex read-only adapters."""
from __future__ import annotations

import os
import unittest
from unittest import mock

from adapter_sdk import CapabilityUnsupported
from codex_adapter import CodexAdapter
from hermes_adapter import HERMES_SESSION_ENV, HermesAdapter


class HermesAdapterTests(unittest.TestCase):
    @mock.patch("hermes_adapter.shutil.which", return_value=None)
    def test_probe_when_not_installed(self, _which) -> None:
        adapter = HermesAdapter(hermes_bin=None)
        probe = adapter.probe()
        self.assertFalse(probe.installed)
        self.assertNotIn("run_status", probe.capabilities)

    @mock.patch("hermes_adapter.shutil.which", return_value="C:/bin/hermes.exe")
    @mock.patch("hermes_adapter.HermesAdapter._read_only", return_value="Model: x\nProvider: y\n")
    def test_probe_when_installed_and_status_reachable(self, _read, _which) -> None:
        adapter = HermesAdapter(hermes_bin="C:/bin/hermes.exe")
        probe = adapter.probe()
        self.assertTrue(probe.installed)
        self.assertIn("run_status", probe.capabilities)
        self.assertIn("session_list", probe.capabilities)

    @mock.patch.dict(os.environ, {HERMES_SESSION_ENV: "sess-abc"}, clear=False)
    def test_session_list_uses_correlation_env(self) -> None:
        adapter = HermesAdapter(hermes_bin="C:/bin/hermes.exe")
        with mock.patch.object(adapter, "probe", return_value=adapter.probe()):
            pass
        # force capability check
        from adapter_sdk import AdapterProbe

        with mock.patch.object(
            adapter, "probe",
            return_value=AdapterProbe(adapter_id="hermes", installed=True, capabilities={"session_list"}),
        ):
            sessions = adapter.session_list()
        self.assertEqual(sessions[0]["sessionId"], "sess-abc")
        self.assertEqual(sessions[0]["source"], "HERMES_SESSION_ID")

    def test_run_status_unsupported_when_surface_unreachable(self) -> None:
        adapter = HermesAdapter(hermes_bin="")
        with self.assertRaises(CapabilityUnsupported):
            adapter.run_status()


class CodexAdapterTests(unittest.TestCase):
    @mock.patch("codex_adapter.shutil.which", return_value=None)
    def test_probe_not_installed(self, _which) -> None:
        adapter = CodexAdapter(codex_bin=None)
        probe = adapter.probe()
        self.assertFalse(probe.installed)
        self.assertEqual(probe.capabilities, set())

    @mock.patch("codex_adapter.shutil.which", return_value="C:/bin/codex.exe")
    def test_probe_installed_reports_heartbeat_only(self, _which) -> None:
        adapter = CodexAdapter(codex_bin="C:/bin/codex.exe")
        with mock.patch.object(adapter, "_version", return_value="0.44.0"):
            probe = adapter.probe()
        self.assertTrue(probe.installed)
        self.assertEqual(probe.capabilities, {"heartbeat"})
        self.assertIn("0.44.0", probe.detail)

    def test_session_list_never_reads_private_store(self) -> None:
        adapter = CodexAdapter(codex_bin="C:/bin/codex.exe")
        with self.assertRaises(CapabilityUnsupported):
            adapter.session_list()

    def test_run_status_explicit_unsupported(self) -> None:
        adapter = CodexAdapter(codex_bin=None)
        with self.assertRaises(CapabilityUnsupported):
            adapter.run_status()

    def test_probe_official_surfaces_read_only(self) -> None:
        """WLOSS-400: app-server/hooks/ACP presence probe never starts anything."""
        adapter = CodexAdapter(codex_bin="C:/bin/codex.exe")
        with mock.patch.object(adapter, "_read_help", return_value="Usage: codex [OPTIONS]\n  app-server    Run the local app server\n  hook          Manage hooks\n  acp           Agent Client Protocol\n"):
            surfaces = adapter.probe_official_surfaces()
        self.assertTrue(surfaces["app_server"])
        self.assertTrue(surfaces["hooks"])
        self.assertTrue(surfaces["acp"])

    @mock.patch("codex_adapter.shutil.which", return_value=None)
    def test_probe_official_surfaces_not_installed(self, _which) -> None:
        adapter = CodexAdapter(codex_bin=None)
        self.assertEqual(adapter.probe_official_surfaces(), {"app_server": False, "hooks": False, "acp": False})


if __name__ == "__main__":
    unittest.main()
