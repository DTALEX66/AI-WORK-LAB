"""WLGM-210 tests: sidecar endpoint descriptor validation."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

# Bootstrapped rather than inherited from the batch runner: this module used to resolve both imports only
# because `run_quality_gate.py` happens to put these directories on sys.path, and the conversion that added
# `project_temp` here inserted the line twice while adding neither path.
ROOT = Path(__file__).resolve().parents[2]
for _entry in (str(ROOT / "packages" / "client-neutral-core" / "scripts"),
               str(ROOT / "services" / "orchestration")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

import project_temp  # noqa: E402
import sidecar_endpoint  # noqa: E402
from sidecar_endpoint import (  # noqa: E402
    _pid_alive,
    capability_probe,
    read_descriptor,
    validate_descriptor,
)


def make_descriptor(**overrides):
    descriptor = {
        "schemaVersion": "workflow/sidecar-endpoint/v1",
        "pid": os.getpid(),
        "host": "127.0.0.1",
        "port": 54321,
        "startedAt": time.time(),
        "projectionUrl": "http://127.0.0.1:54321/api/v1/snapshot",
        "eventsUrl": "http://127.0.0.1:54321/api/v1/events",
    }
    descriptor.update(overrides)
    return descriptor


class SidecarEndpointTests(unittest.TestCase):
    def test_valid_descriptor_passes(self) -> None:
        result = validate_descriptor(make_descriptor(), require_ephemeral_port=False)
        self.assertTrue(result.valid, result.errors)

    def test_external_host_rejected(self) -> None:
        result = validate_descriptor(make_descriptor(host="evil.example.com", projectionUrl="http://evil.example.com:54321/api/v1/snapshot"))
        self.assertFalse(result.valid)
        self.assertTrue(any("loopback" in e for e in result.errors))

    def test_wrong_path_rejected(self) -> None:
        result = validate_descriptor(make_descriptor(projectionUrl="http://127.0.0.1:54321/api/dashboard"))
        self.assertFalse(result.valid)
        self.assertTrue(any("path" in e for e in result.errors))

    def test_query_bearing_url_rejected(self) -> None:
        result = validate_descriptor(make_descriptor(projectionUrl="http://127.0.0.1:54321/api/v1/snapshot?write=1"))
        self.assertFalse(result.valid)

    def test_dead_pid_rejected(self) -> None:
        result = validate_descriptor(make_descriptor(pid=99999999))
        self.assertFalse(result.valid)
        self.assertTrue(any("not alive" in e for e in result.errors))

    def test_live_child_pid_accepted(self) -> None:
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"])
        try:
            self.assertTrue(_pid_alive(child.pid))
        finally:
            child.terminate()
            child.wait(timeout=5)

    def test_windows_pid_requires_still_active_exit_code(self) -> None:
        class FakeFunction:
            def __init__(self, callback) -> None:
                self.callback = callback
                self.argtypes = None
                self.restype = None

            def __call__(self, *args):
                return self.callback(*args)

        class FakeKernel32:
            def __init__(self, exit_code: int) -> None:
                self.exit_code = exit_code
                self.closed = False
                self.OpenProcess = FakeFunction(lambda *_args: 1234)
                self.GetExitCodeProcess = FakeFunction(self._get_exit_code)
                self.CloseHandle = FakeFunction(self._close_handle)

            def _get_exit_code(self, _handle, output) -> int:
                output._obj.value = self.exit_code
                return 1

            def _close_handle(self, _handle) -> int:
                self.closed = True
                return 1

        running_kernel = FakeKernel32(259)
        with mock.patch.object(sidecar_endpoint.os, "name", "nt"), mock.patch(
            "ctypes.WinDLL", return_value=running_kernel, create=True
        ):
            self.assertTrue(_pid_alive(4242))
        self.assertTrue(running_kernel.closed)

        exited_kernel = FakeKernel32(0)
        with mock.patch.object(sidecar_endpoint.os, "name", "nt"), mock.patch(
            "ctypes.WinDLL", return_value=exited_kernel, create=True
        ):
            self.assertFalse(_pid_alive(4242))
        self.assertTrue(exited_kernel.closed)

    def test_future_started_at_rejected(self) -> None:
        result = validate_descriptor(make_descriptor(startedAt=time.time() + 3600))
        self.assertFalse(result.valid)
        self.assertTrue(any("future" in e for e in result.errors))

    def test_old_started_at_rejected(self) -> None:
        result = validate_descriptor(make_descriptor(startedAt=time.time() - 100 * 3600))
        self.assertFalse(result.valid)
        self.assertTrue(any("too old" in e for e in result.errors))

    def test_ephemeral_port_requirement(self) -> None:
        ok = validate_descriptor(make_descriptor(port=54321), require_ephemeral_port=True)
        self.assertTrue(ok.valid, ok.errors)
        low = validate_descriptor(make_descriptor(port=8080), require_ephemeral_port=True)
        self.assertFalse(low.valid)

    def test_none_descriptor_fails(self) -> None:
        result = validate_descriptor(None)
        self.assertFalse(result.valid)

    def test_read_descriptor_roundtrip(self) -> None:
        raw = tempfile.TemporaryDirectory()
        self.addCleanup(raw.cleanup)
        path = Path(raw.name) / "sidecar-endpoint.json"
        path.write_text(json.dumps(make_descriptor()), encoding="utf-8")
        descriptor = read_descriptor(path)
        self.assertIsNotNone(descriptor)
        self.assertEqual(descriptor["schemaVersion"], "workflow/sidecar-endpoint/v1")
        self.assertTrue(validate_descriptor(descriptor).valid)

    def test_read_missing_returns_none(self) -> None:
        self.assertIsNone(read_descriptor(project_temp.fixture_dir(prefix="endpoint-") / "missing.json"))

    def test_capability_probe(self) -> None:
        probe = capability_probe(make_descriptor())
        self.assertTrue(probe["installed"])
        self.assertIn("snapshot_v3", probe["capabilities"])
        none = capability_probe(None)
        self.assertFalse(none["installed"])
        self.assertEqual(none["capabilities"], [])


if __name__ == "__main__":
    unittest.main()
